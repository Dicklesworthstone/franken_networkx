# LEDGER RESURRECTION — franken_networkx

Meta-Lever #1 of `PERF_CAMPAIGN_2026-07-25`, re-adjudicated 2026-07-25 under the
**six-class taxonomy adopted fleet-wide from `frankenfs/docs/LEDGER_RESURRECTION.md`**,
which is better than the one in the campaign doc and supersedes this file's first pass.

- **Auditor:** BlackThrush (cc / Lane M), 2026-07-25
- **Sources:** `docs/NEGATIVE_EVIDENCE.md` (24,261 lines), `docs/NEGATIVE_EVIDENCE_cc.md`
  (9,300), `docs/progress/perf-negative-results.md` — **1,044 entries parsed**.
- **Reproduce:** `python3 scripts/perf_ledger_preflight.py --audit`

## 1. Method

Every `##` section across the three ledgers was parsed and its verdict classified; only
rejection-verdict rows were audited. SURVEY / FRONTIER / routing rows are measurements,
not rejected levers, and are excluded.

**The regex screen is triage, not a verdict.** The queue in §3 and every row in §4 were
read in full and adjudicated by hand; §6 is the mechanical screen output.

### Verdict taxonomy (frankenfs, adopted verbatim)

| Class | Meaning | Sound? |
|---|---|---|
| `VALID-PROFILE` | Rejected before any source edit, on a named profile frame with non-zero self-time and a computed Amdahl ceiling. | yes |
| `VALID-MECHANISM` | No A/A null, but refuted on a *counted* mechanism — instructions/cycles/syscalls/allocations/faults unchanged. A null control cannot change "no work was removed". | yes |
| `VALID-AB` | A/B run with a recorded A/A null; the claimed effect sits inside it. | yes |
| `VOID-CV` | An A/B ran and was killed **only** by a `cv < 5%` gate — the gate campaign §2.3 proves is unreachable on this hardware. | no |
| `VOID-ZEROSELF` | The target frame had ~0% self-time in the profile the bench actually exercised. | no |
| `VOID-NONULL` | An A/B ran, was rejected on a near-1.0 wall ratio, and recorded **no** A/A null and no counted mechanism. Cannot distinguish lever from harness. | no |

`VALID-MECHANISM` cuts **both ways** — it rescues rows from being wrongly voided. Applying
it honestly is what moved this repo's headline number (see §2).

## 2. Counts

| Metric | Count |
|---|---:|
| Ledger entries parsed | 1,044 |
| **Rejection rows — audited** | **159** |
| VALID-AB | 14 |
| VALID-MECHANISM | 25 |
| VALID-PROFILE | 1 |
| **VOID-NONULL** | **112** |
| **VOID-CV** | **4** |
| **VOID-ZEROSELF** | **3** |
| **VOID-ISA** | **0** (hand-adjudicated — see §4) |
| **VOID total** | **119 / 159 = 74.8%** |
| Rows carrying a binary sha256 | 14 / 159 = 8.8% |

### Correction to this repo's previously reported figure

My first pass reported **91% VOID** using the campaign doc's criteria, and that number
reached the fleet scoreboard. It is **too high**. The campaign criteria void a row for
lacking a null control full stop; the six-class taxonomy first asks whether the row was
refuted on a *counted mechanism*, which a null control cannot overturn. Applying
`VALID-MECHANISM` honestly rescues **25 rows**, and the corrected figure is
**74.8%**. The in-repo tool reproduces 156 rows / 75.0% — it screens
headings only, while this audit also catches four body-declared `REJECTED MEASUREMENT`
rows; the two agree within 3 rows.

### The orchestrator's correction is confirmed here, independently

The prediction was that `cv<5%` would be the dominant void class. **It is not.**
`VOID-CV` is **4 rows**; `VOID-NONULL` is **112**. franken_networkx and frankenfs
found the same shape from different corpora (frankenfs: 4 vs 214).

**Read the void rate honestly.** 119 void rows are *not* 119 buried wins. VOID-NONULL
overwhelmingly means "the row measured ~1.0x and never wrote down what ~1.0x means on
that bench" — most of those levers really are dead; the class exists because the row
cannot *prove* it. The actionable yield is a small head, and it is ranked in §3.

## 3. Rehabilitation queue and re-run yield

Ranked by the campaign's rule (profile self-time of the target frame). Self-time is
unrecorded for 145 of 159 rows — which is itself a void reason — so where it is
absent the ranking proxy is the magnitude of the discarded effect on a frame still
present on today's measured surface.

| # | original row | ledger claim | re-measured on HEAD | null CI | outcome |
|---|---|---:|---:|---|---|
| V1 | `2026-06-27 subgraph(view) 0.5x view-machinery-bound` | 0.50x | **3.5719x** (DECIDABLE) | [0.9512,1.0061] | **RE-WON** |
| V2 | `2026-07-01 node_link_data 0.70x materialization FLOOR` | 0.70x | **0.8623x** (DECIDABLE) | [0.9963,1.0151] | recovered — 'floor' refuted |
| V3 | `2026-07-02 dense DiGraph.edges() (reverted, bench rejection)` | 0.60x | **0.5850x** (DECIDABLE) | [0.9940,1.0110] | CONFIRMED loss |
| V3b | `2026-07-02 dense DiGraph.edges() — same row, data=True shape` | 0.75x | **1.6195x** (DECIDABLE) | [0.9919,1.0602] | **RE-WON** |
| V4 | `2026-06-27 RA/AA link-pred 0.59x neighbors-materialization` | 0.59x | **0.9709x** (DECIDABLE) | [0.9954,1.0048] | recovered to ~parity |
| V4b | `2026-06-27 RA/AA link-pred 0.59x neighbors-materialization` | 0.59x | **0.9647x** (DECIDABLE) | [0.9941,1.0051] | recovered to ~parity |
| V5 | `2026-06-29 MG/MDG induced subgraph().copy() NO-SHIP` | n/a | **0.6915x** (DECIDABLE) | [0.9770,1.0111] | CONFIRMED loss |
**Yield: 7 re-run, 2 re-won, 3 recovered to near parity, 2 confirmed still open.** The two
confirmed rows are now the only *evidence-backed* entries of the seven, and each carries a
retry predicate in `docs/progress/perf-negative-results.md`.

Note V3/V3b: **one ledger row covered two different result shapes.** The no-data shape is
still 0.585x while the `data=True` shape is a 1.62x win. A row cannot carry two shapes.

### Already-resurrected before this audit, and the proof the method pays

Three 2026-07-10 rows were rejected **solely because `cv` exceeded 5%**, each with complete
provenance otherwise (ELF sha256, same worker, interleaved pairs, byte-exact parity, and
80-99% self-time verified for BOTH arms): **1.7884x**, **1.3043x**, **1.3011x**. The third
**was later shipped anyway** — `5abbfd8a4` *"perf(dijkstra): reuse persistent multigraph
node ids"* — by someone re-deriving it from scratch. A cv-gated rejection buried a real,
landable win and cost the re-derivation.

This repo also ran a *partial* integrity audit on **2026-07-10**
(`NEGATIVE_EVIDENCE.md:1640`), triggered by the same frankenmermaid finding, which correctly
invalidated a "bit-parallel grid/1600 0.27x" row as narrow and self-time-less. It was never
institutionalized — which is exactly the decay this audit is meant to stop (§5).

## 4. VOID-ISA — hand-adjudicated, and the count is ZERO

