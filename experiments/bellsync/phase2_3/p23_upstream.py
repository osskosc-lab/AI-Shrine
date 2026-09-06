from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


EXPECTED_SEMANTIC_SHA256 = (
    "2d7a3c518fd5c8d463f58226220ccd345ba3b1a25c31cca92afb4e86c35a2c3b"
)

EXPECTED = {
    "phase2_2_frozen_verdict": "PHASE2_2_FAIL_SPECTRAL_DETERMINATION",
    "phase2_2_r1_verdict": "PHASE2_2_R1_SPECTRAL_ISOLATION_FAIL",
    "phase2_2_r1a_verdict": "RECONCILIATION_PASS",
    "delta_pair_definition": "PER_SEED_RELATIVE_REDUCTION",
    "auc_d_definition": "45_STEP_DISCRETE_SUM",
    "pair_a_delta_pair": 0.0018119107809711564,
    "pair_b_delta_pair": 0.000816775760243488,
    "numerical_reproducibility": "PASS",
    "pair_a_abs_diff": 0.0,
    "pair_b_abs_diff": 0.0,
    "provenance_consistency": "PASS",
    "p0_status": "UNBLOCKED",
}


class UpstreamError(ValueError):
    pass


def canonical_json(data: Any) -> str:
    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_ledger(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def semantic_subset(ledger: dict[str, Any]) -> dict[str, Any]:
    frozen = ledger["frozen_ledger"]
    r1a = ledger["r1a_reconciliation"]
    return {
        "phase2_2_frozen_verdict": frozen["phase2_2_verdict"],
        "phase2_2_r1_verdict": frozen["phase2_2_r1_verdict"],
        "phase2_2_r1a_verdict": r1a["verdict"],
        "delta_pair_definition": r1a["delta_pair_definition"],
        "auc_d_definition": r1a["auc_d_definition"],
        "pair_a_delta_pair": r1a["pair_a_reported"],
        "pair_b_delta_pair": r1a["pair_b_reported"],
        "numerical_reproducibility": r1a["numerical_reproducibility"],
        "pair_a_abs_diff": r1a["pair_a_abs_diff"],
        "pair_b_abs_diff": r1a["pair_b_abs_diff"],
        "provenance_consistency": r1a["provenance_consistency"],
        "p0_status": r1a["p0_status"],
    }


def semantic_evidence_hash(ledger: dict[str, Any]) -> str:
    return sha256_text(canonical_json(semantic_subset(ledger)))


def _is_sha256(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def verify_semantic_evidence(
    ledger: dict[str, Any],
) -> dict[str, Any]:
    subset = semantic_subset(ledger)
    mismatches = {
        key: {"expected": EXPECTED[key], "actual": subset.get(key)}
        for key in EXPECTED
        if subset.get(key) != EXPECTED[key]
    }

    digest = semantic_evidence_hash(ledger)
    declared = ledger.get("semantic_evidence_sha256")

    if mismatches:
        raise UpstreamError(
            "P23_P0_SEMANTIC_MISMATCH: "
            + canonical_json(mismatches)
        )
    if digest != EXPECTED_SEMANTIC_SHA256:
        raise UpstreamError(
            "P23_P0_SEMANTIC_HASH_MISMATCH"
        )
    if declared != EXPECTED_SEMANTIC_SHA256:
        raise UpstreamError(
            "P23_P0_DECLARED_HASH_MISMATCH"
        )

    r1a = ledger["r1a_reconciliation"]
    tol = float(r1a["numerical_tolerance"])
    for label in ("pair_a", "pair_b"):
        reported = float(r1a[f"{label}_reported"])
        reproduced = float(r1a[f"{label}_reproduced"])
        abs_diff = float(r1a[f"{label}_abs_diff"])
        recomputed = abs(reported - reproduced)

        if abs(recomputed - abs_diff) > 1e-18:
            raise UpstreamError(
                f"P23_P0_DIFF_INCONSISTENT:{label}"
            )
        if abs_diff >= tol:
            raise UpstreamError(
                f"P23_P0_NUMERICAL_REPRO_FAIL:{label}"
            )

    return {
        "semantic_evidence_verified": True,
        "semantic_evidence_sha256": digest,
        "r1a_reconciliation_verified": True,
    }


def verify_r1_gate_consistency(
    ledger: dict[str, Any],
) -> dict[str, Any]:
    gates = ledger["r1_gate_matrix"]
    required_pass = [
        "G1_GRAPH_BALANCE",
        "G2_MATCHED_STRUCTURE",
        "G3_SPECTRAL_ORDERING",
        "G5_PAIR_A_3REGULAR",
        "G5_PAIR_B_4REGULAR",
    ]
    for gate in required_pass:
        if gates.get(gate) != "PASS":
            raise UpstreamError(
                f"P23_P0_R1_GATE_INCONSISTENT:{gate}"
            )

    if gates.get("G0_SERIALIZATION") != "PASS_SCOPED_SELF_TEST":
        raise UpstreamError(
            "P23_P0_R1_GATE_INCONSISTENT:G0_SERIALIZATION"
        )

    for gate in (
        "G4_PAIR_A_3REGULAR",
        "G4_PAIR_B_4REGULAR",
    ):
        if gates.get(gate) != "FAIL":
            raise UpstreamError(
                f"P23_P0_R1_GATE_INCONSISTENT:{gate}"
            )

    pair_a = ledger["r1_pairs"]["PAIR_A_3REGULAR"]
    pair_b = ledger["r1_pairs"]["PAIR_B_4REGULAR"]
    if not (
        float(pair_a["ci95_low"]) < 0.0 < float(pair_a["ci95_high"])
    ):
        raise UpstreamError(
            "P23_P0_R1_CI_INCONSISTENT:PAIR_A"
        )
    if not (
        float(pair_b["ci95_low"]) < 0.0 < float(pair_b["ci95_high"])
    ):
        raise UpstreamError(
            "P23_P0_R1_CI_INCONSISTENT:PAIR_B"
        )

    return {
        "r1_gate_consistency_verified": True,
        "r1_spectral_gain_supported": False,
    }


def verify_source_artifact_contract(
    ledger: dict[str, Any],
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    blockers: list[str] = []
    artifacts = ledger["source_artifacts"]
    root = (
        Path(repo_root)
        if repo_root is not None
        else Path(__file__).resolve().parents[3]
    )

    required = ("script", "final_verdict")
    for key in required:
        artifact = artifacts[key]
        declared = artifact.get("sha256")
        path = artifact.get("repository_path")

        if not _is_sha256(declared):
            blockers.append(
                f"SOURCE_ARTIFACT_SHA256_MISSING:{key}"
            )
        if not isinstance(path, str) or not path.strip():
            blockers.append(
                f"SOURCE_ARTIFACT_REPOSITORY_PATH_MISSING:{key}"
            )
            continue
        if not _is_sha256(declared):
            continue

        resolved = root / path
        if not resolved.is_file():
            blockers.append(
                f"SOURCE_ARTIFACT_NOT_FOUND:{key}"
            )
            continue

        actual = hashlib.sha256(resolved.read_bytes()).hexdigest()
        if actual != declared:
            blockers.append(
                f"SOURCE_ARTIFACT_HASH_MISMATCH:{key}"
            )

    return {
        "source_artifact_contract_verified": not blockers,
        "blockers": blockers,
    }


def verify_series_completion(
    ledger: dict[str, Any],
) -> dict[str, Any]:
    series = ledger["series_completion"]

    r2 = bool(series.get("r2_executed"))
    stop = bool(series.get("explicit_stop_record_present"))
    final = bool(series.get("final_series_ledger_present"))

    complete = final and (r2 or stop)
    blockers = []
    if not (r2 or stop):
        blockers.append(
            "PHASE2_2_R2_OR_STOP_RECORD_MISSING"
        )
    if not final:
        blockers.append(
            "PHASE2_2_FINAL_SERIES_LEDGER_MISSING"
        )

    return {
        "series_completion_verified": complete,
        "blockers": blockers,
    }


def evaluate_upstream(
    ledger: dict[str, Any],
) -> dict[str, Any]:
    semantic = verify_semantic_evidence(ledger)
    r1 = verify_r1_gate_consistency(ledger)
    artifacts = verify_source_artifact_contract(ledger)
    series = verify_series_completion(ledger)

    blockers = (
        artifacts["blockers"]
        + series["blockers"]
    )
    upstream_verified = (
        semantic["semantic_evidence_verified"]
        and r1["r1_gate_consistency_verified"]
        and artifacts["source_artifact_contract_verified"]
        and series["series_completion_verified"]
    )

    return {
        "gate": "P23-P0",
        "r1a_evidence_imported": True,
        **semantic,
        **r1,
        "source_artifact_contract_verified": artifacts[
            "source_artifact_contract_verified"
        ],
        "series_completion_verified": series[
            "series_completion_verified"
        ],
        "upstream_phase2_2_verified": upstream_verified,
        "upstream_gate_status": (
            "VERIFIED_PASS"
            if upstream_verified
            else "PARTIAL_PASS_BLOCKED"
        ),
        "production_blockers": blockers,
        "phase2_3_stochastic_execution_authorized": False,
        "phase2_3_confirmatory_execution_authorized": False,
    }


def run(path: str | Path) -> dict[str, Any]:
    ledger = load_ledger(path)
    return evaluate_upstream(ledger)


if __name__ == "__main__":
    here = Path(__file__).resolve().parent
    print(
        json.dumps(
            run(here / "upstream_phase2_2_ledger.json"),
            indent=2,
            sort_keys=True,
        )
    )
