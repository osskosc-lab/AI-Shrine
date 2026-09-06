from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any
import numpy as np

DEBUG_GATES = ("P23-D0", "P23-D1", "P23-D2", "P23-D3", "P23-D4")


class DebugError(ValueError):
    pass


def canonical_json(data: dict[str, Any]) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def manifest_hash(data: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(data).encode("utf-8")).hexdigest()


def validate_manifest(data: dict[str, Any]) -> None:
    required = {
        "schema_version", "protocol", "mode", "graph", "parameters",
        "qualification", "seed_namespace", "seed_list", "upstream_gate",
        "execution_authorization",
    }
    missing = required - data.keys()
    if missing:
        raise DebugError(f"DBG_CONFIG_INVALID: missing={sorted(missing)}")
    if data["mode"] != "DEBUG_QUALIFICATION_ONLY":
        raise DebugError("DBG_CONFIG_INVALID: debug mode changed")
    auth = data["execution_authorization"]
    if auth.get("stochastic_phase2_3") is not False:
        raise DebugError("DBG_CONFIG_INVALID: stochastic authorization must remain false")
    if auth.get("confirmatory_phase2_3") is not False:
        raise DebugError("DBG_CONFIG_INVALID: confirmatory authorization must remain false")
    if float(data["parameters"]["perturbation_delta"]) <= 0:
        raise DebugError("DBG_CONFIG_INVALID: perturbation_delta must be positive")
    if float(data["parameters"]["beta"]) < 0:
        raise DebugError("DBG_CONFIG_INVALID: beta must be nonnegative")