**Added after the orchestrator lifted the fleet ISA constraint** (`ovh-b`, the only rch
worker without avx2+fma, removed from the `rust` tag). A rejection is VOID-ISA when the
lever's mechanism was vectorization-shaped AND the measurement ran on a binary that could
not emit AVX2. frankenfs warns the class is small and specific and that inflating it is
the failure mode; **for franken_networkx it is empty.** All 10 regex candidates were read:

| Entry | Hand verdict |
|---|---|
| `NEGATIVE_EVIDENCE_cc.md:9167` — AVX2 dense-linalg (`br-r37-c1-2zn1u`) | **NOT VOID-ISA — this row already tested v3.** Both arms ran on a pinned AVX2 worker (`hz2`) with `cfg!(target_feature)` execution proof; it measured 1.415x/1.229x and rejected on dilution + shipping cost. Reclassified by hand from the screen's `VOID-NONULL` to **`VALID-PROFILE`**: the effect is nowhere near 1.0 and the row computes an explicit Amdahl dilution argument. |
| `NEGATIVE_EVIDENCE.md:1612` — `+native` popcount 3.17x / rotate 2.08x ALU loops, **closeness bit-parallel kernel 0.98x** | **NOT void.** The real kernel was measured, not just the microbench. Confirmed independently below. |
| `NEGATIVE_EVIDENCE.md:1640` — bit-parallel grid/1600 integrity audit | Not a lever rejection; it is an audit row that voids a *different* row. Excluded. |
| `NEGATIVE_EVIDENCE_cc.md:423` — closeness per-source CSR fallback | **NOT VOID-ISA.** Mechanism is CSR-vs-String rows, not SIMD, and it carries a null. |
| 6 further regex hits (MultiDiGraph ctor stages, MultiGraph selfloop int cache) | Regex false positives — no vectorization-shaped mechanism. |

### The re-decision was measured, not asserted

A whole-binary A/B was run per campaign §2.6 (full row in
`docs/progress/perf-negative-results.md`): two release cdylibs from one pinned source state,
**ELF sha differing** (`ba240617…` vs `c0b97361…`), and instruction-level proof that codegen
changed — base `ymm=5109, popcnt=0` vs v3 `ymm=66376, popcnt=49`. **Nothing was decidable**:
the base-vs-base A/A null spans 0.86x-1.77x, so process-level whole-binary A/B cannot resolve
effects of this size on this host. The closeness result (1.0240 inside a 1.0861 null) is
**consistent with the prior 0.98x finding** — the popcount kernels do not visibly move even
with `popcnt` going 0 -> 49 instructions emitted.

### Where this repo DIVERGES from the fleet-wide recommendation

frankenfs correctly concludes "benchmark at v3, because that is what `build-perf.sh` ships".
**franken_networkx ships an abi3 wheel to arbitrary user CPUs.** A v3 benchmark binary would
measure something we do not ship and would *overstate* what users get. Here v3 is a
**shipping** question (runtime dispatch / wheel variants), not a benchmarking one.
**Do not adopt `RUSTFLAGS=-C target-cpu=x86-64-v3` for franken_networkx benchmarks.**

## 5. Institutionalization — because ledger integrity DECAYS

The fleet data is unambiguous: the repo that audited once and then *mechanically enforced*
the check sits at **1.7% VOID**; repos that audited once and banked the wins sit at
**25-91%**. This repo's own 2026-07-10 partial audit (§3) proves the point locally — it was
correct, and it decayed because nothing enforced it.

Landed with this audit:

* **`scripts/perf_ledger_preflight.py`** — three modes, frankensqlite's exit-2-means-BLOCKED
  convention:
  * `--check [REF]` — every rejection row added since REF must carry an A/A null **or** a
    counted mechanism. Exit 2 otherwise.
  * `--prior-art TERMS` — greps all three ledgers before a lever is proposed and exits 2 if a
    prior REJECT matches, enforcing the campaign's HARD GATE. If the matching row is `VOID-*`,
    the rejection is not evidence and may be re-run — the new row must say so and cite it.
  * `--audit` — re-classifies every rejection row and prints the void rate. **A rising void
    rate is how decay is detected.** Run it periodically.
* **`tests/python/test_perf_ledger_gate.py`** — wires `--check` into the test suite, so a
  rejection row recording neither a null nor a counted mechanism **fails the suite**. That is
  the difference between discouraged and impossible.

## 6. Full audit table

`VOID-*` rows are not evidence. `sha?` is whether the row records the sha256 of the binary
that ran — 8.8% do, which is why so many rows cannot be re-attached to a build.

