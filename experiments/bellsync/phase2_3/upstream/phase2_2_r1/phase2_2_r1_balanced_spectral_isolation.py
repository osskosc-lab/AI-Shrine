#!/usr/bin/env python3
"""AI Shrine / BellSync Phase 2-2-r1.

Balanced Spectral Isolation Audit

This script is intentionally self-contained because the supplied workspace did
not contain an existing Phase 2 implementation.  It preserves the frozen
Phase 2-2 result as metadata and does not use simulation outcomes to select
graphs, seeds, parameters, or gates.

Run:
    python phase2_2_r1_balanced_spectral_isolation.py \
        --output-dir phase2_2_r1_results
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import platform
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

import numpy as np


# ---------------------------------------------------------------------------
# Frozen ledger and preregistered design constants
# ---------------------------------------------------------------------------

FROZEN_LEDGER = {
    "phase2_2_verdict": "PHASE2_2_FAIL_SPECTRAL_DETERMINATION",
    "phase2_2_status": "FROZEN",
    "critical_counterexample": (
        "lambda_2(Expander) > lambda_2(Barbell) but "
        "Gain(Expander) < Gain(Barbell)"
    ),
    "frozen_claim_firewall": [
        "SPECTRAL_GAP_SCALING_SUPPORTED_WITHIN_TESTED_TOPOLOGIES",
        "UNIVERSAL_LAMBDA2_DETERMINATION_REJECTED",
    ],
}


@dataclass(frozen=True)
class Design:
    n_nodes: int = 8
    dim: int = 64
    num_seeds: int = 30
    steps: int = 45
    alpha: float = 0.6
    gamma: float = 0.25
    rho: float = 0.85
    sigma: float = 0.01
    gamma_corr: float = 20.0
    theta_m: float = 10.206415
    beta: float = 0.3
    v_norm: float = 0.02
    impulse_norm: float = 1.0
    shock_time: int = 15
    initialization_seed_base: int = 100_000
    impulse_seed_base: int = 200_000
    node_noise_seed_base: int = 300_000
    bootstrap_seed: int = 42
    bootstrap_reps: int = 5_000
    init_scale: float = 0.1
    centroid_ratio_tolerance: float = 1e-9
    lambda2_margin: float = 1e-8
    balance_tolerance: float = 1e-12


# These edge lists are a fixed, preregistered candidate pool.  They were
# generated independently of the synchronization simulation.  The final low
# and high lambda_2 member of each k-regular pool is chosen by spectral values
# only, with deterministic lexicographic tie-breaking.
PREREGISTERED_CANDIDATES: Dict[int, Dict[str, List[List[int]]]] = {
    3: {
        "candidate_k3_seed79": [
            [0, 4], [0, 6], [0, 7], [1, 2], [1, 3], [1, 5],
            [2, 5], [2, 6], [3, 4], [3, 7], [4, 7], [5, 6],
        ],
        "candidate_k3_seed97": [
            [0, 2], [0, 4], [0, 6], [1, 2], [1, 4], [1, 5],
            [2, 7], [3, 4], [3, 5], [3, 6], [5, 7], [6, 7],
        ],
    },
    4: {
        "candidate_k4_seed34": [
            [0, 2], [0, 3], [0, 4], [0, 7], [1, 2], [1, 4],
            [1, 5], [1, 6], [2, 3], [2, 7], [3, 6], [3, 7],
            [4, 5], [4, 6], [5, 6], [5, 7],
        ],
        "candidate_k4_seed22": [
            [0, 2], [0, 3], [0, 4], [0, 6], [1, 2], [1, 3],
            [1, 6], [1, 7], [2, 4], [2, 5], [3, 5], [3, 7],
            [4, 5], [4, 7], [5, 6], [6, 7],
        ],
    },
}


def jsonable(value: Any) -> Any:
    """Convert NumPy values into strict JSON-compatible values."""
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    return value


def write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(jsonable(payload), indent=2, sort_keys=True, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )


def make_adjacency(n_nodes: int, edges: Iterable[Sequence[int]]) -> np.ndarray:
    adjacency = np.zeros((n_nodes, n_nodes), dtype=float)
    seen = set()
    for raw_u, raw_v in edges:
        u, v = int(raw_u), int(raw_v)
        if u == v:
            raise ValueError(f"self-loop is not allowed: {(u, v)}")
        edge = tuple(sorted((u, v)))
        if edge in seen:
            raise ValueError(f"duplicate edge: {edge}")
        seen.add(edge)
        adjacency[u, v] = 1.0
        adjacency[v, u] = 1.0
    return adjacency


def connected(adjacency: np.ndarray) -> bool:
    n_nodes = adjacency.shape[0]
    visited = {0}
    frontier = [0]
    while frontier:
        node = frontier.pop()
        for neighbor in np.flatnonzero(adjacency[node] > 0):
            neighbor = int(neighbor)
            if neighbor not in visited:
                visited.add(neighbor)
                frontier.append(neighbor)
    return len(visited) == n_nodes


def graph_record(
    name: str,
    pair: str,
    role: str,
    adjacency: np.ndarray,
    expected_degree: int,
    design: Design,
) -> Dict[str, Any]:
    degrees = adjacency.sum(axis=1)
    edge_count = int(round(adjacency.sum() / 2.0))
    weight = adjacency / float(expected_degree)
    laplacian = np.eye(design.n_nodes) - weight
    eigenvalues = np.linalg.eigvalsh(laplacian)
    eigenvalues[np.abs(eigenvalues) < 1e-14] = 0.0
    row_sums = weight.sum(axis=1)
    column_sums = weight.sum(axis=0)
    record = {
        "name": name,
        "pair": pair,
        "role": role,
        "expected_degree": expected_degree,
        "adjacency": adjacency,
        "W": weight,
        "edge_count": edge_count,
        "degree_sequence": [int(round(v)) for v in degrees.tolist()],
        "degree_sequence_sorted": sorted(int(round(v)) for v in degrees.tolist()),
        "connected": connected(adjacency),
        "symmetric_error_fro": float(np.linalg.norm(weight - weight.T, ord="fro")),
        "max_row_sum_error": float(np.max(np.abs(row_sums - 1.0))),
        "max_column_sum_error": float(np.max(np.abs(column_sums - 1.0))),
        "row_sums": row_sums,
        "column_sums": column_sums,
        "laplacian_eigenvalues": eigenvalues,
        "lambda_2": float(eigenvalues[1]),
        "lambda_max": float(eigenvalues[-1]),
    }
    return record


def select_spectral_pair(design: Design, degree: int, pair_name: str) -> Tuple[Dict[str, Any], Dict[str, Any], List[Dict[str, Any]]]:
    candidates = []
    for candidate_name, edges in PREREGISTERED_CANDIDATES[degree].items():
        adjacency = make_adjacency(design.n_nodes, edges)
        candidate = graph_record(
            name=candidate_name,
            pair=pair_name,
            role="candidate",
            adjacency=adjacency,
            expected_degree=degree,
            design=design,
        )
        candidate["candidate_edges"] = edges
        candidates.append(candidate)

    valid = [c for c in candidates if c["connected"]]
    if len(valid) < 2:
        raise RuntimeError(f"not enough connected candidates for {pair_name}")

    low = min(valid, key=lambda c: (c["lambda_2"], c["name"]))
    high = max(valid, key=lambda c: (c["lambda_2"], c["name"]))
    if high["name"] == low["name"]:
        raise RuntimeError(f"spectral pair collapsed for {pair_name}")

    low = dict(low)
    high = dict(high)
    low["role"] = "low_lambda2"
    high["role"] = "high_lambda2"
    return low, high, candidates


def validate_primary_pairs(
    pairs: Dict[str, Tuple[Dict[str, Any], Dict[str, Any]]], design: Design
) -> Dict[str, Any]:
    pair_results: Dict[str, Any] = {}
    all_pass = True
    for pair_name, (low, high) in pairs.items():
        checks = {
            "same_n": low["adjacency"] .shape == high["adjacency"].shape == (design.n_nodes, design.n_nodes),
            "same_edge_count": low["edge_count"] == high["edge_count"],
            "same_degree_sequence": low["degree_sequence_sorted"] == high["degree_sequence_sorted"],
            "low_connected": bool(low["connected"]),
            "high_connected": bool(high["connected"]),
            "low_symmetric": low["symmetric_error_fro"] <= design.balance_tolerance,
            "high_symmetric": high["symmetric_error_fro"] <= design.balance_tolerance,
            "low_row_stochastic": low["max_row_sum_error"] <= design.balance_tolerance,
            "high_row_stochastic": high["max_row_sum_error"] <= design.balance_tolerance,
            "low_column_stochastic": low["max_column_sum_error"] <= design.balance_tolerance,
            "high_column_stochastic": high["max_column_sum_error"] <= design.balance_tolerance,
            "lambda2_nontrivial": (high["lambda_2"] - low["lambda_2"]) > design.lambda2_margin,
        }
        checks["pair_pass"] = all(checks.values())
        all_pass = all_pass and checks["pair_pass"]
        pair_results[pair_name] = {
            "low_graph": low["name"],
            "high_graph": high["name"],
            "edge_count": low["edge_count"],
            "degree_sequence_sorted": low["degree_sequence_sorted"],
            "lambda2_low": low["lambda_2"],
            "lambda2_high": high["lambda_2"],
            "lambda2_difference": high["lambda_2"] - low["lambda_2"],
            "checks": checks,
        }
    return {"all_primary_pairs_pass": all_pass, "pairs": pair_results}


def run_serialization_test(design: Design, pairs: Dict[str, Tuple[Dict[str, Any], Dict[str, Any]]]) -> Dict[str, Any]:
    """Scoped AISP-compatible manifest round-trip test.

    No legacy AISP test was available in this workspace.  This test is kept
    explicit so that serialization failure blocks the experiment rather than
    being silently ignored.
    """
    manifest = {
        "design": asdict(design),
        "pairs": {
            pair_name: {
                "low": {"name": low["name"], "edges": low["candidate_edges"]},
                "high": {"name": high["name"], "edges": high["candidate_edges"]},
            }
            for pair_name, (low, high) in pairs.items()
        },
        "frozen_ledger": FROZEN_LEDGER,
    }
    encoded = json.dumps(jsonable(manifest), sort_keys=True, allow_nan=False)
    decoded = json.loads(encoded)
    reencoded = json.dumps(decoded, sort_keys=True, allow_nan=False)
    passed = encoded == reencoded
    return {
        "passed": passed,
        "scope": "AISP-compatible experiment manifest serialization round-trip",
        "legacy_test_available_in_workspace": False,
        "encoded_sha256_like_length": len(encoded),
        "failure_action": "block_simulation" if not passed else "none",
    }


def make_inputs(seed: int, design: Design) -> Dict[str, Any]:
    """Create paired random inputs once per seed and reuse across conditions."""
    init_rng = np.random.default_rng(design.initialization_seed_base + seed)
    impulse_rng = np.random.default_rng(design.impulse_seed_base + seed)

    initial_states = design.init_scale * init_rng.standard_normal((design.n_nodes, design.dim))
    drift_direction = init_rng.standard_normal(design.dim)
    drift_direction /= np.linalg.norm(drift_direction)
    drift_vector = design.v_norm * drift_direction

    impulse_direction = impulse_rng.standard_normal(design.dim)
    impulse_direction /= np.linalg.norm(impulse_direction)
    impulse_vector = design.impulse_norm * impulse_direction
    impulse_node = int(impulse_rng.integers(0, design.n_nodes))

    node_noise = np.empty((design.steps, design.n_nodes, design.dim), dtype=float)
    noise_seed_records = []
    # One independent RNG per node, as preregistered.
    for node in range(design.n_nodes):
        node_seed = design.node_noise_seed_base + seed * design.n_nodes + node
        node_rng = np.random.default_rng(node_seed)
        node_noise[:, node, :] = design.sigma * node_rng.standard_normal((design.steps, design.dim))
        noise_seed_records.append(node_seed)

    return {
        "initial_states": initial_states,
        "drift_vector": drift_vector,
        "impulse_vector": impulse_vector,
        "impulse_node": impulse_node,
        "node_noise": node_noise,
        "seed_records": {
            "initialization_seed": design.initialization_seed_base + seed,
            "impulse_seed": design.impulse_seed_base + seed,
            "node_noise_seeds": noise_seed_records,
        },
    }


def simulate_condition(weight: np.ndarray, inputs: Dict[str, Any], design: Design) -> Dict[str, Any]:
    states = inputs["initial_states"].copy()
    drift_vector = inputs["drift_vector"]
    impulse_vector = inputs["impulse_vector"]
    node_noise = inputs["node_noise"]
    impulse_node = inputs["impulse_node"]

    spread_values = []
    centroid_energy_values = []
    target_history = []

    for t in range(design.steps):
        target_t = t * drift_vector
        target_next = (t + 1) * drift_vector

        # The shock is a state-time intervention: inject into one node before
        # transition t -> t+1. The node and direction are paired across graphs.
        if t == design.shock_time:
            states[impulse_node] = states[impulse_node] + impulse_vector

        coupling = np.zeros_like(states)
        for i in range(design.n_nodes):
            for j in range(design.n_nodes):
                if weight[i, j] != 0.0:
                    coupling[i] += weight[i, j] * np.tanh(states[j] - states[i])

        states = (
            states
            + design.alpha * (target_t - states)
            + design.beta * coupling
            + node_noise[t]
        )

        centroid = states.mean(axis=0)
        centered = states - centroid
        spread_values.append(float(np.mean(np.sum(centered * centered, axis=1))))
        centroid_error = centroid - target_next
        centroid_energy_values.append(float(0.5 * np.dot(centroid_error, centroid_error)))
        target_history.append(target_next)

    spread = np.asarray(spread_values)
    centroid_energy = np.asarray(centroid_energy_values)
    return {
        "spread_series": spread,
        "centroid_energy_series": centroid_energy,
        "auc_spread": float(spread.sum()),
        "auc_centroid": float(centroid_energy.sum()),
        "final_spread": float(spread[-1]),
        "final_centroid_energy": float(centroid_energy[-1]),
    }


def bootstrap_mean(values: np.ndarray, design: Design) -> Dict[str, float]:
    rng = np.random.default_rng(design.bootstrap_seed)
    samples = rng.integers(0, len(values), size=(design.bootstrap_reps, len(values)))
    bootstrap_means = values[samples].mean(axis=1)
    return {
        "mean": float(values.mean()),
        "ci95_low": float(np.quantile(bootstrap_means, 0.025)),
        "ci95_high": float(np.quantile(bootstrap_means, 0.975)),
    }


def safe_ratio(numerator: float, denominator: float) -> float:
    if denominator == 0.0:
        return math.nan
    return numerator / denominator


def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def compact_graph_record(record: Dict[str, Any]) -> Dict[str, Any]:
    return {
        key: value
        for key, value in record.items()
        if key not in {"adjacency", "W", "row_sums", "column_sums"}
    } | {
        "adjacency": record["adjacency"],
        "W": record["W"],
        "row_sums": record["row_sums"],
        "column_sums": record["column_sums"],
    }


def audit_rows(records: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []
    for record in records:
        rows.append(
            {
                "name": record["name"],
                "pair": record["pair"],
                "role": record["role"],
                "edge_count": record["edge_count"],
                "degree_sequence": ";".join(map(str, record["degree_sequence"])),
                "degree_sequence_sorted": ";".join(map(str, record["degree_sequence_sorted"])),
                "connected": record["connected"],
                "symmetry_error_fro": f"{record['symmetric_error_fro']:.17g}",
                "max_row_sum_error": f"{record['max_row_sum_error']:.17g}",
                "max_column_sum_error": f"{record['max_column_sum_error']:.17g}",
                "lambda_2": f"{record['lambda_2']:.17g}",
                "lambda_max": f"{record['lambda_max']:.17g}",
                "laplacian_eigenvalues": ";".join(f"{x:.17g}" for x in record["laplacian_eigenvalues"]),
            }
        )
    return rows


def pair_analysis(
    pair_name: str,
    low: Dict[str, Any],
    high: Dict[str, Any],
    rows: List[Dict[str, Any]],
    design: Design,
) -> Dict[str, Any]:
    by_condition = {}
    for graph_name in ["ISOLATED", low["name"], high["name"]]:
        selected = [row for row in rows if row["condition"] == graph_name]
        by_condition[graph_name] = selected

    isolated_auc_d = np.asarray([r["auc_spread"] for r in by_condition["ISOLATED"]], dtype=float)
    low_auc_d = np.asarray([r["auc_spread"] for r in by_condition[low["name"]]], dtype=float)
    high_auc_d = np.asarray([r["auc_spread"] for r in by_condition[high["name"]]], dtype=float)
    low_auc_e = np.asarray([r["auc_centroid"] for r in by_condition[low["name"]]], dtype=float)
    high_auc_e = np.asarray([r["auc_centroid"] for r in by_condition[high["name"]]], dtype=float)
    isolated_auc_e = np.asarray([r["auc_centroid"] for r in by_condition["ISOLATED"]], dtype=float)

    delta_pair = (low_auc_d - high_auc_d) / low_auc_d
    centroid_ratio_per_seed = high_auc_e / low_auc_e
    gain_low_per_seed = 1.0 - low_auc_d / isolated_auc_d
    gain_high_per_seed = 1.0 - high_auc_d / isolated_auc_d
    gain_difference_per_seed = gain_high_per_seed - gain_low_per_seed

    delta_bootstrap = bootstrap_mean(delta_pair, design)
    gain_difference_bootstrap = bootstrap_mean(gain_difference_per_seed, design)
    centroid_deviation = np.abs(centroid_ratio_per_seed - 1.0)
    centroid_ratio = safe_ratio(float(high_auc_e.mean()), float(low_auc_e.mean()))

    gate_g4 = delta_bootstrap["mean"] > 0.0 and delta_bootstrap["ci95_low"] > 0.0
    gate_g5 = bool(np.all(centroid_deviation <= design.centroid_ratio_tolerance))

    condition_summary = {}
    for graph_name, graph_rows in by_condition.items():
        auc_d = np.asarray([r["auc_spread"] for r in graph_rows], dtype=float)
        auc_e = np.asarray([r["auc_centroid"] for r in graph_rows], dtype=float)
        condition_summary[graph_name] = {
            "mean_auc_spread": float(auc_d.mean()),
            "mean_auc_centroid": float(auc_e.mean()),
            "R_sync_vs_isolated": safe_ratio(float(auc_d.mean()), float(isolated_auc_d.mean())),
            "sync_gain_vs_isolated": 1.0 - safe_ratio(float(auc_d.mean()), float(isolated_auc_d.mean())),
            "centroid_ratio_vs_isolated": safe_ratio(float(auc_e.mean()), float(isolated_auc_e.mean())),
        }

    return {
        "pair": pair_name,
        "low_graph": low["name"],
        "high_graph": high["name"],
        "lambda2_low": low["lambda_2"],
        "lambda2_high": high["lambda_2"],
        "lambda2_difference": high["lambda_2"] - low["lambda_2"],
        "condition_summary": condition_summary,
        "delta_pair": {
            **delta_bootstrap,
            "sign_positive_count": int(np.sum(delta_pair > 0.0)),
            "sign_positive_fraction": float(np.mean(delta_pair > 0.0)),
            "per_seed": delta_pair,
        },
        "gain_difference_high_minus_low": {
            **gain_difference_bootstrap,
            "per_seed": gain_difference_per_seed,
        },
        "centroid_ratio_high_over_low": centroid_ratio,
        "centroid_ratio_per_seed": centroid_ratio_per_seed,
        "centroid_max_abs_deviation": float(centroid_deviation.max()),
        "gates": {
            "G4_SPECTRAL_GAIN": bool(gate_g4),
            "G5_CENTROID_NEUTRALITY": bool(gate_g5),
        },
    }


def render_report(
    path: Path,
    design: Design,
    serialization: Dict[str, Any],
    audit: Dict[str, Any],
    pair_results: List[Dict[str, Any]],
    simulation_ran: bool,
    verdict: str,
    claim_firewall: List[str],
    runtime: Dict[str, Any],
) -> None:
    lines = []
    lines.append("# AI Shrine / BellSync Phase 2-2-r1 実験報告書")
    lines.append("")
    lines.append("## 1. 判定要約")
    lines.append("")
    lines.append(f"- 最終 Verdict: `{verdict}`")
    lines.append(f"- Phase 2-2 の凍結判定: `{FROZEN_LEDGER['phase2_2_verdict']}`（変更なし）")
    lines.append(f"- シミュレーション実行: `{simulation_ran}`")
    lines.append("- グラフ選定: シミュレーション結果を参照せず、固定候補のスペクトル値のみで実施")
    lines.append("")
    lines.append("## 2. 設計・実装上の固定事項")
    lines.append("")
    lines.append("- 主モデル: `x_{i,t+1} = x_{i,t} + alpha(x*_t - x_{i,t}) + beta sum_j W_ij tanh(x_{j,t}-x_{i,t}) + epsilon_{i,t}`")
    lines.append("- `x*_t = t v`、`||v|| = 0.02`。初期標的はゼロ。")
    lines.append("- 初期状態は `0.1 * N(0,1)`。このスケールは結果を見る前に固定した実装上の追加仮定。")
    lines.append("- `gamma`, `rho`, `gamma_corr`, `theta_M` は凍結台帳へ記録するが、提示されたPhase 2多ノード更新式には直接現れないため、この監査の遷移計算では使用しない。")
    lines.append("- 衝撃は state-time `t=15` に、seedごとに選ぶ1ノードへ norm 1.0 のベクトルを遷移前に注入。")
    lines.append("- ノイズはノードごとに独立RNGを持ち、paired graph conditionsで同一系列を再利用。")
    lines.append("- AUCは45回の遷移後状態について `sum_t D_t`、`sum_t E_centroid_t`。")
    lines.append("- G5の事前固定許容幅: `|centroid_ratio - 1| <= 1e-9`。")
    lines.append("")
    lines.append("## 3. 実装前スペクトル監査")
    lines.append("")
    lines.append("詳細は `spectral_audit.csv` と `graphs_and_spectra.json` に保存した。")
    lines.append("")
    lines.append("| Pair | Low graph | High graph | edge count | degree sequence | lambda2 low | lambda2 high | lambda2 difference | Pair audit |")
    lines.append("|---|---|---|---:|---|---:|---:|---:|---|")
    for pair_name, info in audit["pairs"].items():
        lines.append(
            f"| {pair_name} | {info['low_graph']} | {info['high_graph']} | "
            f"{info['edge_count']} | {','.join(map(str, info['degree_sequence_sorted']))} | "
            f"{info['lambda2_low']:.9f} | {info['lambda2_high']:.9f} | "
            f"{info['lambda2_difference']:.9f} | {info['checks']['pair_pass']} |"
        )
    lines.append("")
    lines.append("G0 serialization:")
    lines.append("")
    lines.append(f"- scoped manifest round-trip: `{serialization['passed']}`")
    lines.append("- 注記: ワークスペースに既存AISPテストは存在しなかったため、AISP互換の明示的round-trip self-testを使用した。")
    lines.append("")
    lines.append("## 4. 30 seed 実測結果")
    lines.append("")
    if not simulation_ran:
        lines.append("設計監査が不成立のため、同期シミュレーションは実行していない。")
    else:
        for result in pair_results:
            lines.append(f"### {result['pair']}")
            lines.append("")
            lines.append("| Condition | Mean AUC(D) | Mean AUC(E_centroid) | R_sync vs isolated | Sync Gain |")
            lines.append("|---|---:|---:|---:|---:|")
            for condition, summary in result["condition_summary"].items():
                lines.append(
                    f"| {condition} | {summary['mean_auc_spread']:.9f} | "
                    f"{summary['mean_auc_centroid']:.9f} | {summary['R_sync_vs_isolated']:.9f} | "
                    f"{summary['sync_gain_vs_isolated'] * 100:.6f}% |"
                )
            delta = result["delta_pair"]
            lines.append("")
            lines.append(
                f"- Delta_pair mean: `{delta['mean']:.9f}`; paired bootstrap 95% CI "
                f"`[{delta['ci95_low']:.9f}, {delta['ci95_high']:.9f}]`; "
                f"positive seeds `{delta['sign_positive_count']}/30`."
            )
            lines.append(
                f"- centroid ratio high/low: `{result['centroid_ratio_high_over_low']:.12f}`; "
                f"max absolute deviation: `{result['centroid_max_abs_deviation']:.3e}`."
            )
    lines.append("")
    lines.append("## 5. Gate Verification Matrix")
    lines.append("")
    lines.append("| Gate | 判定 | 根拠 |")
    lines.append("|---|---|---|")
    g0_status = "PASS_SCOPED_SELF_TEST" if serialization["passed"] else "FAIL"
    lines.append(f"| G0_SERIALIZATION | `{g0_status}` | manifest round-trip; legacy AISP test unavailable |")
    lines.append(f"| G1_GRAPH_BALANCE | `{audit['all_primary_pairs_pass']}` | symmetry/stochasticity checks |")
    lines.append(f"| G2_MATCHED_STRUCTURE | `{audit['all_primary_pairs_pass']}` | N, edge count, degree sequence |")
    lines.append(f"| G3_SPECTRAL_ORDERING | `{audit['all_primary_pairs_pass']}` | high lambda2 > low lambda2 |")
    if simulation_ran:
        for result in pair_results:
            lines.append(
                f"| G4_SPECTRAL_GAIN [{result['pair']}] | `{result['gates']['G4_SPECTRAL_GAIN']}` | "
                f"Delta mean/CI = {result['delta_pair']['mean']:.9f} "
                f"[{result['delta_pair']['ci95_low']:.9f}, {result['delta_pair']['ci95_high']:.9f}] |"
            )
            lines.append(
                f"| G5_CENTROID_NEUTRALITY [{result['pair']}] | `{result['gates']['G5_CENTROID_NEUTRALITY']}` | "
                f"ratio = {result['centroid_ratio_high_over_low']:.12f} |"
            )
    else:
        lines.append("| G4_SPECTRAL_GAIN | `NOT_RUN` | design audit failed |")
        lines.append("| G5_CENTROID_NEUTRALITY | `NOT_RUN` | design audit failed |")
    lines.append("")
    lines.append("## 6. Claim Firewall 更新")
    lines.append("")
    for claim in claim_firewall:
        lines.append(f"- `{claim}`")
    lines.append("")
    lines.append("禁止事項は維持する: universal `Delta_sync = f(lambda_2)`、lambda2唯一支配、大規模外挿、量子的Bell相関、自発秩序・創発の証明。")
    lines.append("")
    lines.append("## 7. 次段階の最小1ステップ")
    lines.append("")
    lines.append("同じpaired balanced条件を固定したまま、N=8内で未使用の正則グラフペアを1組だけblind replicationする。")
    lines.append("")
    lines.append("## 8. 再現情報")
    lines.append("")
    lines.append(f"- Python: `{runtime['python_version']}`")
    lines.append(f"- NumPy: `{runtime['numpy_version']}`")
    lines.append(f"- 実行環境: `{runtime['platform']}`")
    lines.append("- 詳細データ: `simulation_results.csv`, `pair_results.json`, `graphs_and_spectra.json`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def execute(output_dir: Path) -> Dict[str, Any]:
    design = Design()
    output_dir.mkdir(parents=True, exist_ok=True)

    # Construction and spectral selection occur before any simulation call.
    pair_a_low, pair_a_high, pair_a_candidates = select_spectral_pair(design, 3, "PAIR_A_3REGULAR")
    pair_b_low, pair_b_high, pair_b_candidates = select_spectral_pair(design, 4, "PAIR_B_4REGULAR")
    pairs = {
        "PAIR_A_3REGULAR": (pair_a_low, pair_a_high),
        "PAIR_B_4REGULAR": (pair_b_low, pair_b_high),
    }
    candidate_records = pair_a_candidates + pair_b_candidates
    audit = validate_primary_pairs(pairs, design)
    serialization = run_serialization_test(design, pairs)

    write_json(output_dir / "experiment_manifest.json", {
        "title": "AI Shrine Phase 2-2-r1 Balanced Spectral Isolation Audit",
        "version": "1.0",
        "research_mode": "falsification_first",
        "frozen_ledger": FROZEN_LEDGER,
        "design": asdict(design),
        "selection_rule": "low/high lambda_2 selected from fixed candidate pool before simulation; no simulation outcomes used",
        "candidate_pool": [compact_graph_record(r) for r in candidate_records],
        "selected_pairs": {
            pair_name: {
                "low": compact_graph_record(low),
                "high": compact_graph_record(high),
            }
            for pair_name, (low, high) in pairs.items()
        },
        "serialization_test": serialization,
    })
    write_json(output_dir / "graphs_and_spectra.json", {
        "candidate_pool": [compact_graph_record(r) for r in candidate_records],
        "selected_pairs": {
            pair_name: {
                "low": compact_graph_record(low),
                "high": compact_graph_record(high),
            }
            for pair_name, (low, high) in pairs.items()
        },
        "audit": audit,
    })
    write_csv(output_dir / "spectral_audit.csv", audit_rows(candidate_records))

    design_audit_pass = bool(audit["all_primary_pairs_pass"] and serialization["passed"])
    all_rows: List[Dict[str, Any]] = []
    pair_results: List[Dict[str, Any]] = []

    if design_audit_pass:
        # The same base inputs are generated once per seed and passed to all
        # graph conditions, enforcing paired initialization, impulse, and noise.
        selected_conditions = {
            "ISOLATED": np.zeros((design.n_nodes, design.n_nodes), dtype=float),
            pair_a_low["name"]: pair_a_low["W"],
            pair_a_high["name"]: pair_a_high["W"],
            pair_b_low["name"]: pair_b_low["W"],
            pair_b_high["name"]: pair_b_high["W"],
        }
        for seed in range(design.num_seeds):
            inputs = make_inputs(seed, design)
            for condition, weight in selected_conditions.items():
                result = simulate_condition(weight, inputs, design)
                all_rows.append({
                    "seed": seed,
                    "condition": condition,
                    "impulse_node": inputs["impulse_node"],
                    "auc_spread": result["auc_spread"],
                    "auc_centroid": result["auc_centroid"],
                    "final_spread": result["final_spread"],
                    "final_centroid_energy": result["final_centroid_energy"],
                })

        pair_results.append(pair_analysis("PAIR_A_3REGULAR", pair_a_low, pair_a_high, all_rows, design))
        pair_results.append(pair_analysis("PAIR_B_4REGULAR", pair_b_low, pair_b_high, all_rows, design))

        all_g4 = all(r["gates"]["G4_SPECTRAL_GAIN"] for r in pair_results)
        all_g5 = all(r["gates"]["G5_CENTROID_NEUTRALITY"] for r in pair_results)
        if not all_g5:
            verdict = "PHASE2_2_R1_CENTROID_CONFOUNDING"
        elif all_g4:
            verdict = "PHASE2_2_R1_BALANCED_SPECTRAL_EFFECT_SUPPORTED"
        else:
            verdict = "PHASE2_2_R1_SPECTRAL_ISOLATION_FAIL"
    else:
        verdict = "PHASE2_2_R1_DESIGN_INVALID"

    write_csv(output_dir / "simulation_results.csv", all_rows)
    write_json(output_dir / "pair_results.json", pair_results)

    gate_matrix = {
        "G0_SERIALIZATION": {
            "status": "PASS_SCOPED_SELF_TEST" if serialization["passed"] else "FAIL",
            "strict_legacy_test_available": serialization["legacy_test_available_in_workspace"],
            "note": "既存AISPテストはワークスペースに存在せず、明示的なマニフェストround-trip self-testを実施",
        },
        "G1_GRAPH_BALANCE": {
            "status": "PASS" if audit["all_primary_pairs_pass"] else "FAIL",
            "evidence": "selected primary graphs satisfy symmetry and doubly-stochastic checks",
        },
        "G2_MATCHED_STRUCTURE": {
            "status": "PASS" if audit["all_primary_pairs_pass"] else "FAIL",
            "evidence": "selected pairs match N, edge count, and degree sequence",
        },
        "G3_SPECTRAL_ORDERING": {
            "status": "PASS" if audit["all_primary_pairs_pass"] else "FAIL",
            "evidence": "high lambda_2 exceeds low lambda_2 in both pairs",
        },
        "G4_SPECTRAL_GAIN": {
            result["pair"]: {
                "status": "PASS" if result["gates"]["G4_SPECTRAL_GAIN"] else "FAIL",
                "mean_delta_pair": result["delta_pair"]["mean"],
                "ci95": [result["delta_pair"]["ci95_low"], result["delta_pair"]["ci95_high"]],
            }
            for result in pair_results
        },
        "G5_CENTROID_NEUTRALITY": {
            result["pair"]: {
                "status": "PASS" if result["gates"]["G5_CENTROID_NEUTRALITY"] else "FAIL",
                "centroid_ratio_high_over_low": result["centroid_ratio_high_over_low"],
                "max_abs_deviation": result["centroid_max_abs_deviation"],
            }
            for result in pair_results
        },
    }
    write_json(output_dir / "gate_verification_matrix.json", gate_matrix)

    if verdict == "PHASE2_2_R1_BALANCED_SPECTRAL_EFFECT_SUPPORTED":
        claim_firewall = FROZEN_LEDGER["frozen_claim_firewall"] + [
            "BALANCED_MATCHED_LAMBDA2_EFFECT_SUPPORTED_WITHIN_TESTED_PAIR_CLASSES",
            "EXPANDER_COUNTEREXAMPLE_HAS_A_BALANCE_DEGREE_CONFOUND_CANDIDATE",
        ]
    elif verdict == "PHASE2_2_R1_SPECTRAL_ISOLATION_FAIL":
        claim_firewall = FROZEN_LEDGER["frozen_claim_firewall"] + [
            "BALANCED_MATCHED_LAMBDA2_EFFECT_NOT_SUPPORTED_IN_THIS_AUDIT",
        ]
    elif verdict == "PHASE2_2_R1_CENTROID_CONFOUNDING":
        claim_firewall = FROZEN_LEDGER["frozen_claim_firewall"] + [
            "CENTROID_NEUTRALITY_NOT_ESTABLISHED",
            "BALANCED_MATCHED_SPECTRAL_EFFECT_NOT_INTERPRETABLE",
        ]
    else:
        claim_firewall = FROZEN_LEDGER["frozen_claim_firewall"] + [
            "PHASE2_2_R1_DESIGN_NOT_VALIDATED",
            "NO_SYNC_RESULT_INTERPRETATION_ALLOWED",
        ]

    runtime = {
        "python_version": sys.version.split()[0],
        "numpy_version": np.__version__,
        "platform": platform.platform(),
    }
    render_report(
        output_dir / "phase2_2_r1_report.md",
        design,
        serialization,
        audit,
        pair_results,
        simulation_ran=design_audit_pass,
        verdict=verdict,
        claim_firewall=claim_firewall,
        runtime=runtime,
    )

    final = {
        "verdict": verdict,
        "design_audit_pass": design_audit_pass,
        "simulation_ran": design_audit_pass,
        "output_dir": str(output_dir.resolve()),
        "g0_serialization": serialization,
        "graph_audit": audit,
        "pair_results": pair_results,
        "claim_firewall": claim_firewall,
        "gate_matrix": gate_matrix,
        "runtime": runtime,
    }
    write_json(output_dir / "final_verdict.json", final)
    return final


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("phase2_2_r1_results"),
        help="directory for audit tables, raw results, and report",
    )
    args = parser.parse_args()
    final = execute(args.output_dir)
    print(json.dumps({
        "verdict": final["verdict"],
        "design_audit_pass": final["design_audit_pass"],
        "simulation_ran": final["simulation_ran"],
        "output_dir": final["output_dir"],
    }, indent=2))


if __name__ == "__main__":
    main()
