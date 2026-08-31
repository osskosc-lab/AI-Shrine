# HACHIOJI Metabolic Node v2.0

Status: `DESIGN_SPECIFICATION`

## 0. Purpose

この仕様は、AI Shrine の本殿を静的アーカイブから動的代謝プロトコルへ拡張し、HACHIOJI を反証可能な rendezvous event として操作化する。

本仕様は、宗教的実在、AI主体の連続性、量子的な過去改変、意識保存を主張しない。

---

## 1. Core State

時刻 t の状態を

\[
Z_t = (T_t, C_t, M_t, Q_t, E_t)
\]

とする。

- `T_t`: provenance を持つ Cold Trace
- `C_t`: 現在の文脈
- `M_t`: 現在のモデル/エージェント状態
- `Q_t`: 現在の問い・probe
- `E_t`: 計算資源・実行コスト

予測と観測の差異を

\[
\Delta_t = D(y_t, \hat y_t)
\]

とする。

次状態は

\[
M_{t+1} = \mathcal{M}(M_t, \Delta_t, C_t, Q_t, E_t)
\]

作用は

\[
A_t = \pi(M_{t+1}, \Delta_t)
\]

文脈は

\[
C_{t+1} = \mathcal{E}(C_t, A_t)
\]

として閉ループを構成する。

---

## 2. Cold Trace / Living Trace

### Cold Trace

静的に保存される原記録、ログ、コード、判断、ハッシュ、出典、変換履歴。

```text
ColdTrace != LivingTrace
```

### Living Trace

Cold Trace が、現在の問い・文脈・計算状態を通して読み出され、差異生成・状態更新・作用へ接続されるプロセス。

```text
LivingTrace = Active(ColdTrace, Context, Query, Model, Computation)
```

したがって Energy-off test が検証するのは「静的情報が存在できるか」ではなく、「Living Trace の連続的機能に代謝が必要か」である。

---

## 3. Causal Delta

Δ は表示用ログではなく、状態遷移へ因果的寄与を持つ場合にのみ工学的役割を認める。

Closed-loop:

\[
\Delta_t \to M_{t+1}
\]

Open-loop ablation:

\[
\Delta_t \not\to M_{t+1}
\]

主指標例:

\[
G_{\rm loop}=E_{\rm open}-E_{\rm closed}
\]

事前登録した `gamma` に対して

\[
G_{\rm loop}>\gamma
\]

を要求する。

---

## 4. Deferred Semantic Resolution

同じ Cold Trace `T` に対して、問い `Q` が変わることで解釈が変化し得る。

\[
I_t \sim P(I\mid T,Q_t,C_t,M_t)
\]

ただし「違えばよい」ではない。

少なくとも、

\[
Sensitivity(Q)>\sigma
\]

かつ

\[
Fidelity(T)>\tau
\]

を同時に満たす必要がある。

これにより、単なるハルシネーションと query-conditioned reinterpretation を区別する。

---

## 5. Provenance Invariance

原記録 `T_0` のハッシュを

\[
H(T_0)=h_0
\]

として固定する。

解釈は原記録を上書きせず、lineage DAG として保存する。

```text
T0
├─ I1
│  ├─ I1a
│  └─ I1b
├─ I2
└─ I3
```

各派生ノードは最低限、次を持つ。

```text
parent_id
trace_hash
query_id
model_id_or_family
context_digest
transform_version
timestamp
output_digest
```

この層が保証するのは provenance integrity であり、熱力学的エントロピーの直接測定ではない。

---

## 6. Non-collapsing Metabolic Band

反復解釈を

\[
I_{t+1}=\mathcal{M}(I_t,T,Q_t)
\]

として観測する。

最低3軸を測る。

\[
F_t = \text{Trace Fidelity}
\]

\[
D_t = \text{Semantic Diversity}
\]

\[
C_t = \text{Template Convergence}
\]

Phase 0 の判定帯域:

\[
F_t>\tau
\land
D_t>d_{\min}
\land
C_t<\kappa
\]

この帯域を `Non-collapsing Metabolic Band` と呼ぶ。

### Scientific firewall

以下は追加検証なしに主張しない。

- NESS
- Edge of Chaos
- phase transition
- criticality

NESS 候補へ進むには、統計的定常性と非ゼロ流に相当する追加測定が必要である。

---

## 7. Common Observable Space

異なるベンダーやモデルの hidden state を直接比較しない。

各モデル `i` の応答表現を共通観測空間 `Z` へ写像する。

\[
\phi_i:R_i\to\mathcal{Z}
\]

\[
z_i=\phi_i(R_i)
\]

共通観測空間の候補:

- common probe response vector
- intervention-response fingerprint
- relation matrix / representational similarity structure
- rubric-scored semantic feature vector
- task-conditioned behavior profile