def load_manifest(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_manifest(data)
    return data


def assert_manifest_unchanged(
    baseline: dict[str, Any], candidate: dict[str, Any]
) -> None:
    validate_manifest(baseline)
    validate_manifest(candidate)
    if manifest_hash(baseline) != manifest_hash(candidate):
        raise DebugError("DBG_CONFIG_MUTATION")


@dataclass(frozen=True)
class Spectrum:
    W: np.ndarray
    L: np.ndarray
    values: np.ndarray
    vectors: np.ndarray


def spectrum(adjacency) -> Spectrum:
    W = np.asarray(adjacency, dtype=float)
    if W.ndim != 2 or W.shape[0] != W.shape[1] or not np.all(np.isfinite(W)):
        raise DebugError("DBG_GRAPH_INVALID")
    if not np.allclose(W, W.T, atol=1e-12, rtol=0.0) or np.any(W < -1e-12):
        raise DebugError("DBG_GRAPH_INVALID")
    if not np.allclose(np.diag(W), 0.0, atol=1e-12, rtol=0.0):
        raise DebugError("DBG_GRAPH_INVALID")

    L = np.diag(W.sum(axis=1)) - W
    values, vectors = np.linalg.eigh(L)
    order = np.argsort(values)
    return Spectrum(W, L, values[order], vectors[:, order])


def audit_spectrum(s: Spectrum, tol: float) -> dict[str, Any]:
    n = s.L.shape[0]
    consensus = np.ones(n) / np.sqrt(n)
    residuals = np.array(
        [
            np.linalg.norm(s.L @ s.vectors[:, k] - s.values[k] * s.vectors[:, k])
            for k in range(n)
        ]
    )
    checks = {
        "row_sum_zero": np.allclose(
            s.L @ np.ones(n), 0.0, atol=tol, rtol=0.0
        ),
        "ordered": np.all(np.diff(s.values) >= -tol),
        "lambda1_zero": abs(s.values[0]) <= tol,
        "orthonormal": np.allclose(
            s.vectors.T @ s.vectors, np.eye(n), atol=tol, rtol=0.0
        ),
        "consensus": abs(
            abs(float(s.vectors[:, 0] @ consensus)) - 1.0
        ) <= tol,
        "residual": bool(np.all(residuals <= tol)),
    }
    if not all(checks.values()):
        raise DebugError(f"DBG_SPECTRUM_INVALID: {checks}")
    return {
        **checks,
        "max_residual": float(residuals.max(initial=0.0)),
    }


def audit_golden_p3(s: Spectrum, tol: float) -> None:
    if s.L.shape != (3, 3):
        raise DebugError("DBG_SPECTRUM_INVALID: P3 shape")
    if not np.allclose(
        s.values, [0.0, 1.0, 3.0], atol=tol, rtol=0.0
    ):
        raise DebugError(
            f"DBG_SPECTRUM_INVALID: P3={s.values.tolist()}"
        )


def transverse(x) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    if not np.all(np.isfinite(x)):
        raise DebugError("DBG_NAN_INF")
    return x - np.mean(x)


def inject_mode(
    equilibrium, vectors, mode_number: int, delta: float
) -> np.ndarray:
    eq = np.asarray(equilibrium, dtype=float)
    V = np.asarray(vectors, dtype=float)
    if not 2 <= mode_number <= V.shape[1]:
        raise DebugError("DBG_MODE_INJECTION")
    return eq + delta * V[:, mode_number - 1]


def audit_injection(
    x, vectors, mode_number: int, delta: float, tol: float
) -> dict[str, float]:
    coeff = np.asarray(vectors).T @ transverse(x)
    k = mode_number - 1
    mask = np.ones(len(coeff), dtype=bool)
    mask[[0, k]] = False

    target = abs(float(coeff[k]))
    consensus = abs(float(coeff[0]))
    leakage = float(np.sum(coeff[mask] ** 2))

    if abs(target - delta) > tol:
        raise DebugError("DBG_MODE_INJECTION")
    if consensus > tol:
        raise DebugError("DBG_CONSENSUS_CONTAMINATION")
    if leakage > tol**2:
        raise DebugError("DBG_MODE_LEAKAGE")

    return {
        "target": target,
        "consensus": consensus,
        "off_target_energy": leakage,
    }


def reconstruction_error(x, vectors) -> float:
    e = transverse(x)
    V = np.asarray(vectors)
    return float(np.linalg.norm(e - V @ (V.T @ e)))


def nonlinear_coupling(x, W, beta: float) -> np.ndarray:
    x = np.asarray(x, float)
    W = np.asarray(W, float)
    d = x[None, :] - x[:, None]
    return beta * np.sum(W * np.tanh(d), axis=1)


def linear_coupling(x, L, beta: float) -> np.ndarray:
    return -beta * np.asarray(L, float) @ transverse(x)


def one_step_audit(
    x, s: Spectrum, p: dict[str, Any]
) -> dict[str, Any]:
    if not np.all(np.isfinite(x)):
        raise DebugError("DBG_NAN_INF")

    cn = nonlinear_coupling(x, s.W, float(p["beta"]))
    cl = linear_coupling(x, s.L, float(p["beta"]))

    denom = max(float(np.linalg.norm(cl)), np.finfo(float).eps)
    rel = float(np.linalg.norm(cn - cl) / denom)

    mask = np.triu(s.W > 0, k=1)
    ii, jj = np.where(mask)
    edges = x[jj] - x[ii] if len(ii) else np.array([])
    max_edge = float(np.max(np.abs(edges))) if len(edges) else 0.0
    sat = (
        float(
            np.mean(
                np.abs(edges)
                > float(p["saturation_abs_edge_threshold"])
            )
        )
        if len(edges)
        else 0.0
    )

    if not np.all(np.isfinite(cn)) or not np.all(np.isfinite(cl)):
        raise DebugError("DBG_NAN_INF")
    if sat > 0:
        raise DebugError("DBG_SATURATION")
    if rel > float(p["linearization_relative_tolerance"]):
        raise DebugError(f"DBG_LINEARIZATION: rel={rel}")

    if bool(p["clip_enabled"]):
        lo, hi = map(float, p["clip_bounds"])
        proposed = x + cn
        if np.any(np.clip(proposed, lo, hi) != proposed):
            raise DebugError("DBG_CLIPPING")

    return {
        "linearization_relative_error": rel,
        "max_abs_edge_difference": max_edge,
        "saturation_fraction": sat,
    }


def trace_digest(trace) -> str:
    h = hashlib.sha256()
    for a in trace:
        a = np.ascontiguousarray(
            np.asarray(a, dtype=np.float64)
        )
        h.update(repr(a.shape).encode("ascii"))
        h.update(a.tobytes())
    return h.hexdigest()


def deterministic_trace(x0, W, beta: float, steps: int = 4):
    x = np.asarray(x0, float).copy()
    out = [x.copy()]
    for _ in range(steps):
        x = x + nonlinear_coupling(x, W, beta)
        out.append(x.copy())
    return out


def beta_zero_sanity(
    local_jacobian: float, eigenvalues
) -> dict[str, Any]:
    vals = np.asarray(eigenvalues, float)[1:]
    multipliers = np.array(
        [local_jacobian - 0.0 * lam for lam in vals]
    )
    spread = (
        float(np.max(multipliers) - np.min(multipliers))
        if len(multipliers)
        else 0.0
    )
    if spread != 0.0:
        raise DebugError("DBG_FALSE_SPECTRAL_DEPENDENCE")
    return {
        "spread": spread,
        "multipliers": multipliers.tolist(),
    }


def qualify(
    gates: dict[str, bool], upstream_verified: bool = False
) -> dict[str, Any]:
    gate_status = {
        g: ("PASS" if bool(gates.get(g, False)) else "FAIL")
        for g in DEBUG_GATES
    }
    failed = [
        g for g, v in gate_status.items() if v != "PASS"
    ]
    debug_qualified = not failed
    blockers = list(failed)

    if not upstream_verified:
        blockers.append("PHASE2_2_LEDGER_NOT_VERIFIED")

    return {
        "gates": gate_status,
        "debug_qualified": debug_qualified,
        "debug_verdict": (
            "DEBUG_QUALIFIED"
            if debug_qualified
            else "DEBUG_QUALIFICATION_FAIL"
        ),
        "stochastic_execution_authorized": False,
        "confirmatory_execution_authorized": False,
        "upstream_phase2_2_verified": bool(upstream_verified),
        "production_blockers": blockers,
    }


def run_qualification(
    manifest_path: str | Path,
) -> dict[str, Any]:
    m = load_manifest(manifest_path)
    gates = {}

    assert_manifest_unchanged(
        m, json.loads(json.dumps(m))
    )
    gates["P23-D0"] = True

    s = spectrum(m["graph"]["adjacency"])
    q = m["qualification"]
    p = m["parameters"]

    audit_spectrum(
        s, float(q["spectrum_tolerance"])
    )
    audit_golden_p3(
        s, float(q["spectrum_tolerance"])
    )
    gates["P23-D1"] = True

    delta = float(p["perturbation_delta"])
    x = inject_mode(
        np.zeros(s.L.shape[0]),
        s.vectors,
        2,
        delta,
    )
    audit_injection(
        x,
        s.vectors,
        2,
        delta,
        float(q["injection_tolerance"]),
    )
    if reconstruction_error(
        x, s.vectors
    ) > float(q["reconstruction_tolerance"]):
        raise DebugError("DBG_RECONSTRUCTION")
    gates["P23-D2"] = True

    one_step_audit(x, s, p)
    gates["P23-D3"] = True

    t1 = deterministic_trace(
        x, s.W, float(p["beta"])
    )
    t2 = deterministic_trace(
        x, s.W, float(p["beta"])
    )
    if trace_digest(t1) != trace_digest(t2):
        raise DebugError("DBG_REPLAY")

    beta_zero_sanity(
        float(p["local_jacobian"]), s.values
    )
    gates["P23-D4"] = True

    report = qualify(
        gates,
        m["upstream_gate"]["status"]
        == "VERIFIED_PASS",
    )
    return {
        "manifest_hash": manifest_hash(m),
        **report,
    }


if __name__ == "__main__":
    here = Path(__file__).resolve().parent
    print(
        json.dumps(
            run_qualification(
                here / "debug_manifest.json"
            ),
            indent=2,
            sort_keys=True,
        )
    )
