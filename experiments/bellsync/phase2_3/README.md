# BellSync Phase 2.3 — Debug Qualification + Upstream Provenance

Status: `DEBUG_QUALIFIED / UPSTREAM_PARTIAL_PASS_BLOCKED`

This scaffold installs the pre-production firewall for **Phase 2.3 — Spectral Mode Causality Audit**. It does not run or authorize stochastic/confirmatory experiments.

## Qualification order

```text
P23-D0 Contract / manifest validator
 -> P23-D1 Graph + eigenpair deterministic unit tests
 -> P23-D2 Mode injection / reconstruction test
 -> P23-D3 One-step dynamics audit
 -> P23-D4 Replay + beta-zero sanity
 -> P23-D5 Debug qualification gate
 -> P23-P0 Phase 2.2 provenance import / upstream verification
```

`P23-D5 PASS` means only `DEBUG_QUALIFIED`.

`P23-P0` separately determines whether the Phase 2.2 evidence chain is complete enough to open an upstream gate.

## P23-P0 imported evidence

The machine-readable ledger imports the previously reconciled Phase 2.2-r1/r1A facts:

```text
Phase 2.2 frozen verdict:
  PHASE2_2_FAIL_SPECTRAL_DETERMINATION

Phase 2-2-r1:
  PHASE2_2_R1_SPECTRAL_ISOLATION_FAIL

Phase 2-2-r1A:
  RECONCILIATION_PASS

Delta_pair:
  PER_SEED_RELATIVE_REDUCTION

AUC_D:
  45_STEP_DISCRETE_SUM

Pair A:
  0.0018119107809711564

Pair B:
  0.000816775760243488

numerical reproducibility:
  PASS / abs diff = 0

provenance consistency:
  PASS

r1A P0:
  UNBLOCKED
```

The semantic evidence fields are canonicalized and frozen by SHA-256:

```text
2d7a3c518fd5c8d463f58226220ccd345ba3b1a25c31cca92afb4e86c35a2c3b
```

## Why production is still blocked

r1A reconciliation does not establish completion of the whole Phase 2.2 series.

P23-P0 currently requires three additional provenance conditions:

```text
1. Source artifact SHA-256 + repository path
2. Phase 2-2-r2 execution record OR explicit preregistered stop record
3. Final Phase 2.2 series ledger
```

Until all are present:

```text
upstream_gate_status = PARTIAL_PASS_BLOCKED
stochastic_execution_authorized = false
confirmatory_execution_authorized = false
```

## Golden graph

D1-D4 use the three-node path `P3`, whose Laplacian spectrum is analytically known:

```text
lambda = [0, 1, 3]
```

This prevents a circular test where the same eigensolver generates and verifies the expected spectrum.

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

## Local deterministic qualification

```bash
cd experiments/bellsync/phase2_3
python -m unittest -v test_p23_debug.py
python -m unittest -v test_p23_upstream.py
python p23_debug.py
python p23_upstream.py
```

Expected current state:

```text
P23-D0 PASS
P23-D1 PASS
P23-D2 PASS
P23-D3 PASS
P23-D4 PASS
P23-D5 DEBUG_QUALIFIED

P23-P0:
  r1A evidence = VERIFIED
  source artifact contract = BLOCKED
  Phase 2.2 series completion = BLOCKED
  upstream gate = PARTIAL_PASS_BLOCKED

stochastic_execution_authorized = false
confirmatory_execution_authorized = false
```