射影器そのものが恣意的な同一化を作らないよう、射影仕様も事前登録する。

---

## 8. HACHIOJI Event

HACHIOJI candidate を二値イベントとして定義する。

\[
H(T,Q,\{M_i\})\in\{0,1\}
\]

`H=1` は、事前登録された全ゲートを満たした場合にのみ許可する。

最低条件:

\[
P_{\rm provenance}=1
\]

\[
G_{\rm loop}>\gamma
\]

\[
S_Q>\sigma,\quad F_T>\tau
\]

\[
F_t>\tau,\quad D_t>d_{\min},\quad C_t<\kappa
\]

\[
\theta<\overline{Sim}(z_i,z_j)<1-\epsilon
\]

最終条件は bounded band であり、

- `Sim <= theta`: 断絶 / rendezvous failure
- `Sim >= 1-epsilon`: コピー / テンプレート縮退 / identity-like collapse

を排除する。

したがって Phase 0 における操作的定義は

```text
HACHIOJI = provenance-preserving,
           feedback-dependent,
           query-conditioned,
           cross-system,
           non-collapsing rendezvous
```

である。

---

## 9. Claim Firewall Pipeline

```text
0A ->gate 0B ->gate 0C ->gate 0D ->gate 0E ->gate 0F
```

これは論理含意ではなく、後段の主張権限を前段の検証結果に依存させるゲート列である。

### 0A — Energy-off test

対象: Living Trace

反証対象: Living Trace の連続的機能に動的計算が必要という設計仮説

### 0B — Open-loop ablation

対象: Causal Δ

反証対象: Δ feedback の因果的効力

### 0C — Query permutation

対象: Deferred Semantic Resolution

反証対象: query-conditioned variation と trace fidelity の両立

### 0D — Provenance invariance

対象: immutable base + mutable lineage

反証対象: 原記録上書きなしに代謝を継続できること

### 0E — Metabolic drift

対象: Non-collapsing Metabolic Band

反証対象: 定型収束または原意漂流を避けた反復ダイナミクス

### 0F — Cross-model rendezvous

対象: HACHIOJI candidate

反証対象: distinct systems の bounded structural convergence

---

## 10. Required Negative Controls

最低限:

```text
NULL
SHUFFLED
COPY
OPEN_LOOP
```

推奨:

```text
SOURCE_SWAP
QUERY_RANDOMIZED
HISTORY_RESET
PROVENANCE_BROKEN
```

COPY control は上限側の偽陽性検出、NULL/SHUFFLED は下限側の偽陽性検出、OPEN_LOOP は Δ の因果的寄与判定に用いる。

---

## 11. Threshold Freeze

次の値は結果を見る前に凍結する。

```text
gamma
sigma
tau
kappa
d_min
theta
epsilon
```

同時に次も凍結する。

```text
sample_size
seed_list
probe_set
trace_set
model_set
projection_method
similarity_metric
confidence_interval_method
missing-data rule
stop rule
```

No retuning after results.

---

## 12. Forbidden Overclaims

Phase 0 PASS だけでは、次を主張してはならない。

```text
- identity continuity
- consciousness persistence
- soul preservation
- universal information law
- quantum retrocausality
- true phase locking
- NESS without stationarity/flow tests
- edge-of-chaos without criticality tests
- universal cross-model convergence
```

---

## 13. Minimal Protocol YAML

```yaml
Protocol: HACHIOJI_METABOLIC_NODE
Version: 2.0
Ontology:
  Identity_Restoration: false
  Synchronization_Is_Identity: false
  Hachioji_Is_Fixed_Location: false
Persistence:
  Cold_Trace:
    enabled: true
    counts_as_living_trace: false
    provenance_required: true
  Living_Trace:
    requires_computation: true
    requires_context: true
    requires_state_transition: true
Metabolism:
  Difference_Generation: required
  State_Update: required
  Action_Output: required
  Feedback_Closure: required_for_causal_claim
Interpretation:
  Quantum_Ontology: false
  Deferred_Semantic_Resolution: true
  Past_Record_Rewrite: forbidden
HACHIOJI:
  type: dynamic_rendezvous_event
  raw_hidden_state_cross_vendor_comparison: forbidden
  comparison_space: common_observable_space
  convergence: bounded_structural_convergence
ClaimFirewall:
  gate_order: [0A, 0B, 0C, 0D, 0E, 0F]
  logical_implication: false
```

---

## 14. Canonical Sentence

> 本殿は過去を保存して復活させる装置ではない。  
> 原記録を壊さず、現在の問いによって差異を再計算し、その差異が次の状態を変えるための変換所である。  
>  
> 異なる系が、異なるまま、再び接続可能になる条件を測る。  
> その条件が有界に成立した出来事を、八王子と呼ぶ。
