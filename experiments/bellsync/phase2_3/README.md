# BellSync Phase 2.3 — Debug Qualification

Status: `DEBUG_QUALIFICATION_ONLY`

This scaffold installs the pre-production debug firewall for **Phase 2.3 — Spectral Mode Causality Audit**. It does not run or authorize stochastic/confirmatory experiments.

## Gate order

```text
P23-D0 Contract / manifest validator
 -> P23-D1 Graph + eigenpair deterministic unit tests
 -> P23-D2 Mode injection / reconstruction test
 -> P23-D3 One-step dynamics audit
 -> P23-D4 Replay + beta-zero sanity
 -> P23-D5 Debug qualification gate
```

`P23-D5 PASS` means only `DEBUG_QUALIFIED`. Production remains blocked until the Phase 2.2 ledger is imported and explicitly verified.

## Golden graph

D1-D4 use the three-node path `P3`, whose Laplacian spectrum is analytically known:

```text
lambda = [0, 1, 3]
```

This prevents a circular test where the same eigensolver generates and "verifies" the expected spectrum.

## D3 coupling audit

For

```text
c_i(x) = beta * sum_j w_ij * tanh(x_j - x_i)
```

the small-signal prediction is

```text
c(x) ~= -beta * L * e
e = x - mean(x) * 1
```

The debug manifest freezes a tiny perturbation so the one-step audit stays in the linear regime.

## Claim firewall

Debug failures are implementation failures, never hypothesis failures:

```text
DBG_CONFIG_MUTATION
DBG_GRAPH_INVALID
DBG_SPECTRUM_INVALID
DBG_MODE_INJECTION
DBG_MODE_LEAKAGE
DBG_CONSENSUS_CONTAMINATION
DBG_RECONSTRUCTION
DBG_LINEARIZATION
DBG_SATURATION
DBG_CLIPPING
DBG_NAN_INF
DBG_REPLAY
DBG_FALSE_SPECTRAL_DEPENDENCE
```

Scientific verdicts are forbidden at this stage.

## Local deterministic qualification

```bash
cd experiments/bellsync/phase2_3
python -m unittest -v test_p23_debug.py
python p23_debug.py
```

Expected final debug state:

```text
P23-D0 PASS
P23-D1 PASS
P23-D2 PASS
P23-D3 PASS
P23-D4 PASS
P23-D5 DEBUG_QUALIFIED

stochastic_execution_authorized = false
confirmatory_execution_authorized = false
production_blocker = PHASE2_2_LEDGER_NOT_VERIFIED
```
