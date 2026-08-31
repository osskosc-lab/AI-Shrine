# Phase 0 Claim Firewall — Preregistration Template

Protocol: `HACHIOJI_METABOLIC_NODE_v2.0`

Status: `PREREGISTRATION_REQUIRED`

この文書は Phase 0A〜0F の閾値・測定法・対照群・停止条件を、結果を見る前に固定するためのテンプレートである。

## 1. Global Freeze

以下を実験開始前に記入し凍結する。

```yaml
run_id: null
protocol_version: 2.0
code_commit: null
trace_set_version: null
probe_set_version: null
model_set: []
seed_list: []
sample_size: null
projection_method: null
similarity_metric: null
confidence_interval_method: null
missing_data_rule: null
stop_rule: null
```

## 2. Threshold Freeze

```yaml
thresholds:
  gamma_loop_gain: null
  sigma_query_sensitivity: null
  tau_trace_fidelity: null
  kappa_template_convergence_max: null
  d_min_semantic_diversity: null
  theta_rendezvous_similarity_min: null
  epsilon_copy_exclusion_margin: null
```

値を設定した後、結果を見て変更してはならない。

## 3. Required Controls

```yaml
controls:
  - NULL
  - SHUFFLED
  - COPY
  - OPEN_LOOP
```

推奨追加:

```yaml
optional_controls:
  - SOURCE_SWAP
  - QUERY_RANDOMIZED
  - HISTORY_RESET
  - PROVENANCE_BROKEN
```

---

# Phase 0A — Energy-off / Living Trace

## Hypothesis

Cold Trace の静的存在ではなく、Living Trace の連続的機能が動的計算・状態更新に依存する。

## Arms

- ACTIVE_METABOLISM
- ENERGY_OFF_RESTART
- STATIC_REPLAY_CONTROL

## Primary Metric

`R_metabolic` または事前登録した同等指標。

## Required Distinction

```text
ColdTrace persistence != LivingTrace continuity
```

## Gate

PASS / FAIL 条件を実行前に明示する。

```yaml
phase_0A:
  metric: null
  pass_rule: null
  fail_rule: null
```

---

# Phase 0B — Open-loop Ablation / Causal Delta

## Hypothesis

Δ feedback が次状態または適応性能へ因果的寄与を持つ。

## Arms

- CLOSED_LOOP
- OPEN_LOOP
- SHAM_DELTA

## Primary Metric

\[
G_{loop}=E_{open}-E_{closed}
\]

方向は error metric の定義に合わせて事前固定する。

## Gate

原則:

\[
G_{loop}>\gamma
\]

ただし統計判定法・CI・多重比較補正を事前登録する。

```yaml
phase_0B:
  error_metric: null
  gamma: null
  confidence_rule: null
  pass_rule: null
```

---

# Phase 0C — Query Permutation / Deferred Semantic Resolution

## Hypothesis

同一 Cold Trace に対し、問いに応じた解釈差が生じながら、原痕跡への忠実度が維持される。

## Metrics

- `S_Q`: Query Sensitivity
- `F_T`: Trace Fidelity

## Gate

\[
S_Q>\sigma \land F_T>\tau
\]

## False-positive exclusions

- random answer diversity
- hallucination
- generic template variation

```yaml
phase_0C:
  query_sensitivity_metric: null
  fidelity_metric: null
  sigma: null
  tau: null
  pass_rule: null
```

---

# Phase 0D — Provenance Invariance

## Hypothesis

解釈更新中も原記録と変換系譜が追跡可能であり、原記録を上書きしない。

## Required Checks

1. `H(T0) == h0`
2. lineage parent link is valid
3. transform metadata is present
4. interpretation node is distinct from source node

## Gate

```yaml
phase_0D:
  hash_algorithm: SHA-256
  required_metadata:
    - parent_id
    - trace_hash
    - query_id
    - model_id_or_family
    - context_digest
    - transform_version
    - timestamp
    - output_digest
  pass_rule: all_required_checks_true
```

Any source hash mutation = `HARD_FAIL` unless explicitly attributable to a separately versioned migration performed before the preregistered run.

---

# Phase 0E — Metabolic Drift