| # | source:line | date | entry | claimed | null | self-time | sha? | class |
|---|---|---|---|---:|---|---|---|---|
| 1 | `NEGATIVE_EVIDENCE.md:5` | 2026-07-16 | 2026-07-16 BlackThrush NO-SHIP: pre-size durability envelope JSON — 0.9985x (`br-r37-c1-04z53.9177`) | 0.9985x | recorded | **none** | no | VALID-MECHANISM |
| 2 | `NEGATIVE_EVIDENCE.md:251` | 2026-07-16 | 2026-07-16 BlackThrush NO-SHIP: index self-loop k-out reinforcement — 0.9889x (`br-r37-c1-3uuu8`) | 0.9889x | recorded | **none** | no | VALID-MECHANISM |
| 3 | `NEGATIVE_EVIDENCE.md:390` | 2026-07-16 | 2026-07-16 BlackThrush NO-SHIP: cache CGSE random-edge labels — 1.0278x, 7/15 (`br-r37-c1-ppmfy`) | 1.0278x | recorded | **none** | no | VALID-MECHANISM |
| 4 | `NEGATIVE_EVIDENCE.md:485` | 2026-07-16 | 2026-07-16 BlackThrush NO-SHIP: versioned-ledger linear merge is below its null (`br-r37-c1-gx0fd`) | — | recorded | **none** | no | VALID-AB |
| 5 | `NEGATIVE_EVIDENCE.md:1021` | 2026-07-14 | 2026-07-14 RusticHollow NO-SHIP: `min_weight_matching` in-place candidate transform is inside the null floor (`br-r37-c1-pic0x`) | — | 1.0518x | **none** | no | VALID-MECHANISM |
| 6 | `NEGATIVE_EVIDENCE.md:1121` | 2026-07-10 | 2026-07-10 codex REJECT: `connected_components` Vec FIFO is bit-identical but slower on both median self-time gates | — | **none** | recorded | no | **VOID-NONULL** |
| 7 | `NEGATIVE_EVIDENCE.md:1244` | 2026-07-10 | 2026-07-10 cod_nx REJECTED MEASUREMENT: corrected ORIG reproduced 1.788x but cold-worker drift failed CV (`br-r37-c1-04z53.9171`) | 1.7880x | **none** | recorded | yes | **VOID-NONULL** |
| 8 | `NEGATIVE_EVIDENCE.md:1256` | 2026-07-10 | 2026-07-10 cod_nx REJECTED MEASUREMENT: corrected long-warm retry hit a contended worker (`br-r37-c1-04z53.9171`) | — | **none** | recorded | yes | **VOID-CV** |
| 9 | `NEGATIVE_EVIDENCE.md:1268` | 2026-07-10 | 2026-07-10 cod_nx REJECTED MEASUREMENT: external NetworkX control was outlier-dominated (`br-r37-c1-04z53.9171`) | — | **none** | recorded | yes | **VOID-NONULL** |
| 10 | `NEGATIVE_EVIDENCE.md:1309` | 2026-07-10 | 2026-07-10 cod_nx REJECTED MEASUREMENT: longer linear sampling replicated 1.3043x but amplified shared-host CV (`br-r37-c1-gtty9`) | 1.3043x | **none** | recorded | yes | VALID-MECHANISM |
| 11 | `NEGATIVE_EVIDENCE.md:1323` | 2026-07-10 | 2026-07-10 cod_nx REJECTED MEASUREMENT: persistent MultiGraph dense node IDs were 1.3011x faster, but both paired CVs missed 5% (`br-r37-... | 1.3011x | **none** | 11.1% | yes | **VOID-CV** |
| 12 | `NEGATIVE_EVIDENCE.md:1345` | 2026-07-10 | 2026-07-10 cod_nx LEDGER-INTEGRITY CORRECTION: the StackCanon REJECT itself is INVALID — its timed `Graph` path never called the `MultiGr... | — | **none** | 0.1% | yes | **VOID-ZEROSELF** |
| 13 | `NEGATIVE_EVIDENCE.md:1449` | 2026-07-10 | 2026-07-10 cod_nx MEDIAN/NULL RE-DECISION: StackCanon is VOID, not a REJECT (`br-r37-c1-04z53.9173`) | — | recorded | recorded | yes | **VOID-ZEROSELF** |
| 14 | `NEGATIVE_EVIDENCE.md:1640` | 2026-07-10 | 2026-07-10 cc LEDGER-INTEGRITY AUDIT: the "batch-parallel bit-parallel grid/1600 0.27x" reject is NOT evidence against chunked-parallel b... | 0.2700x | **none** | recorded | no | **VOID-ZEROSELF** |
| 15 | `NEGATIVE_EVIDENCE.md:1755` | 2026-07-10 | 2026-07-10 cod_nx MEASUREMENT REJECT: bidirectional-only guard isolation is stable, but one 400-call NetworkX control missed CV (`br-r37-... | — | **none** | **none** | yes | **VOID-NONULL** |
| 16 | `NEGATIVE_EVIDENCE.md:1779` | 2026-07-10 | 2026-07-10 cod_nx SOURCE REJECT (PY BINDING, exact string-key weighted MultiGraph): positive 13.10-17.23x measurement had an over-broad s... | 17.2300x | **none** | 0.1% | yes | VALID-MECHANISM |
| 17 | `NEGATIVE_EVIDENCE.md:1848` | 2026-07-10 | 2026-07-10 cod_nx MEASUREMENT REJECT: 400-call pinned MultiGraph bidirectional A/B moved the noise to the candidate shortest-path row (`b... | — | **none** | **none** | yes | **VOID-NONULL** |
| 18 | `NEGATIVE_EVIDENCE.md:1870` | 2026-07-10 | 2026-07-10 cod_nx MEASUREMENT REJECT: final-source pinned 200-call MultiGraph bidirectional A/B missed the `<5%` CV gate in one NetworkX ... | — | **none** | **none** | yes | **VOID-CV** |
| 19 | `NEGATIVE_EVIDENCE.md:1894` | 2026-07-10 | 2026-07-10 cod_nx MEASUREMENT REJECT: unpinned `hz1` MultiGraph bidirectional A/B did not meet the `<5%` CV gate (`br-r37-c1-04z53.9170`) | — | **none** | **none** | yes | **VOID-CV** |
| 20 | `NEGATIVE_EVIDENCE.md:2459` | 2026-07-08 | 2026-07-08 CyanGrove NO-SHIP: `get_edge_attributes(Graph)` cache-local projection lost vs LEGACY ORIGINAL; `DiGraph` row already wins | — | **none** | **none** | no | **VOID-NONULL** |
| 21 | `NEGATIVE_EVIDENCE.md:3157` | 2026-07-04 | 2026-07-04 CopperCliff NO-SHIP: weighted directed target shortest_path_length reverse-view route is 0.096x vs NetworkX | 0.0960x | **none** | **none** | no | **VOID-NONULL** |
| 22 | `NEGATIVE_EVIDENCE.md:3901` | 2026-07-04 | 2026-07-04 CopperCliff NO-SHIP: MultiDiGraph single_source_shortest_path depth-filled emitter regressed 0.867x -> 0.531x | 0.5310x | **none** | **none** | no | **VOID-NONULL** |
| 23 | `NEGATIVE_EVIDENCE.md:4893` | 2026-07-03 | 2026-07-03 CopperCliff RE-CONFIRM NO-SHIP (independent repro): steiner_tree de-delegation is parity-blocked AND not faster | — | **none** | **none** | no | **VOID-NONULL** |
| 24 | `NEGATIVE_EVIDENCE.md:5389` | 2026-07-02 | 2026-07-02 CopperCliff NO-SHIP (reverted, FLOOR closed): dense DiGraph.edges() — nx's directed generator is near-optimal; eager reaches o... | 0.7500x | **none** | **none** | no | **VOID-NONULL** |
| 25 | `NEGATIVE_EVIDENCE.md:5412` | 2026-07-02 | 2026-07-02 CopperCliff NO-SHIP (reverted, bench rejection): dense DiGraph.edges() 0.60x — gap is OutEdgeView, not DiEdgeView/contains_key | 0.6000x | **none** | **none** | no | **VOID-NONULL** |
| 26 | `NEGATIVE_EVIDENCE.md:5473` | 2026-07-02 | 2026-07-02 CopperCliff SURFACE + NO-SHIP: greedy_color(smallest_last) is a conversion FLOOR; filtered-view adjacency() fast-row reverted ... | — | **none** | **none** | no | **VOID-NONULL** |
| 27 | `NEGATIVE_EVIDENCE.md:5868` | 2026-07-02 | 2026-07-02 CopperCliff NO-SHIP (reverted, bench rejection): simple-DiGraph degree(weight) store twins — eager mirror means NOT strict wor... | — | **none** | **none** | no | **VOID-NONULL** |
| 28 | `NEGATIVE_EVIDENCE.md:6097` | 2026-07-02 | 2026-07-02 CopperCliff SURFACE (AUTHORITATIVE cargo bench): head2head 20/24 workloads WIN; the 4 residual gaps are ALL documented floor/N... | — | **none** | **none** | no | **VOID-NONULL** |
| 29 | `NEGATIVE_EVIDENCE.md:6412` | 2026-07-01 | 2026-07-01 CopperCliff NO-SHIP: node_link_data 0.70x vs nx is the materialization floor (native binding 0.90-0.95x vs the comprehension —... | 0.9500x | **none** | **none** | no | **VOID-NONULL** |
| 30 | `NEGATIVE_EVIDENCE.md:6509` | 2026-06-29 | 2026-06-29 CopperCliff NO-SHIP: DiGraph weighted degree(weight) store accumulator — ~0 gain, materialization floor (`br-r37-c1-dgwdegs`) | — | **none** | **none** | no | VALID-MECHANISM |
| 31 | `NEGATIVE_EVIDENCE.md:6538` | 2026-06-29 | 2026-06-29 CopperCliff NO-SHIP: MG/MDG induced subgraph().copy() parent.edges() shortcut — nx induced-view REORDERS edges (`br-r37-c1-mgs... | — | **none** | **none** | no | **VOID-NONULL** |
| 32 | `NEGATIVE_EVIDENCE.md:6814` | 2026-06-28 | 2026-06-28 BlackThrush MultiDiGraph in_edges data-key CSR predecessor scan - NO-SHIP (`cod-a`) | — | **none** | **none** | no | **VOID-NONULL** |
| 33 | `NEGATIVE_EVIDENCE.md:6875` | 2026-06-28 | 2026-06-28 BlackThrush MultiDiGraph weighted in-degree one-pass store scan - NO-SHIP (`cod-b`) | — | **none** | **none** | no | **VOID-NONULL** |
| 34 | `NEGATIVE_EVIDENCE.md:6941` | 2026-06-28 | 2026-06-28 BlackThrush MultiGraph selfloop heterogenous tuple constructor - NO-SHIP (`cod-b`) | — | **none** | **none** | no | **VOID-NONULL** |
| 35 | `NEGATIVE_EVIDENCE.md:6990` | 2026-06-28 | 2026-06-28 BlackThrush MultiDiGraph weighted degree tuple cache - NO-SHIP (`cod-a`) | — | **none** | **none** | no | **VOID-NONULL** |
| 36 | `NEGATIVE_EVIDENCE.md:7057` | 2026-06-27 | 2026-06-27 BlackThrush MultiGraph selfloop scalar-only borrowed-node scan - NO-SHIP (`cod-b`) | — | **none** | **none** | no | **VOID-NONULL** |
| 37 | `NEGATIVE_EVIDENCE.md:7122` | 2026-06-28 | 2026-06-28 BlackThrush MultiGraph selfloop borrowed-bucket fast path - NO-SHIP (`cod-a`) | — | **none** | **none** | no | VALID-MECHANISM |
| 38 | `NEGATIVE_EVIDENCE.md:7252` | 2026-06-27 | 2026-06-27 BlackThrush MultiDiGraph in_edges data-key batch view constructor - NO-SHIP (`cod-a`) | — | **none** | **none** | no | **VOID-NONULL** |
| 39 | `NEGATIVE_EVIDENCE.md:7370` | 2026-06-27 | 2026-06-27 BlackThrush directed degree generator-delegation bypass - NO-SHIP (`cod-b`) | — | **none** | **none** | no | **VOID-NONULL** |
| 40 | `NEGATIVE_EVIDENCE.md:7483` | 2026-06-27 | 2026-06-27 BlackThrush MultiDiGraph weighted degree values-only probe - NO-SHIP (`cod-a`) | — | **none** | **none** | no | **VOID-NONULL** |
| 41 | `NEGATIVE_EVIDENCE.md:8291` | 2026-06-21 | 2026-06-21 Cod-B `ubizp` MultiGraph SSSP Parent-Copy No-Ship (`br-r37-c1-04z53`, cod-b) | — | **none** | **none** | no | **VOID-NONULL** |
| 42 | `NEGATIVE_EVIDENCE.md:8589` | 2026-06-21 | 2026-06-21 Cod-A `non_edges` Exact-Int Lazy Iterator No-Ship (`br-r37-c1-04z53`, cod-a) | — | **none** | **none** | no | **VOID-NONULL** |
| 43 | `NEGATIVE_EVIDENCE.md:8641` | 2026-06-21 | 2026-06-21 Cod-B Native MultiDiGraph Compose No-Ship (`br-r37-c1-04z53`, cod-b) | — | **none** | **none** | no | **VOID-NONULL** |
| 44 | `NEGATIVE_EVIDENCE.md:8706` | 2026-06-21 | 2026-06-21 Cod-B Public Gauntlet + `non_edges` Set-Pop No-Ship (`br-r37-c1-04z53`, cod-b) | — | **none** | **none** | no | **VOID-NONULL** |
| 45 | `NEGATIVE_EVIDENCE.md:8861` | 2026-06-21 | 2026-06-21 Tree Submodule Spanning-Tree Route Rejection (`br-r37-c1-04z53`, cod-b) | — | **none** | **none** | no | **VOID-NONULL** |
| 46 | `NEGATIVE_EVIDENCE.md:9279` | 2026-06-20 | 2026-06-20 MultiDiGraph CSR Row-Streaming Boundary Reject (`br-r37-c1-04z53`, cod-a) | — | **none** | **none** | no | **VOID-NONULL** |
| 47 | `NEGATIVE_EVIDENCE.md:9345` | 2026-06-20 | 2026-06-20 MultiDiGraph CSR Boundary Snapshot Reject (`br-r37-c1-04z53`, cod-b) | — | **none** | **none** | no | **VOID-NONULL** |
| 48 | `NEGATIVE_EVIDENCE.md:9426` | 2026-06-20 | 2026-06-20 MultiDiGraph Precise Dirty-Key Sparse Reject (`br-r37-c1-04z53`, cod-b) | — | **none** | **none** | no | **VOID-NONULL** |
| 49 | `NEGATIVE_EVIDENCE.md:9491` | 2026-06-20 | 2026-06-20 MultiDiGraph Dirty Sparse Boundary Borrowed-Index Reject (`br-r37-c1-kqh2u`) | — | **none** | **none** | no | **VOID-NONULL** |
| 50 | `NEGATIVE_EVIDENCE.md:9576` | 2026-06-20 | 2026-06-20 Default-Order Matrix Export + Dijkstra Emitter No-Ships (`br-r37-c1-04z53`) | — | **none** | **none** | no | **VOID-NONULL** |
| 51 | `NEGATIVE_EVIDENCE.md:10451` | 2026-06-20 | 2026-06-20 Max-Weight Matching Native Tie-Break No-Ship | — | **none** | **none** | no | **VOID-NONULL** |
| 52 | `NEGATIVE_EVIDENCE.md:10621` | 2026-06-20 | 2026-06-20 `volume(G, S)` native-binding routing rejected (`br-r37-c1-volnative`, BlackThrush) | — | **none** | **none** | no | **VOID-NONULL** |
| 53 | `NEGATIVE_EVIDENCE.md:10732` | 2026-06-20 | 2026-06-20 `within_inter_cluster` bulk-community pre-fill REVERTED (net regression) (`br-r37-c1-wicbulk`, BlackThrush) | — | **none** | **none** | no | **VOID-NONULL** |
| 54 | `NEGATIVE_EVIDENCE.md:12916` | 2026-06-23 | 2026-06-23 BlackThrush DiGraph `edges(nbunch, data="w")` guarded-drain no-ship (`br-r37-c1-04z53.9162`, cod-b) | — | **none** | **none** | no | **VOID-NONULL** |
| 55 | `NEGATIVE_EVIDENCE.md:13034` | 2026-06-22 | 2026-06-22 BlackThrush stale MultiGraph connectivity and reverted micro-levers (`br-r37-c1-04z53.9164`, cod-a) | — | **none** | **none** | no | **VOID-NONULL** |
| 56 | `NEGATIVE_EVIDENCE.md:13326` | 2026-06-24 | 2026-06-24 BlackThrush/CopperCliff adjacency outer-dict cache - no-ship after remote rerun | — | **none** | **none** | no | **VOID-NONULL** |
| 57 | `NEGATIVE_EVIDENCE.md:13452` | 2026-06-24 | 2026-06-24 BlackThrush MultiDiGraph full weighted in/out degree - no-ship | — | **none** | **none** | no | **VOID-NONULL** |
| 58 | `NEGATIVE_EVIDENCE.md:13573` | 2026-06-25 | 2026-06-25 CopperCliff MultiDiGraph weighted degree - index-native accumulator - NO-SHIP (br-r37-c1-eilce) | — | **none** | **none** | no | **VOID-NONULL** |
| 59 | `NEGATIVE_EVIDENCE.md:13650` | 2026-06-25 | 2026-06-25 CopperCliff MultiDiGraph in_edges(data=attr) edge_key removal - NO-SHIP (br-r37-c1-eilce family) | — | **none** | **none** | no | **VOID-NONULL** |
| 60 | `NEGATIVE_EVIDENCE.md:13757` | 2026-06-25 | 2026-06-25 BlackThrush Graph.to_directed scalar-attr lazy-mirror attempt - NO-SHIP | — | **none** | **none** | no | **VOID-NONULL** |
| 61 | `NEGATIVE_EVIDENCE.md:13793` | 2026-06-25 | 2026-06-25 BlackThrush MultiGraph selfloop list-iterator lever - NO-SHIP | — | **none** | **none** | no | **VOID-NONULL** |
| 62 | `NEGATIVE_EVIDENCE.md:13843` | 2026-06-25 | 2026-06-25 BlackThrush MultiDiGraph weighted-degree edge-order accumulator - NO-SHIP | — | **none** | **none** | no | **VOID-NONULL** |
| 63 | `NEGATIVE_EVIDENCE.md:13882` | 2026-06-25 | 2026-06-25 BlackThrush core-laggard display-key probes - NO-SHIP | — | **none** | **none** | no | **VOID-NONULL** |
| 64 | `NEGATIVE_EVIDENCE.md:13915` | 2026-06-25 | 2026-06-25 BlackThrush MultiGraph selfloop attr tuple cache recheck - NO-SHIP | — | **none** | **none** | no | **VOID-NONULL** |
| 65 | `NEGATIVE_EVIDENCE.md:14015` | 2026-06-25 | 2026-06-25 BlackThrush MultiGraph.clear_edges adjacency-spine rebuild - NO-SHIP | — | **none** | **none** | no | VALID-MECHANISM |
| 66 | `NEGATIVE_EVIDENCE.md:14051` | 2026-06-25 | 2026-06-25 BlackThrush MultiGraph.selfloop_edges list-iterator handoff - REJECT | — | **none** | **none** | no | **VOID-NONULL** |
| 67 | `NEGATIVE_EVIDENCE.md:14077` | 2026-06-26 | 2026-06-26 BlackThrush MultiDiGraph weighted in/out degree count zip - NO-SHIP | — | **none** | **none** | no | **VOID-NONULL** |
| 68 | `NEGATIVE_EVIDENCE.md:14170` | 2026-06-25 | 2026-06-25 BlackThrush MultiDiGraph.in_edges data-key borrowed stream - REJECT | — | **none** | **none** | no | **VOID-NONULL** |
| 69 | `NEGATIVE_EVIDENCE.md:14211` | 2026-06-26 | 2026-06-26 BlackThrush MultiGraph.add_edge sparse attr mirror for clear_edges - REJECT | — | **none** | **none** | no | **VOID-NONULL** |
| 70 | `NEGATIVE_EVIDENCE.md:14251` | 2026-06-26 | 2026-06-26 BlackThrush MultiDiGraph.in_edges data-key clean cache - REJECT | — | **none** | **none** | no | **VOID-NONULL** |
| 71 | `NEGATIVE_EVIDENCE.md:14290` | 2026-06-26 | 2026-06-26 SilverStone MultiDiGraph weighted in-degree clean result cache - REJECT | — | **none** | **none** | no | **VOID-NONULL** |
| 72 | `NEGATIVE_EVIDENCE.md:14370` | 2026-06-26 | 2026-06-26 BlackThrush MultiGraph selfloop clean-int mirror bypass - REJECT | — | **none** | **none** | no | **VOID-NONULL** |
| 73 | `NEGATIVE_EVIDENCE.md:14424` | 2026-06-26 | 2026-06-26 BlackThrush MultiGraph.clear_edges wholesale mirror-map replace - REJECT | — | **none** | **none** | no | **VOID-NONULL** |
| 74 | `NEGATIVE_EVIDENCE.md:14472` | 2026-06-26 | 2026-06-26 BlackThrush weighted multi_source_dijkstra projection-order de-gate - REJECT | — | **none** | **none** | no | **VOID-NONULL** |
| 75 | `NEGATIVE_EVIDENCE.md:14579` | 2026-06-27 | 2026-06-27 BlackThrush MultiDiGraph weighted-degree cached node-key pairs - REVERTED | — | **none** | **none** | no | VALID-MECHANISM |
| 76 | `NEGATIVE_EVIDENCE.md:14717` | 2026-06-27 | 2026-06-27 BlackThrush MultiDiGraph weighted in-degree iterator materializer - NO-SHIP | — | **none** | **none** | no | VALID-MECHANISM |
| 77 | `NEGATIVE_EVIDENCE.md:14791` | 2026-06-27 | 2026-06-27 BlackThrush MultiDiGraph weighted in-degree lazy native iterator - NO-SHIP | — | **none** | **none** | no | **VOID-NONULL** |
| 78 | `NEGATIVE_EVIDENCE.md:14923` | 2026-06-27 | 2026-06-27 BlackThrush MultiGraph selfloop small-int object cache - NO-SHIP | — | **none** | **none** | no | **VOID-NONULL** |
| 79 | `NEGATIVE_EVIDENCE.md:14983` | 2026-06-27 | 2026-06-27 BlackThrush MultiDiGraph weighted in-degree edge-stream accumulator - NO-SHIP | — | **none** | **none** | no | **VOID-NONULL** |
| 80 | `NEGATIVE_EVIDENCE.md:15033` | 2026-06-27 | 2026-06-27 BlackThrush MultiDiGraph `in_edges(keys, data=<attr>)` default-key emit - NO-SHIP | — | **none** | **none** | no | **VOID-NONULL** |
| 81 | `NEGATIVE_EVIDENCE.md:15097` | 2026-06-27 | 2026-06-27 CopperCliff to_directed/to_undirected single-attr AttrMap-clone - NO-SHIP | — | **none** | **none** | no | VALID-MECHANISM |
| 82 | `NEGATIVE_EVIDENCE.md:15339` | 2026-06-28 | 2026-06-28 CopperCliff multi_source_dijkstra_path_length 0.20x — NO-SHIP (length-only de-delegation is value-exact but ORDER-blocked by t... | 86.0000x | **none** | **none** | no | **VOID-NONULL** |
| 83 | `NEGATIVE_EVIDENCE.md:16038` | 2026-06-28 | 2026-06-28 CopperCliff NO-SHIP: MultiGraph size(weight) native scalar — substrate-bound below nx (REVERTED, 2 approaches tried) | — | **none** | **none** | no | **VOID-NONULL** |
| 84 | `NEGATIVE_EVIDENCE.md:16191` | 2026-06-28 | 2026-06-28 CopperCliff NO-SHIP (lever DISPROVEN by implementation): native CSR MG dijkstra ALSO loses — the floor is the MultiGraph's STR... | — | **none** | **none** | no | **VOID-NONULL** |
| 85 | `NEGATIVE_EVIDENCE.md:16325` | 2026-06-28 | 2026-06-28 CopperCliff NO-SHIP: multi_source_dijkstra_path_length on a MultiGraph 0.088x — projection + gate-overhead bound (~0-gain to fix) | 0.0880x | **none** | **none** | no | **VOID-NONULL** |
| 86 | `NEGATIVE_EVIDENCE.md:16393` | 2026-06-28 | 2026-06-28 CopperCliff NO-SHIP: steiner_tree 0.556x — in-process mehlhorn is WORSE (0.346x); needs a native kernel | 0.3460x | **none** | **none** | no | **VOID-NONULL** |
| 87 | `NEGATIVE_EVIDENCE.md:16724` | 2026-06-29 | 2026-06-29 CopperCliff NO-SHIP (REVERTED): MG edges(data=<attr>) store-read routing — neutral/regression | — | **none** | **none** | no | **VOID-NONULL** |
| 88 | `NEGATIVE_EVIDENCE.md:16985` | 2026-06-29 | 2026-06-29 CopperCliff EDGE-batch corruption: same class as node fix, but dispatch tangled — attempt REVERTED | — | **none** | **none** | no | **VOID-NONULL** |
| 89 | `NEGATIVE_EVIDENCE.md:17170` | 2026-06-29 | 2026-06-29 BlackThrush NO-SHIP: MDG in_edges(keys,data=<attr>) py_node_key hoist — ~0 gain | — | recorded | **none** | no | VALID-AB |
| 90 | `NEGATIVE_EVIDENCE.md:17232` | 2026-06-29 | 2026-06-29 BlackThrush NO-SHIP: edge_py_keys default-int gate is NOT the in_edges(keys,data) floor | — | recorded | **none** | no | VALID-AB |
| 91 | `NEGATIVE_EVIDENCE.md:17600` | 2026-06-29 | 2026-06-29 BlackThrush NO-SHIP: PyGraph degree(nbunch, weight) int-accumulator twin — store-read floor, trades workloads | — | **none** | **none** | no | **VOID-NONULL** |
| 92 | `NEGATIVE_EVIDENCE.md:17842` | 2026-06-29 | 2026-06-29 BlackThrush NO-SHIP (cargo-bench-confirmed): clear_edges 0.351x is per-edge CONSTRUCTION fragmentation, not a clear_edges bug | 0.3510x | **none** | **none** | no | **VOID-NONULL** |
| 93 | `NEGATIVE_EVIDENCE.md:18721` | 2026-07-10 | 2026-07-10 cod_nx REJECT (PY WRAPPER, string-key weighted MultiGraph `shortest_path(source,target,weight)`): in-process multigraph bidire... | — | **none** | 0.1% | no | **VOID-NONULL** |
| 94 | `NEGATIVE_EVIDENCE.md:19523` | 2026-07-11 | 2026-07-11 WhiteJaguar REJECT (FLOW, `max_flow`): compact sorted residual rows — 5.10% worse same-worker median (`br-r37-c1-fz193`) | — | **none** | **none** | yes | VALID-MECHANISM |
| 95 | `NEGATIVE_EVIDENCE.md:20262` | 2026-07-13 | 2026-07-13 CrimsonHorizon REJECT (`MultiDiGraph(<true iterator>)`): broad drain wins plain/attrs but regresses keyed 23.7% (`br-r37-c1-2f... | — | 1.0085x | **none** | no | VALID-AB |
| 96 | `NEGATIVE_EVIDENCE.md:20919` | 2026-07-14 | 2026-07-14 RusticHollow NO-SHIP (`core_number`): edgeless peeling bypass is inside the null-control floor (`br-r37-c1-dy8w1`) | — | recorded | **none** | no | VALID-AB |
| 97 | `NEGATIVE_EVIDENCE.md:21085` | 2026-07-14 | 2026-07-14 RusticHollow NO-SHIP (`dag_longest_path_length`): direct scalar DP stays below the keep floor (`br-r37-c1-qwzl2`) | — | recorded | **none** | no | VALID-AB |
| 98 | `NEGATIVE_EVIDENCE.md:22022` | 2026-07-14 | 2026-07-14 GrayCitadel INVALID / NO-SHIP (`build_crosswalk_report`): borrowed fixture-ID indexes did not reach timed path (`br-r37-c1-wrq... | — | **none** | **none** | no | VALID-MECHANISM |
| 99 | `NEGATIVE_EVIDENCE.md:22065` | 2026-07-14 | 2026-07-14 GrayCitadel INVALID / NO-SHIP (`dominance_frontiers`): index-space propagation did not reach timed path (`br-r37-c1-nfe62`) | — | **none** | **none** | no | **VOID-NONULL** |
| 100 | `NEGATIVE_EVIDENCE.md:22428` | 2026-07-14 | 2026-07-14 GrayCitadel NO-SHIP (`generate_sidecar_for_file`): fused packet serialization metadata pass — **1.0226x inside null noise** (`... | 1.0226x | recorded | **none** | yes | VALID-MECHANISM |
| 101 | `NEGATIVE_EVIDENCE.md:23861` | 2026-07-24 | 2026-07-24 StormyForge REJECT (`MultiDiGraph(iterator)` scalar attrs): adopt the private snapshot as the live mirror — **1.0280x** (`br-r... | 1.0280x | 1.0033x | **none** | no | VALID-MECHANISM |
| 102 | `NEGATIVE_EVIDENCE.md:23905` | 2026-07-24 | 2026-07-24 StormyForge REJECT (`MultiDiGraph(iterator)` scalar attrs): defer normalized fallback tuples — **1.0105x** (`br-r37-c1-pab55`) | 1.0105x | 0.9986x | **none** | no | VALID-MECHANISM |
| 103 | `NEGATIVE_EVIDENCE.md:24112` | 2026-07-24 | 2026-07-24 StormyForge REJECT (`MultiDiGraph(iterator)` keyed scalar attrs): fused validation + native decode — **1.0202x** (`br-r37-c1-4... | 1.0202x | 1.0056x | **none** | no | VALID-MECHANISM |
| 104 | `NEGATIVE_EVIDENCE.md:24161` | 2026-07-24 | 2026-07-24 StormyForge REJECT (`MultiDiGraph(iterator)` keyed scalar attrs): exact tuple-iterator stage pre-sizing — **1.0144x** (`br-r37... | 1.0144x | 1.0009x | **none** | no | VALID-MECHANISM |
| 105 | `NEGATIVE_EVIDENCE.md:24210` | 2026-07-24 | 2026-07-24 StormyForge REJECT (`MultiDiGraph(iterator)` keyed scalar attrs): raw exact-string stage lookup — **0.9897x** (`br-r37-c1-04z5... | 0.9897x | 1.0065x | **none** | no | VALID-MECHANISM |
| 106 | `NEGATIVE_EVIDENCE_cc.md:423` | 2026-07-12 | REJECT (cod, 2026-07-12): declined `closeness_centrality` per-source CSR fallback does not clear its null (br-r37-c1-yy0rp) | — | 1.0852x | **none** | no | VALID-MECHANISM |
| 107 | `NEGATIVE_EVIDENCE_cc.md:688` | 2026-07-12 | REJECT + SWEEP (cc, 2026-07-12): `ego_graph` BFS below-null; neighbour-walk sub-family exhausted | — | recorded | **none** | no | VALID-AB |
| 108 | `NEGATIVE_EVIDENCE_cc.md:1233` | 2026-07-12 | REJECT (cc, 2026-07-12): `quotient_graph` batch — BELOW NULL (br-r37-c1-quotientbatch) | — | 1.1103x | **none** | no | VALID-MECHANISM |
| 109 | `NEGATIVE_EVIDENCE_cc.md:1903` | 2026-07-11 | SURFACE (cc, 2026-07-11): `barabasi_albert_graph` batch-by-index = BELOW-NOISE (1.04x) — BA is SAMPLING-bound, not insertion-bound → not ... | 1.0400x | 0.9967x | **none** | no | VALID-AB |
| 110 | `NEGATIVE_EVIDENCE_cc.md:3307` | 2026-07-10 | REJECT (cc, 2026-07-10): MultiGraph `degree(nbunch, weight=)` per-edge `edge_key` alloc removal — byte-identical but **below the noise fl... | — | **none** | **none** | no | **VOID-NONULL** |
| 111 | `NEGATIVE_EVIDENCE_cc.md:3431` | 2026-07-10 | REJECT (cc, 2026-07-10): the different-primitive SoA / cache-friendly integer-adjacency for MG target Dijkstra is **0.7152x** (0/121 wins... | 0.7152x | 0.9987x | **none** | no | VALID-AB |
| 112 | `NEGATIVE_EVIDENCE_cc.md:3494` | 2026-07-10 | REJECT (cc, 2026-07-10): scratch-reuse for the MG target Dijkstra is BELOW the null floor — measured 1.0053x median, inside NULL [0.836,1... | 1.0053x | 0.9976x | **none** | no | VALID-MECHANISM |
| 113 | `NEGATIVE_EVIDENCE_cc.md:4563` | 2026-06-28 | DOMAIN MAP + 2 NO-SHIPs + BLOCKER (cc, 2026-06-28): dijkstra/bellman_ford family & flow/matching/operators/traversal sweeps — all wins ex... | — | **none** | **none** | no | **VOID-NONULL** |
| 114 | `NEGATIVE_EVIDENCE_cc.md:4805` | 2026-06-27 | NO-SHIP (cc, 2026-06-27): MDG in_edges(keys,data=key) single-pass bucket walk + node-obj hoist — REGRESSION 0.263x->0.190x | 0.1900x | **none** | **none** | no | **VOID-NONULL** |
| 115 | `NEGATIVE_EVIDENCE_cc.md:5009` | — | read_edgelist 0.40x: parse_edgelist NOT a drop-in (REVERTED) | 0.4000x | **none** | **none** | no | **VOID-NONULL** |
| 116 | `NEGATIVE_EVIDENCE_cc.md:5629` | — | SCAFFOLD CAUGHT A REGRESSION: qbj9u directed effective_size kernel diverged (REVERTED) | — | **none** | **none** | no | **VOID-NONULL** |
| 117 | `NEGATIVE_EVIDENCE_cc.md:5690` | 2026-06-24 | NO-SHIP (CORRECTED): adjacency() outer-dict cache — FALSIFIED by durable per-crate Criterion bench (2026-06-24, CopperCliff) | — | **none** | **none** | no | **VOID-NONULL** |
| 118 | `NEGATIVE_EVIDENCE_cc.md:5778` | 2026-06-25 | 2026-06-25 CopperCliff to_directed scalar deepcopy-skip - NO-SHIP ~0-gain (br-r37-c1-eilce family) | — | **none** | **none** | no | **VOID-NONULL** |
| 119 | `NEGATIVE_EVIDENCE_cc.md:5808` | 2026-06-25 | 2026-06-25 CopperCliff set_edge/set_node_attributes broadcast - NO-SHIP ~0-gain (eager-mirror floor) | — | **none** | **none** | no | **VOID-NONULL** |
| 120 | `NEGATIVE_EVIDENCE_cc.md:5873` | 2026-06-25 | 2026-06-25 CopperCliff BUILDFIX main was non-compiling + dijkstra sync-dirty NO-SHIP | — | **none** | **none** | no | **VOID-NONULL** |
| 121 | `NEGATIVE_EVIDENCE_cc.md:6055` | 2026-06-25 | 2026-06-25 CopperCliff products/bipartite/operators/DAG sweep — REJECTS (modest delegation-tax gaps) | — | **none** | **none** | no | **VOID-NONULL** |
| 122 | `NEGATIVE_EVIDENCE_cc.md:6071` | 2026-06-25 | 2026-06-25 CopperCliff I/O sweep — parse_adjlist/adjacency_data REJECT (add_edges_from substrate floor) | — | **none** | **none** | no | **VOID-NONULL** |
| 123 | `NEGATIVE_EVIDENCE_cc.md:6110` | 2026-06-25 | 2026-06-25 CopperCliff REJECT: set-order-locked delegated algos are STRUCTURALLY unwinnable vs nx | — | **none** | **none** | no | **VOID-NONULL** |
| 124 | `NEGATIVE_EVIDENCE_cc.md:6197` | 2026-06-25 | 2026-06-25 CopperCliff REJECT: structural/copy/conversion primitive sweep — losses are native+floored | — | **none** | **none** | no | **VOID-NONULL** |
| 125 | `NEGATIVE_EVIDENCE_cc.md:6324` | 2026-06-25 | 2026-06-25 CopperCliff REJECT: approximation.steiner_tree 0.409x — conversion-tax-bound, de-delegation parity-risky | 0.4090x | **none** | **none** | no | **VOID-NONULL** |
| 126 | `NEGATIVE_EVIDENCE_cc.md:6539` | 2026-06-25 | 2026-06-25 CopperCliff construction-builder sweep — binomial_tree REJECT, rest wins/floor-bound | — | **none** | **none** | no | **VOID-NONULL** |
| 127 | `NEGATIVE_EVIDENCE_cc.md:6584` | 2026-06-25 | 2026-06-25 CopperCliff property-check + LCA/cuts/matching sweep — wins; min_weight_matching REJECT | — | **none** | **none** | no | **VOID-NONULL** |
| 128 | `NEGATIVE_EVIDENCE_cc.md:6599` | 2026-06-25 | 2026-06-25 CopperCliff chordal/dominating/eulerian sweep — wins; connected_dominating_set REJECT | — | **none** | **none** | no | **VOID-NONULL** |
| 129 | `NEGATIVE_EVIDENCE_cc.md:6737` | 2026-06-26 | 2026-06-26 CopperCliff re-examined order-locked rejects vs their TEST CONTRACTS (after find_asteroidal win) | — | **none** | **none** | no | **VOID-NONULL** |
| 130 | `NEGATIVE_EVIDENCE_cc.md:6766` | 2026-06-26 | 2026-06-26 CopperCliff flow sweep — capacity_scaling/max_flow_min_cost WINS; min_cost_flow family REJECT (convert+delegate bound) | — | **none** | **none** | no | **VOID-NONULL** |
| 131 | `NEGATIVE_EVIDENCE_cc.md:6824` | 2026-06-26 | 2026-06-26 CopperCliff removal/matrix-centrality sweep — WINS; communicability_betweenness O(n^4)-hard REJECT | — | **none** | **none** | no | **VOID-NONULL** |
| 132 | `NEGATIVE_EVIDENCE_cc.md:6840` | 2026-06-26 | 2026-06-26 CopperCliff spectral sweep — fiedler_vector win CONFIRMED at scale; spectral_ordering sign-locked REJECT | — | **none** | **none** | no | **VOID-NONULL** |
| 133 | `NEGATIVE_EVIDENCE_cc.md:6961` | 2026-06-26 | 2026-06-26 CopperCliff group_betweenness Puzis port — WIP/NO-SHIP-yet (Rust bug, Python ref VERIFIED) | — | **none** | **none** | no | **VOID-NONULL** |
| 134 | `NEGATIVE_EVIDENCE_cc.md:6981` | 2026-06-26 | 2026-06-26 CopperCliff group_betweenness(>=3) DEFINITIVE REJECT — nx's Puzis algorithm is SET-ORDER-DEPENDENT | — | **none** | **none** | no | **VOID-NONULL** |
| 135 | `NEGATIVE_EVIDENCE_cc.md:7027` | 2026-06-26 | 2026-06-26 CopperCliff steiner_tree — fast-Kou REJECT (weight-locked to nx mehlhorn default); LCA/dominating wins | — | **none** | **none** | no | **VOID-NONULL** |
| 136 | `NEGATIVE_EVIDENCE_cc.md:7205` | 2026-06-26 | 2026-06-26 CopperCliff multi_source via k-single_source workaround — REJECT (paths diverge + slower); fully reserved-gated | — | **none** | **none** | no | **VOID-NONULL** |
| 137 | `NEGATIVE_EVIDENCE_cc.md:7309` | 2026-06-26 | 2026-06-26 CopperCliff treewidth_min_degree convert+delegate — REJECT (decomp is adjacency-order-sensitive, breaks byte-exactness) | — | **none** | **none** | no | **VOID-NONULL** |
| 138 | `NEGATIVE_EVIDENCE_cc.md:7486` | 2026-06-26 | 2026-06-26 CopperCliff NEGATIVE: MG.size(weight) native-AttrMap read — byte-exact but perf inconsistent (REVERTED) | — | **none** | **none** | no | **VOID-NONULL** |
| 139 | `NEGATIVE_EVIDENCE_cc.md:7519` | 2026-06-26 | 2026-06-26 CopperCliff NEGATIVE #2: MG.size(weight) zero-alloc native fold — ~0-gain at bench size (REVERTED) | — | **none** | **none** | no | **VOID-NONULL** |
| 140 | `NEGATIVE_EVIDENCE_cc.md:7753` | 2026-06-27 | 2026-06-27 CopperCliff NEGATIVE: DiGraph in_edges(data=str) store-read ~0-gain (already near floor; REVERTED) | — | **none** | **none** | no | **VOID-NONULL** |
| 141 | `NEGATIVE_EVIDENCE_cc.md:7902` | 2026-06-27 | 2026-06-27 CopperCliff REVERTED a571d20d6 (degree index-native = host-noise false win) | — | **none** | **none** | no | **VOID-NONULL** |
| 142 | `NEGATIVE_EVIDENCE_cc.md:7930` | 2026-06-27 | 2026-06-27 CopperCliff RA/AA link-pred 0.59x = neighbors-materialization substrate (degree-batch REGRESSED, reverted) | 0.5900x | **none** | **none** | no | **VOID-NONULL** |
| 143 | `NEGATIVE_EVIDENCE_cc.md:7962` | 2026-06-27 | 2026-06-27 CopperCliff community link-pred (cn/ra_index/within_inter soundarajan_hopcroft) hybrid native REGRESSED, reverted | — | **none** | **none** | no | **VOID-NONULL** |
| 144 | `NEGATIVE_EVIDENCE_cc.md:8079` | 2026-06-27 | 2026-06-27 CopperCliff remove_edges_from bulk-retain = ~0-gain (REVERTED) — per-edge swap_remove+String-hash is the floor | — | **none** | **none** | no | **VOID-NONULL** |
| 145 | `NEGATIVE_EVIDENCE_cc.md:8095` | 2026-06-27 | 2026-06-27 CopperCliff FINDING: add_edges_from(dict attrs) leaves Rust store stale -> size/degree/wiener(weight) WRONG (correctness bug);... | — | **none** | **none** | no | **VOID-NONULL** |
| 146 | `NEGATIVE_EVIDENCE_cc.md:8176` | 2026-06-27 | 2026-06-27 CopperCliff subgraph(view) 0.5x view-machinery-bound (filt set-intersection marginal, reverted) + find_induced_nodes without_f... | 0.5000x | **none** | **none** | no | **VOID-NONULL** |
| 147 | `NEGATIVE_EVIDENCE_cc.md:8291` | — | Mutation-cluster residual is a PyO3 call-boundary floor — SURFACED (CopperCliff, no-ship) | — | **none** | **none** | no | **VOID-NONULL** |
| 148 | `NEGATIVE_EVIDENCE_cc.md:8581` | 2026-07-02 | 2026-07-02 CopperCliff SURFACE (architectural, NO-SHIP this pass): node removal is the storage-model wall — 0.003-0.14x, needs slotmap/de... | 0.1400x | **none** | **none** | no | **VOID-NONULL** |
| 149 | `NEGATIVE_EVIDENCE_cc.md:9101` | 2026-07-22 | 2026-07-22 SnowyBadger (cc) S8 MEASURED VERDICT: positional renumber REJECTED for the real flip — 190-203x slower than the String store o... | 203.0000x | **none** | **none** | no | **VOID-NONULL** |
| 150 | `NEGATIVE_EVIDENCE_cc.md:9167` | 2026-07-22 | 2026-07-22 SnowyBadger (cc) REJECT (br-r37-c1-2zn1u): AVX2 dense-linalg — the pure-FLOP core moves only 1.2-1.4x; below shipping threshold | — | **none** | recorded | no | VALID-PROFILE |
| 151 | `perf-negative-results.md:191` | 2026-07-23 | 2026-07-23 SnowyBadger (cc) REJECT + BLOCKER (br-r37-c1-04z53): edges(nbunch,data=True) repack removal — correct but reddens full suite v... | — | **none** | recorded | no | **VOID-NONULL** |
| 152 | `perf-negative-results.md:217` | 2026-07-23 | 2026-07-23 SnowyBadger (cc) SHIP + CORRECTION (br-r37-c1-04z53): edges(nbunch,data) repack removal — the prior REJECT was an INSTALL-STAT... | — | **none** | **none** | no | **VOID-NONULL** |
| 153 | `perf-negative-results.md:395` | 2026-07-23 | 2026-07-23 BlackThrush (cc) REJECT (br-r37-c1-thp6w): MultiGraph fresh-batch capacity-reserve does NOT move construction — String-substra... | — | 1.0000x | 8.0% | no | VALID-AB |
| 154 | `perf-negative-results.md:431` | 2026-07-24 | 2026-07-24 BlackThrush (cc) REJECT (br-r37-c1-thp6w S13): slab index-read route `edges_ordered_indices_borrowed` — O(n) slot->position bu... | — | recorded | **none** | no | VALID-AB |
| 155 | `perf-negative-results.md:622` | 2026-07-24 | 2026-07-24 StormyForge REJECT (`MultiDiGraph(iterator)` scalar attrs): private snapshot mirror transfer — **1.0280x** (`br-r37-c1-kbs9t`) | 1.0280x | 1.0033x | **none** | no | VALID-AB |
| 156 | `perf-negative-results.md:651` | 2026-07-24 | 2026-07-24 StormyForge REJECT (`MultiDiGraph(iterator)` scalar attrs): deferred normalized fallback tuples — **1.0105x** (`br-r37-c1-pab55`) | 1.0105x | 0.9986x | **none** | no | VALID-AB |
| 157 | `perf-negative-results.md:782` | 2026-07-24 | 2026-07-24 StormyForge REJECT (`MultiDiGraph(iterator)` keyed scalar attrs): fused validation + native decode — **1.0202x** (`br-r37-c1-4... | 1.0202x | 1.0101x | **none** | no | VALID-MECHANISM |
| 158 | `perf-negative-results.md:817` | 2026-07-24 | 2026-07-24 StormyForge REJECT (`MultiDiGraph(iterator)` keyed scalar attrs): exact tuple-iterator stage pre-sizing — **1.0144x** (`br-r37... | 1.0144x | 1.0060x | **none** | no | VALID-MECHANISM |
| 159 | `perf-negative-results.md:853` | 2026-07-24 | 2026-07-24 StormyForge REJECT (`MultiDiGraph(iterator)` keyed scalar attrs): raw exact-string stage lookup — **0.9897x** (`br-r37-c1-04z5... | 0.9897x | 1.0065x | **none** | no | VALID-AB |