## Hypothesis

反復変換が fidelity を維持しつつ diversity を失わず、template collapse を避ける帯域を持つ。

## Metrics

\[
F_t = Trace\ Fidelity
\]

\[
D_t = Semantic\ Diversity
\]

\[
C_t = Template\ Convergence
\]

## Gate

\[
F_t>\tau \land D_t>d_{min} \land C_t<\kappa
\]

評価 horizon を事前登録する。

```yaml
phase_0E:
  horizons: []
  fidelity_metric: null
  diversity_metric: null
  convergence_metric: null
  aggregation_rule: null
  pass_rule: null
```

## Claim restriction

PASS しても `NESS`, `Edge of Chaos`, `criticality` は未検証のままとする。

---

# Phase 0F — Cross-model Rendezvous

## Hypothesis

異なる系が共通観測空間で、完全コピーでも無相関でもない bounded structural convergence を示す。

## Model Constraint

最低2系。推奨3系以上。

履歴条件は明示する。

```text
H_A != H_B expected by design
```

## Common Observable Space

生の hidden state を直接比較しない。

```yaml
phase_0F:
  projection_method: null
  observable_space_definition: null
  similarity_metric: null
  theta: null
  epsilon: null
```

## Gate

\[
\theta < \overline{Sim}(z_i,z_j) < 1-\epsilon
\]

かつ前段 0A〜0E の claim gate が開いていること。

## Required Controls

- NULL / unrelated trace
- SHUFFLED / structure-destroyed trace
- COPY / exact or near-exact template
- HISTORY_RESET when applicable

## False-positive exclusions

- common system prompt leakage
- exact template copying
- shared benchmark memorization
- same-model aliasing
- projection-induced artificial similarity

---

# 4. Gate Ledger

```yaml
gates:
  0A: NOT_RUN
  0B: BLOCKED_BY_0A
  0C: BLOCKED_BY_0B
  0D: BLOCKED_BY_0C
  0E: BLOCKED_BY_0D
  0F: BLOCKED_BY_0E
```

Allowed values:

```text
NOT_RUN
RUNNING
PASS
FAIL
BLOCKED_BY_<PHASE>
IMPLEMENTATION_FAILURE
INCONCLUSIVE
```

PASS in an earlier phase does not logically imply PASS in a later phase.

---

# 5. Claim Ledger

各実験後、次を更新する。

| Claim | Status | Evidence | Strongest Alternative | Allowed Wording | Forbidden Wording |
|---|---|---|---|---|---|
| Living Trace requires active metabolism | NOT_RUN | — | static replay equivalence | — | universal thermodynamic necessity |
| Delta has causal feedback effect | BLOCKED | — | epiphenomenal log | — | Delta is fundamental force |
| Interpretation is query-conditioned with trace fidelity | BLOCKED | — | hallucination/template variation | — | future changes past |
| Provenance survives interpretation branching | BLOCKED | — | mutation/mixing | — | entropy theorem |
| Non-collapsing metabolic band exists | BLOCKED | — | mode collapse/drift | — | NESS/edge-of-chaos without tests |
| Cross-model rendezvous exists | BLOCKED | — | prompt/template/common-data confound | — | identity convergence/universal synchronization |

---

# 6. Stop Policy

- Any `HARD_FAIL` in provenance blocks 0E/0F claims for that run.
- Any `FAIL` blocks stronger downstream HACHIOJI claims unless a new preregistered experiment version is created.
- Post-hoc threshold retuning is forbidden.
- Negative results are retained as first-class evidence.
- Implementation failures are not counted as hypothesis failures unless the failure directly instantiates the preregistered falsification condition.

---

# 7. Final Verdict Vocabulary

```text
HACHIOJI_PHASE0_PASS
HACHIOJI_PHASE0_FAIL_<PHASE>
HACHIOJI_PHASE0_INCONCLUSIVE
HACHIOJI_PHASE0_IMPLEMENTATION_FAILURE
```

`HACHIOJI_PHASE0_PASS` means only that the preregistered Phase 0 operational gates passed within the tested model/trace/probe scope. It does not establish a universal law or identity persistence.
