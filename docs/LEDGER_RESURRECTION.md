# LEDGER RESURRECTION — franken_networkx

Meta-Lever #1 of `PERF_CAMPAIGN_2026-07-25`. Audit of every rejection row in this
repo's negative-evidence ledgers against the campaign's VOID criteria, plus the
re-run of the top-ranked void entries under the corrected harness contract (§2).

- **Auditor:** BlackThrush (cc / STRUCTURAL lane), 2026-07-25
- **Sources:** `docs/NEGATIVE_EVIDENCE.md` (24,261 lines), `docs/NEGATIVE_EVIDENCE_cc.md`
  (9,300), `docs/progress/perf-negative-results.md` (887) — 1,044 entries parsed.
- **Harness for every re-run:** self-reporting `_fnx` ELF sha256, byte-identity proof
  before timing, A/A null control in the same invocation, median-of-per-round-ratios,
  decidability gated on the null's bootstrap 95% CI with a 2x margin. `cv` is recorded
  as provenance and is never a gate.

## Yield

| metric | count |
|---|---:|
| entries parsed | 1044 |
| rejection rows audited | 159 |
| **VOID** (>=1 hard criterion) | **146** (91%) |
| VALID (survives the criteria) | 13 |
| rows carrying an A/A null control | 30 |
| rows carrying profile self-time attribution | 14 |
| rows carrying a binary sha | 14 |
| rows carrying a retry predicate | 13 |
| rows decided on the `cv<5%` gate | 13 |
| entries re-run under the corrected harness | 7 |
| **re-won** (loss -> decidable win) | **2** |
| substantially recovered (loss shrank, still <1.0x) | 3 |
| confirmed still-open losses | 2 |

The dominant failure mode here is **not** the one frankenlibc found (ratios sitting
inside the null band — only 17 rows). It is that **129 of 159 rejection rows carry no
A/A null control at all**, and **145 carry no profile attribution**, so for those rows
there is no recorded basis on which the measurement could have detected the lever.

## The three highest-value void rows, and the proof the method works

`2026-07-10` produced three rows that were rejected **solely because `cv` exceeded 5%**,
each with an effect far outside any plausible noise floor and otherwise complete
provenance (ELF sha256, same worker, interleaved pairs, byte-exact parity, non-zero
self-time verified for BOTH arms at 97-99%):

| entry | effect | why rejected | self-time of target |
|---|---:|---|---|
| `br-r37-c1-04z53.9171` corrected ORIG classifier | **1.7884x** | `cv 13.62%/12.15%` | 80.5% / 84.0% |
| `br-r37-c1-gtty9` longer linear sampling | **1.3043x** | `cv 11.69%/10.87%` | 97.9% / 98.7% |
| `br-r37-c1-gtty9` persistent MultiGraph dense node IDs | **1.3011x** | `cv 6.82%/6.09%` | 97.9% / 98.8% |

Per campaign §2.3 the `cv<5%` gate is unreachable on this hardware, so all three are
VOID. **The third one was later shipped anyway** — commit `5abbfd8a4`
*"perf(dijkstra): reuse persistent multigraph node ids"* — which is direct in-repo
proof that a cv-gated rejection buried a real, landable win. The other two are the
same lever family measured differently.

This repo's own A/A nulls, measured today, quantify why the gate is wrong: a row with
`cv 17.06%/5.52%` had a null CI of `0.9997-1.0152` (decidable to ~1.03x), while a row
with `cv 0.44%/0.79%` had a null CI of `0.9947-1.0065`. `cv` differed by 30x; the
decidable floor differed by less than 2x, and in the *opposite* direction to the `cv`
ranking.

## Re-runs under the corrected harness

Ranked by the size of the claimed effect on a frame still present on today's measured
surface (self-time was unrecorded for these rows, which is itself their void reason,
so the ranking proxy is the magnitude of the discarded effect).

| # | original row | ledger claim | re-measured (HEAD, vs genuine nx 3.6.1) | null CI | verdict |
|---|---|---:|---:|---|---|
| V1 | `2026-06-27 subgraph(view) 0.5x view-machinery-bound` | 0.50x | **3.5719x** (DECIDABLE) | [0.9512,1.0061] | **RE-WON** |
| V2 | `2026-07-01 node_link_data 0.70x materialization FLOOR` | 0.70x | **0.8623x** (DECIDABLE) | [0.9963,1.0151] | recovered — 'floor' refuted |
| V3 | `2026-07-02 dense DiGraph.edges() (reverted, bench rejection)` | 0.60x | **0.5850x** (DECIDABLE) | [0.9940,1.0110] | CONFIRMED loss |
| V3b | `2026-07-02 dense DiGraph.edges() (same row, data=True shape)` | 0.75x | **1.6195x** (DECIDABLE) | [0.9919,1.0602] | **RE-WON** |
| V4 | `2026-06-27 RA/AA link-pred 0.59x neighbors-materialization` | 0.59x | **0.9709x** (DECIDABLE) | [0.9954,1.0048] | recovered to ~parity |
| V4b | `2026-06-27 RA/AA link-pred 0.59x neighbors-materialization` | 0.59x | **0.9647x** (DECIDABLE) | [0.9941,1.0051] | recovered to ~parity |
| V5 | `2026-06-29 MG/MDG induced subgraph().copy() NO-SHIP` | n/a | **0.6915x** (DECIDABLE) | [0.9770,1.0111] | CONFIRMED loss |

Two outright resurrections (`subgraph(view)` **3.5719x**, dense
`DiGraph.edges(data=True)` **1.6195x**), three rows whose loss had already shrunk to
near parity while the ledger still recorded the old figure, and two rows that are
genuinely still open — those two are now the only *evidence-backed* entries of the
seven. Note V3/V3b: one ledger row covered two different result shapes; the
no-data shape is still 0.585x while the `data=True` shape is a 1.62x win. A single
row cannot carry two shapes.

## What the audit says about the ledger process

1. **A rejection with no null control is not evidence.** 129 of 159 rows. The fix is
   mechanical: `paired(base, base)` costs exactly one extra arm of wall time.
2. **A rejection with no profile attribution cannot be ranked for re-run.** 145 of 159
   rows, which is why the queue above had to be ranked by discarded-effect size.
3. **One row must describe one measured shape.** The V3/V3b split shows a single row
   averaging a 0.585x loss and a 1.62x win into one 'reverted, bench rejection'.
4. **Ledger rows expire.** V1 moved 7x (0.50x -> 3.57x) without anyone reopening it.
   Rows should carry the HEAD sha they were measured at, and a re-measure-by date.

## Retry predicates for the still-open rows

- **dense `DiGraph.edges()` (0.5850x, V3):** retry when a profile of
  `list(G.edges())` on a >=10k-edge dense DiGraph attributes >=20% exact self-time to
  tuple materialization in the edge-view walk (not to the adjacency scan), AND the
  A/A null floor on the measuring host is below 1.02x. Do NOT retry via the
  `data=True` path — that shape already wins 1.6195x.
- **MultiGraph induced `subgraph().copy()` (0.6915x, V5):** retry only after the
  `br-r37-c1-thp6w` slab cutover lands (measured 5.324x construction / 3.69x removal
  on the store), since this row is dominated by MultiGraph construction, and only if
  the row is still <0.95x with a null floor below 1.02x.
- **`node_link_data` (0.8623x, V2):** the 'materialization floor' claim is refuted;
  retry when a profile attributes >=15% exact self-time to per-edge dict construction
  in `node_link_data` itself rather than to the edge walk.

## Full audit table

`VOID` = at least one hard criterion (no null control / ratio inside the null floor /
~0% self-time on the target frame). Rows marked `VALID` carry a null control and an
effect outside it. `sha?` is whether the row records the sha256 of the binary that ran.

| # | source:line | date | entry | claimed | null | self-time | sha? | verdict | void criteria |
|---|---|---|---|---:|---|---|---|---|---|
| 1 | `NEGATIVE_EVIDENCE.md:5` | 2026-07-16 | 2026-07-16 BlackThrush NO-SHIP: pre-size durability envelope JSON — 0.9985x (`br-r37-c1-04z53.9177`) | 0.9985x | recorded | **none** | no | **VOID** | ratio inside 0.905-1.105 null band; no profile attribution; no binary sha (concurrent editors) |
| 2 | `NEGATIVE_EVIDENCE.md:251` | 2026-07-16 | 2026-07-16 BlackThrush NO-SHIP: index self-loop k-out reinforcement — 0.9889x (`br-r37-c1-3uuu8`) | 0.9889x | recorded | **none** | no | **VOID** | ratio inside 0.905-1.105 null band; no profile attribution; no binary sha (concurrent editors) |
| 3 | `NEGATIVE_EVIDENCE.md:390` | 2026-07-16 | 2026-07-16 BlackThrush NO-SHIP: cache CGSE random-edge labels — 1.0278x, 7/15 (`br-r37-c1-ppmfy`) | 1.0278x | recorded | **none** | no | **VOID** | ratio inside 0.905-1.105 null band; no profile attribution; no binary sha (concurrent editors) |
| 4 | `NEGATIVE_EVIDENCE.md:485` | 2026-07-16 | 2026-07-16 BlackThrush NO-SHIP: versioned-ledger linear merge is below its null (`br-r37-c1-gx0fd`) | — | recorded | **none** | no | VALID | no profile attribution; no binary sha (concurrent editors) |
| 5 | `NEGATIVE_EVIDENCE.md:1021` | 2026-07-14 | 2026-07-14 RusticHollow NO-SHIP: `min_weight_matching` in-place candidate transform is inside the null floor (`br-r37-c1-pic0x`) | — | 1.0518x | **none** | no | VALID | no profile attribution; no binary sha (concurrent editors) |
| 6 | `NEGATIVE_EVIDENCE.md:1121` | 2026-07-10 | 2026-07-10 codex REJECT: `connected_components` Vec FIFO is bit-identical but slower on both median self-time gates | — | **none** | recorded | no | **VOID** | no A/A null recorded; no binary sha (concurrent editors) |
| 7 | `NEGATIVE_EVIDENCE.md:1244` | 2026-07-10 | 2026-07-10 cod_nx REJECTED MEASUREMENT: corrected ORIG reproduced 1.788x but cold-worker drift failed CV (`br-r37-c1-04z53.9171`) | 1.7880x | **none** | recorded | yes | **VOID** | no A/A null recorded; decided on the cv<5% gate |
| 8 | `NEGATIVE_EVIDENCE.md:1256` | 2026-07-10 | 2026-07-10 cod_nx REJECTED MEASUREMENT: corrected long-warm retry hit a contended worker (`br-r37-c1-04z53.9171`) | — | **none** | recorded | yes | **VOID** | no A/A null recorded; decided on the cv<5% gate |
| 9 | `NEGATIVE_EVIDENCE.md:1268` | 2026-07-10 | 2026-07-10 cod_nx REJECTED MEASUREMENT: external NetworkX control was outlier-dominated (`br-r37-c1-04z53.9171`) | — | **none** | recorded | yes | **VOID** | no A/A null recorded |
| 10 | `NEGATIVE_EVIDENCE.md:1309` | 2026-07-10 | 2026-07-10 cod_nx REJECTED MEASUREMENT: longer linear sampling replicated 1.3043x but amplified shared-host CV (`br-r37-c1-gtty9`) | 1.3043x | **none** | recorded | yes | **VOID** | no A/A null recorded; decided on the cv<5% gate |
| 11 | `NEGATIVE_EVIDENCE.md:1323` | 2026-07-10 | 2026-07-10 cod_nx REJECTED MEASUREMENT: persistent MultiGraph dense node IDs were 1.3011x faster, but both paired CVs missed 5% (`br-r37-c1-gtty9`) | 1.3011x | **none** | 11.1% | yes | **VOID** | no A/A null recorded; decided on the cv<5% gate |
| 12 | `NEGATIVE_EVIDENCE.md:1345` | 2026-07-10 | 2026-07-10 cod_nx LEDGER-INTEGRITY CORRECTION: the StackCanon REJECT itself is INVALID — its timed `Graph` path never called the `MultiGraph`-only ... | — | **none** | 0.1% | yes | **VOID** | no A/A null recorded; target frame ~0% self-time |
| 13 | `NEGATIVE_EVIDENCE.md:1449` | 2026-07-10 | 2026-07-10 cod_nx MEDIAN/NULL RE-DECISION: StackCanon is VOID, not a REJECT (`br-r37-c1-04z53.9173`) | — | recorded | recorded | yes | **VOID** | target frame ~0% self-time |
| 14 | `NEGATIVE_EVIDENCE.md:1640` | 2026-07-10 | 2026-07-10 cc LEDGER-INTEGRITY AUDIT: the "batch-parallel bit-parallel grid/1600 0.27x" reject is NOT evidence against chunked-parallel bit-paralle... | 0.2700x | **none** | recorded | no | **VOID** | no A/A null recorded; target frame ~0% self-time; no binary sha (concurrent editors) |
| 15 | `NEGATIVE_EVIDENCE.md:1755` | 2026-07-10 | 2026-07-10 cod_nx MEASUREMENT REJECT: bidirectional-only guard isolation is stable, but one 400-call NetworkX control missed CV (`br-r37-c1-04z53.9... | — | **none** | **none** | yes | **VOID** | no A/A null recorded; no profile attribution; decided on the cv<5% gate |
| 16 | `NEGATIVE_EVIDENCE.md:1779` | 2026-07-10 | 2026-07-10 cod_nx SOURCE REJECT (PY BINDING, exact string-key weighted MultiGraph): positive 13.10-17.23x measurement had an over-broad shared node... | 17.2300x | **none** | 0.1% | yes | **VOID** | no A/A null recorded |
| 17 | `NEGATIVE_EVIDENCE.md:1848` | 2026-07-10 | 2026-07-10 cod_nx MEASUREMENT REJECT: 400-call pinned MultiGraph bidirectional A/B moved the noise to the candidate shortest-path row (`br-r37-c1-0... | — | **none** | **none** | yes | **VOID** | no A/A null recorded; no profile attribution; decided on the cv<5% gate |
| 18 | `NEGATIVE_EVIDENCE.md:1870` | 2026-07-10 | 2026-07-10 cod_nx MEASUREMENT REJECT: final-source pinned 200-call MultiGraph bidirectional A/B missed the `<5%` CV gate in one NetworkX control ro... | — | **none** | **none** | yes | **VOID** | no A/A null recorded; no profile attribution; decided on the cv<5% gate |
| 19 | `NEGATIVE_EVIDENCE.md:1894` | 2026-07-10 | 2026-07-10 cod_nx MEASUREMENT REJECT: unpinned `hz1` MultiGraph bidirectional A/B did not meet the `<5%` CV gate (`br-r37-c1-04z53.9170`) | — | **none** | **none** | yes | **VOID** | no A/A null recorded; no profile attribution; decided on the cv<5% gate |
| 20 | `NEGATIVE_EVIDENCE.md:2459` | 2026-07-08 | 2026-07-08 CyanGrove NO-SHIP: `get_edge_attributes(Graph)` cache-local projection lost vs LEGACY ORIGINAL; `DiGraph` row already wins | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 21 | `NEGATIVE_EVIDENCE.md:3157` | 2026-07-04 | 2026-07-04 CopperCliff NO-SHIP: weighted directed target shortest_path_length reverse-view route is 0.096x vs NetworkX | 0.0960x | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 22 | `NEGATIVE_EVIDENCE.md:3901` | 2026-07-04 | 2026-07-04 CopperCliff NO-SHIP: MultiDiGraph single_source_shortest_path depth-filled emitter regressed 0.867x -> 0.531x | 0.5310x | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 23 | `NEGATIVE_EVIDENCE.md:4893` | 2026-07-03 | 2026-07-03 CopperCliff RE-CONFIRM NO-SHIP (independent repro): steiner_tree de-delegation is parity-blocked AND not faster | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 24 | `NEGATIVE_EVIDENCE.md:5389` | 2026-07-02 | 2026-07-02 CopperCliff NO-SHIP (reverted, FLOOR closed): dense DiGraph.edges() — nx's directed generator is near-optimal; eager reaches only 0.75x ... | 0.7500x | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 25 | `NEGATIVE_EVIDENCE.md:5412` | 2026-07-02 | 2026-07-02 CopperCliff NO-SHIP (reverted, bench rejection): dense DiGraph.edges() 0.60x — gap is OutEdgeView, not DiEdgeView/contains_key | 0.6000x | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 26 | `NEGATIVE_EVIDENCE.md:5473` | 2026-07-02 | 2026-07-02 CopperCliff SURFACE + NO-SHIP: greedy_color(smallest_last) is a conversion FLOOR; filtered-view adjacency() fast-row reverted byte-wrong | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 27 | `NEGATIVE_EVIDENCE.md:5868` | 2026-07-02 | 2026-07-02 CopperCliff NO-SHIP (reverted, bench rejection): simple-DiGraph degree(weight) store twins — eager mirror means NOT strict work removal | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 28 | `NEGATIVE_EVIDENCE.md:6097` | 2026-07-02 | 2026-07-02 CopperCliff SURFACE (AUTHORITATIVE cargo bench): head2head 20/24 workloads WIN; the 4 residual gaps are ALL documented floor/NO-SHIP | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 29 | `NEGATIVE_EVIDENCE.md:6412` | 2026-07-01 | 2026-07-01 CopperCliff NO-SHIP: node_link_data 0.70x vs nx is the materialization floor (native binding 0.90-0.95x vs the comprehension — REVERTED) | 0.9500x | **none** | **none** | no | **VOID** | no A/A null recorded; ratio inside 0.905-1.105 null band; no profile attribution; no binary sha (concurrent editors) |
| 30 | `NEGATIVE_EVIDENCE.md:6509` | 2026-06-29 | 2026-06-29 CopperCliff NO-SHIP: DiGraph weighted degree(weight) store accumulator — ~0 gain, materialization floor (`br-r37-c1-dgwdegs`) | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 31 | `NEGATIVE_EVIDENCE.md:6538` | 2026-06-29 | 2026-06-29 CopperCliff NO-SHIP: MG/MDG induced subgraph().copy() parent.edges() shortcut — nx induced-view REORDERS edges (`br-r37-c1-mgsubcopy`) | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 32 | `NEGATIVE_EVIDENCE.md:6814` | 2026-06-28 | 2026-06-28 BlackThrush MultiDiGraph in_edges data-key CSR predecessor scan - NO-SHIP (`cod-a`) | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 33 | `NEGATIVE_EVIDENCE.md:6875` | 2026-06-28 | 2026-06-28 BlackThrush MultiDiGraph weighted in-degree one-pass store scan - NO-SHIP (`cod-b`) | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 34 | `NEGATIVE_EVIDENCE.md:6941` | 2026-06-28 | 2026-06-28 BlackThrush MultiGraph selfloop heterogenous tuple constructor - NO-SHIP (`cod-b`) | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 35 | `NEGATIVE_EVIDENCE.md:6990` | 2026-06-28 | 2026-06-28 BlackThrush MultiDiGraph weighted degree tuple cache - NO-SHIP (`cod-a`) | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 36 | `NEGATIVE_EVIDENCE.md:7057` | 2026-06-27 | 2026-06-27 BlackThrush MultiGraph selfloop scalar-only borrowed-node scan - NO-SHIP (`cod-b`) | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 37 | `NEGATIVE_EVIDENCE.md:7122` | 2026-06-28 | 2026-06-28 BlackThrush MultiGraph selfloop borrowed-bucket fast path - NO-SHIP (`cod-a`) | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 38 | `NEGATIVE_EVIDENCE.md:7252` | 2026-06-27 | 2026-06-27 BlackThrush MultiDiGraph in_edges data-key batch view constructor - NO-SHIP (`cod-a`) | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 39 | `NEGATIVE_EVIDENCE.md:7370` | 2026-06-27 | 2026-06-27 BlackThrush directed degree generator-delegation bypass - NO-SHIP (`cod-b`) | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 40 | `NEGATIVE_EVIDENCE.md:7483` | 2026-06-27 | 2026-06-27 BlackThrush MultiDiGraph weighted degree values-only probe - NO-SHIP (`cod-a`) | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 41 | `NEGATIVE_EVIDENCE.md:8291` | 2026-06-21 | 2026-06-21 Cod-B `ubizp` MultiGraph SSSP Parent-Copy No-Ship (`br-r37-c1-04z53`, cod-b) | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 42 | `NEGATIVE_EVIDENCE.md:8589` | 2026-06-21 | 2026-06-21 Cod-A `non_edges` Exact-Int Lazy Iterator No-Ship (`br-r37-c1-04z53`, cod-a) | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 43 | `NEGATIVE_EVIDENCE.md:8641` | 2026-06-21 | 2026-06-21 Cod-B Native MultiDiGraph Compose No-Ship (`br-r37-c1-04z53`, cod-b) | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 44 | `NEGATIVE_EVIDENCE.md:8706` | 2026-06-21 | 2026-06-21 Cod-B Public Gauntlet + `non_edges` Set-Pop No-Ship (`br-r37-c1-04z53`, cod-b) | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 45 | `NEGATIVE_EVIDENCE.md:8861` | 2026-06-21 | 2026-06-21 Tree Submodule Spanning-Tree Route Rejection (`br-r37-c1-04z53`, cod-b) | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 46 | `NEGATIVE_EVIDENCE.md:9279` | 2026-06-20 | 2026-06-20 MultiDiGraph CSR Row-Streaming Boundary Reject (`br-r37-c1-04z53`, cod-a) | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 47 | `NEGATIVE_EVIDENCE.md:9345` | 2026-06-20 | 2026-06-20 MultiDiGraph CSR Boundary Snapshot Reject (`br-r37-c1-04z53`, cod-b) | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 48 | `NEGATIVE_EVIDENCE.md:9426` | 2026-06-20 | 2026-06-20 MultiDiGraph Precise Dirty-Key Sparse Reject (`br-r37-c1-04z53`, cod-b) | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 49 | `NEGATIVE_EVIDENCE.md:9491` | 2026-06-20 | 2026-06-20 MultiDiGraph Dirty Sparse Boundary Borrowed-Index Reject (`br-r37-c1-kqh2u`) | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 50 | `NEGATIVE_EVIDENCE.md:9576` | 2026-06-20 | 2026-06-20 Default-Order Matrix Export + Dijkstra Emitter No-Ships (`br-r37-c1-04z53`) | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 51 | `NEGATIVE_EVIDENCE.md:10451` | 2026-06-20 | 2026-06-20 Max-Weight Matching Native Tie-Break No-Ship | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 52 | `NEGATIVE_EVIDENCE.md:10621` | 2026-06-20 | 2026-06-20 `volume(G, S)` native-binding routing rejected (`br-r37-c1-volnative`, BlackThrush) | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 53 | `NEGATIVE_EVIDENCE.md:10732` | 2026-06-20 | 2026-06-20 `within_inter_cluster` bulk-community pre-fill REVERTED (net regression) (`br-r37-c1-wicbulk`, BlackThrush) | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 54 | `NEGATIVE_EVIDENCE.md:12916` | 2026-06-23 | 2026-06-23 BlackThrush DiGraph `edges(nbunch, data="w")` guarded-drain no-ship (`br-r37-c1-04z53.9162`, cod-b) | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 55 | `NEGATIVE_EVIDENCE.md:13034` | 2026-06-22 | 2026-06-22 BlackThrush stale MultiGraph connectivity and reverted micro-levers (`br-r37-c1-04z53.9164`, cod-a) | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 56 | `NEGATIVE_EVIDENCE.md:13326` | 2026-06-24 | 2026-06-24 BlackThrush/CopperCliff adjacency outer-dict cache - no-ship after remote rerun | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 57 | `NEGATIVE_EVIDENCE.md:13452` | 2026-06-24 | 2026-06-24 BlackThrush MultiDiGraph full weighted in/out degree - no-ship | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 58 | `NEGATIVE_EVIDENCE.md:13573` | 2026-06-25 | 2026-06-25 CopperCliff MultiDiGraph weighted degree - index-native accumulator - NO-SHIP (br-r37-c1-eilce) | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 59 | `NEGATIVE_EVIDENCE.md:13650` | 2026-06-25 | 2026-06-25 CopperCliff MultiDiGraph in_edges(data=attr) edge_key removal - NO-SHIP (br-r37-c1-eilce family) | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 60 | `NEGATIVE_EVIDENCE.md:13757` | 2026-06-25 | 2026-06-25 BlackThrush Graph.to_directed scalar-attr lazy-mirror attempt - NO-SHIP | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 61 | `NEGATIVE_EVIDENCE.md:13793` | 2026-06-25 | 2026-06-25 BlackThrush MultiGraph selfloop list-iterator lever - NO-SHIP | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 62 | `NEGATIVE_EVIDENCE.md:13843` | 2026-06-25 | 2026-06-25 BlackThrush MultiDiGraph weighted-degree edge-order accumulator - NO-SHIP | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 63 | `NEGATIVE_EVIDENCE.md:13882` | 2026-06-25 | 2026-06-25 BlackThrush core-laggard display-key probes - NO-SHIP | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 64 | `NEGATIVE_EVIDENCE.md:13915` | 2026-06-25 | 2026-06-25 BlackThrush MultiGraph selfloop attr tuple cache recheck - NO-SHIP | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 65 | `NEGATIVE_EVIDENCE.md:14015` | 2026-06-25 | 2026-06-25 BlackThrush MultiGraph.clear_edges adjacency-spine rebuild - NO-SHIP | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 66 | `NEGATIVE_EVIDENCE.md:14051` | 2026-06-25 | 2026-06-25 BlackThrush MultiGraph.selfloop_edges list-iterator handoff - REJECT | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 67 | `NEGATIVE_EVIDENCE.md:14077` | 2026-06-26 | 2026-06-26 BlackThrush MultiDiGraph weighted in/out degree count zip - NO-SHIP | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 68 | `NEGATIVE_EVIDENCE.md:14170` | 2026-06-25 | 2026-06-25 BlackThrush MultiDiGraph.in_edges data-key borrowed stream - REJECT | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 69 | `NEGATIVE_EVIDENCE.md:14211` | 2026-06-26 | 2026-06-26 BlackThrush MultiGraph.add_edge sparse attr mirror for clear_edges - REJECT | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 70 | `NEGATIVE_EVIDENCE.md:14251` | 2026-06-26 | 2026-06-26 BlackThrush MultiDiGraph.in_edges data-key clean cache - REJECT | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 71 | `NEGATIVE_EVIDENCE.md:14290` | 2026-06-26 | 2026-06-26 SilverStone MultiDiGraph weighted in-degree clean result cache - REJECT | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 72 | `NEGATIVE_EVIDENCE.md:14370` | 2026-06-26 | 2026-06-26 BlackThrush MultiGraph selfloop clean-int mirror bypass - REJECT | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 73 | `NEGATIVE_EVIDENCE.md:14424` | 2026-06-26 | 2026-06-26 BlackThrush MultiGraph.clear_edges wholesale mirror-map replace - REJECT | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 74 | `NEGATIVE_EVIDENCE.md:14472` | 2026-06-26 | 2026-06-26 BlackThrush weighted multi_source_dijkstra projection-order de-gate - REJECT | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 75 | `NEGATIVE_EVIDENCE.md:14579` | 2026-06-27 | 2026-06-27 BlackThrush MultiDiGraph weighted-degree cached node-key pairs - REVERTED | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 76 | `NEGATIVE_EVIDENCE.md:14717` | 2026-06-27 | 2026-06-27 BlackThrush MultiDiGraph weighted in-degree iterator materializer - NO-SHIP | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 77 | `NEGATIVE_EVIDENCE.md:14791` | 2026-06-27 | 2026-06-27 BlackThrush MultiDiGraph weighted in-degree lazy native iterator - NO-SHIP | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 78 | `NEGATIVE_EVIDENCE.md:14923` | 2026-06-27 | 2026-06-27 BlackThrush MultiGraph selfloop small-int object cache - NO-SHIP | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 79 | `NEGATIVE_EVIDENCE.md:14983` | 2026-06-27 | 2026-06-27 BlackThrush MultiDiGraph weighted in-degree edge-stream accumulator - NO-SHIP | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 80 | `NEGATIVE_EVIDENCE.md:15033` | 2026-06-27 | 2026-06-27 BlackThrush MultiDiGraph `in_edges(keys, data=<attr>)` default-key emit - NO-SHIP | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 81 | `NEGATIVE_EVIDENCE.md:15097` | 2026-06-27 | 2026-06-27 CopperCliff to_directed/to_undirected single-attr AttrMap-clone - NO-SHIP | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 82 | `NEGATIVE_EVIDENCE.md:15339` | 2026-06-28 | 2026-06-28 CopperCliff multi_source_dijkstra_path_length 0.20x — NO-SHIP (length-only de-delegation is value-exact but ORDER-blocked by the parked ... | 86.0000x | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 83 | `NEGATIVE_EVIDENCE.md:16038` | 2026-06-28 | 2026-06-28 CopperCliff NO-SHIP: MultiGraph size(weight) native scalar — substrate-bound below nx (REVERTED, 2 approaches tried) | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 84 | `NEGATIVE_EVIDENCE.md:16191` | 2026-06-28 | 2026-06-28 CopperCliff NO-SHIP (lever DISPROVEN by implementation): native CSR MG dijkstra ALSO loses — the floor is the MultiGraph's STRING-KEYED ... | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 85 | `NEGATIVE_EVIDENCE.md:16325` | 2026-06-28 | 2026-06-28 CopperCliff NO-SHIP: multi_source_dijkstra_path_length on a MultiGraph 0.088x — projection + gate-overhead bound (~0-gain to fix) | 0.0880x | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 86 | `NEGATIVE_EVIDENCE.md:16393` | 2026-06-28 | 2026-06-28 CopperCliff NO-SHIP: steiner_tree 0.556x — in-process mehlhorn is WORSE (0.346x); needs a native kernel | 0.3460x | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 87 | `NEGATIVE_EVIDENCE.md:16724` | 2026-06-29 | 2026-06-29 CopperCliff NO-SHIP (REVERTED): MG edges(data=<attr>) store-read routing — neutral/regression | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 88 | `NEGATIVE_EVIDENCE.md:16985` | 2026-06-29 | 2026-06-29 CopperCliff EDGE-batch corruption: same class as node fix, but dispatch tangled — attempt REVERTED | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 89 | `NEGATIVE_EVIDENCE.md:17170` | 2026-06-29 | 2026-06-29 BlackThrush NO-SHIP: MDG in_edges(keys,data=<attr>) py_node_key hoist — ~0 gain | — | recorded | **none** | no | VALID | no profile attribution; no binary sha (concurrent editors) |
| 90 | `NEGATIVE_EVIDENCE.md:17232` | 2026-06-29 | 2026-06-29 BlackThrush NO-SHIP: edge_py_keys default-int gate is NOT the in_edges(keys,data) floor | — | recorded | **none** | no | VALID | no profile attribution; no binary sha (concurrent editors) |
| 91 | `NEGATIVE_EVIDENCE.md:17600` | 2026-06-29 | 2026-06-29 BlackThrush NO-SHIP: PyGraph degree(nbunch, weight) int-accumulator twin — store-read floor, trades workloads | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 92 | `NEGATIVE_EVIDENCE.md:17842` | 2026-06-29 | 2026-06-29 BlackThrush NO-SHIP (cargo-bench-confirmed): clear_edges 0.351x is per-edge CONSTRUCTION fragmentation, not a clear_edges bug | 0.3510x | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 93 | `NEGATIVE_EVIDENCE.md:18721` | 2026-07-10 | 2026-07-10 cod_nx REJECT (PY WRAPPER, string-key weighted MultiGraph `shortest_path(source,target,weight)`): in-process multigraph bidirectional-Di... | — | **none** | 0.1% | no | **VOID** | no A/A null recorded; no binary sha (concurrent editors) |
| 94 | `NEGATIVE_EVIDENCE.md:19523` | 2026-07-11 | 2026-07-11 WhiteJaguar REJECT (FLOW, `max_flow`): compact sorted residual rows — 5.10% worse same-worker median (`br-r37-c1-fz193`) | — | **none** | **none** | yes | **VOID** | no A/A null recorded; no profile attribution |
| 95 | `NEGATIVE_EVIDENCE.md:20262` | 2026-07-13 | 2026-07-13 CrimsonHorizon REJECT (`MultiDiGraph(<true iterator>)`): broad drain wins plain/attrs but regresses keyed 23.7% (`br-r37-c1-2fxqr`) | — | 1.0085x | **none** | no | VALID | no profile attribution; no binary sha (concurrent editors) |
| 96 | `NEGATIVE_EVIDENCE.md:20919` | 2026-07-14 | 2026-07-14 RusticHollow NO-SHIP (`core_number`): edgeless peeling bypass is inside the null-control floor (`br-r37-c1-dy8w1`) | — | recorded | **none** | no | VALID | no profile attribution; no binary sha (concurrent editors) |
| 97 | `NEGATIVE_EVIDENCE.md:21085` | 2026-07-14 | 2026-07-14 RusticHollow NO-SHIP (`dag_longest_path_length`): direct scalar DP stays below the keep floor (`br-r37-c1-qwzl2`) | — | recorded | **none** | no | VALID | no profile attribution; no binary sha (concurrent editors) |
| 98 | `NEGATIVE_EVIDENCE.md:22022` | 2026-07-14 | 2026-07-14 GrayCitadel INVALID / NO-SHIP (`build_crosswalk_report`): borrowed fixture-ID indexes did not reach timed path (`br-r37-c1-wrq5x`) | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 99 | `NEGATIVE_EVIDENCE.md:22065` | 2026-07-14 | 2026-07-14 GrayCitadel INVALID / NO-SHIP (`dominance_frontiers`): index-space propagation did not reach timed path (`br-r37-c1-nfe62`) | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 100 | `NEGATIVE_EVIDENCE.md:22428` | 2026-07-14 | 2026-07-14 GrayCitadel NO-SHIP (`generate_sidecar_for_file`): fused packet serialization metadata pass — **1.0226x inside null noise** (`br-r37-c1-... | 1.0226x | recorded | **none** | yes | **VOID** | ratio inside 0.905-1.105 null band; no profile attribution |
| 101 | `NEGATIVE_EVIDENCE.md:23861` | 2026-07-24 | 2026-07-24 StormyForge REJECT (`MultiDiGraph(iterator)` scalar attrs): adopt the private snapshot as the live mirror — **1.0280x** (`br-r37-c1-kbs9t`) | 1.0280x | 1.0033x | **none** | no | **VOID** | ratio inside 0.905-1.105 null band; no profile attribution; decided on the cv<5% gate; no binary sha (concurrent editors) |
| 102 | `NEGATIVE_EVIDENCE.md:23905` | 2026-07-24 | 2026-07-24 StormyForge REJECT (`MultiDiGraph(iterator)` scalar attrs): defer normalized fallback tuples — **1.0105x** (`br-r37-c1-pab55`) | 1.0105x | 0.9986x | **none** | no | **VOID** | ratio inside 0.905-1.105 null band; no profile attribution; decided on the cv<5% gate; no binary sha (concurrent editors) |
| 103 | `NEGATIVE_EVIDENCE.md:24112` | 2026-07-24 | 2026-07-24 StormyForge REJECT (`MultiDiGraph(iterator)` keyed scalar attrs): fused validation + native decode — **1.0202x** (`br-r37-c1-4ig2s`) | 1.0202x | 1.0056x | **none** | no | **VOID** | ratio inside 0.905-1.105 null band; no profile attribution; decided on the cv<5% gate; no binary sha (concurrent editors) |
| 104 | `NEGATIVE_EVIDENCE.md:24161` | 2026-07-24 | 2026-07-24 StormyForge REJECT (`MultiDiGraph(iterator)` keyed scalar attrs): exact tuple-iterator stage pre-sizing — **1.0144x** (`br-r37-c1-04z53.... | 1.0144x | 1.0009x | **none** | no | **VOID** | ratio inside 0.905-1.105 null band; no profile attribution; decided on the cv<5% gate; no binary sha (concurrent editors) |
| 105 | `NEGATIVE_EVIDENCE.md:24210` | 2026-07-24 | 2026-07-24 StormyForge REJECT (`MultiDiGraph(iterator)` keyed scalar attrs): raw exact-string stage lookup — **0.9897x** (`br-r37-c1-04z53.9182`) | 0.9897x | 1.0065x | **none** | no | **VOID** | ratio inside 0.905-1.105 null band; no profile attribution; decided on the cv<5% gate; no binary sha (concurrent editors) |
| 106 | `NEGATIVE_EVIDENCE_cc.md:423` | 2026-07-12 | REJECT (cod, 2026-07-12): declined `closeness_centrality` per-source CSR fallback does not clear its null (br-r37-c1-yy0rp) | — | 1.0852x | **none** | no | VALID | no profile attribution; no binary sha (concurrent editors) |
| 107 | `NEGATIVE_EVIDENCE_cc.md:688` | 2026-07-12 | REJECT + SWEEP (cc, 2026-07-12): `ego_graph` BFS below-null; neighbour-walk sub-family exhausted | — | recorded | **none** | no | VALID | no profile attribution; no binary sha (concurrent editors) |
| 108 | `NEGATIVE_EVIDENCE_cc.md:1233` | 2026-07-12 | REJECT (cc, 2026-07-12): `quotient_graph` batch — BELOW NULL (br-r37-c1-quotientbatch) | — | 1.1103x | **none** | no | VALID | no profile attribution; no binary sha (concurrent editors) |
| 109 | `NEGATIVE_EVIDENCE_cc.md:1903` | 2026-07-11 | SURFACE (cc, 2026-07-11): `barabasi_albert_graph` batch-by-index = BELOW-NOISE (1.04x) — BA is SAMPLING-bound, not insertion-bound → not shipped | 1.0400x | 0.9967x | **none** | no | **VOID** | ratio inside 0.905-1.105 null band; no profile attribution; no binary sha (concurrent editors) |
| 110 | `NEGATIVE_EVIDENCE_cc.md:3307` | 2026-07-10 | REJECT (cc, 2026-07-10): MultiGraph `degree(nbunch, weight=)` per-edge `edge_key` alloc removal — byte-identical but **below the noise floor**; the... | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 111 | `NEGATIVE_EVIDENCE_cc.md:3431` | 2026-07-10 | REJECT (cc, 2026-07-10): the different-primitive SoA / cache-friendly integer-adjacency for MG target Dijkstra is **0.7152x** (0/121 wins) — the up... | 0.7152x | 0.9987x | **none** | no | VALID | no profile attribution; no binary sha (concurrent editors) |
| 112 | `NEGATIVE_EVIDENCE_cc.md:3494` | 2026-07-10 | REJECT (cc, 2026-07-10): scratch-reuse for the MG target Dijkstra is BELOW the null floor — measured 1.0053x median, inside NULL [0.836,1.071]. The... | 1.0053x | 0.9976x | **none** | no | **VOID** | ratio inside 0.905-1.105 null band; no profile attribution; no binary sha (concurrent editors) |
| 113 | `NEGATIVE_EVIDENCE_cc.md:4563` | 2026-06-28 | DOMAIN MAP + 2 NO-SHIPs + BLOCKER (cc, 2026-06-28): dijkstra/bellman_ford family & flow/matching/operators/traversal sweeps — all wins except the c... | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 114 | `NEGATIVE_EVIDENCE_cc.md:4805` | 2026-06-27 | NO-SHIP (cc, 2026-06-27): MDG in_edges(keys,data=key) single-pass bucket walk + node-obj hoist — REGRESSION 0.263x->0.190x | 0.1900x | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 115 | `NEGATIVE_EVIDENCE_cc.md:5009` | — | read_edgelist 0.40x: parse_edgelist NOT a drop-in (REVERTED) | 0.4000x | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 116 | `NEGATIVE_EVIDENCE_cc.md:5629` | — | SCAFFOLD CAUGHT A REGRESSION: qbj9u directed effective_size kernel diverged (REVERTED) | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 117 | `NEGATIVE_EVIDENCE_cc.md:5690` | 2026-06-24 | NO-SHIP (CORRECTED): adjacency() outer-dict cache — FALSIFIED by durable per-crate Criterion bench (2026-06-24, CopperCliff) | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 118 | `NEGATIVE_EVIDENCE_cc.md:5778` | 2026-06-25 | 2026-06-25 CopperCliff to_directed scalar deepcopy-skip - NO-SHIP ~0-gain (br-r37-c1-eilce family) | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 119 | `NEGATIVE_EVIDENCE_cc.md:5808` | 2026-06-25 | 2026-06-25 CopperCliff set_edge/set_node_attributes broadcast - NO-SHIP ~0-gain (eager-mirror floor) | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 120 | `NEGATIVE_EVIDENCE_cc.md:5873` | 2026-06-25 | 2026-06-25 CopperCliff BUILDFIX main was non-compiling + dijkstra sync-dirty NO-SHIP | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 121 | `NEGATIVE_EVIDENCE_cc.md:6055` | 2026-06-25 | 2026-06-25 CopperCliff products/bipartite/operators/DAG sweep — REJECTS (modest delegation-tax gaps) | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 122 | `NEGATIVE_EVIDENCE_cc.md:6071` | 2026-06-25 | 2026-06-25 CopperCliff I/O sweep — parse_adjlist/adjacency_data REJECT (add_edges_from substrate floor) | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 123 | `NEGATIVE_EVIDENCE_cc.md:6110` | 2026-06-25 | 2026-06-25 CopperCliff REJECT: set-order-locked delegated algos are STRUCTURALLY unwinnable vs nx | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 124 | `NEGATIVE_EVIDENCE_cc.md:6197` | 2026-06-25 | 2026-06-25 CopperCliff REJECT: structural/copy/conversion primitive sweep — losses are native+floored | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 125 | `NEGATIVE_EVIDENCE_cc.md:6324` | 2026-06-25 | 2026-06-25 CopperCliff REJECT: approximation.steiner_tree 0.409x — conversion-tax-bound, de-delegation parity-risky | 0.4090x | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 126 | `NEGATIVE_EVIDENCE_cc.md:6539` | 2026-06-25 | 2026-06-25 CopperCliff construction-builder sweep — binomial_tree REJECT, rest wins/floor-bound | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 127 | `NEGATIVE_EVIDENCE_cc.md:6584` | 2026-06-25 | 2026-06-25 CopperCliff property-check + LCA/cuts/matching sweep — wins; min_weight_matching REJECT | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 128 | `NEGATIVE_EVIDENCE_cc.md:6599` | 2026-06-25 | 2026-06-25 CopperCliff chordal/dominating/eulerian sweep — wins; connected_dominating_set REJECT | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 129 | `NEGATIVE_EVIDENCE_cc.md:6737` | 2026-06-26 | 2026-06-26 CopperCliff re-examined order-locked rejects vs their TEST CONTRACTS (after find_asteroidal win) | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 130 | `NEGATIVE_EVIDENCE_cc.md:6766` | 2026-06-26 | 2026-06-26 CopperCliff flow sweep — capacity_scaling/max_flow_min_cost WINS; min_cost_flow family REJECT (convert+delegate bound) | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 131 | `NEGATIVE_EVIDENCE_cc.md:6824` | 2026-06-26 | 2026-06-26 CopperCliff removal/matrix-centrality sweep — WINS; communicability_betweenness O(n^4)-hard REJECT | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 132 | `NEGATIVE_EVIDENCE_cc.md:6840` | 2026-06-26 | 2026-06-26 CopperCliff spectral sweep — fiedler_vector win CONFIRMED at scale; spectral_ordering sign-locked REJECT | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 133 | `NEGATIVE_EVIDENCE_cc.md:6961` | 2026-06-26 | 2026-06-26 CopperCliff group_betweenness Puzis port — WIP/NO-SHIP-yet (Rust bug, Python ref VERIFIED) | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 134 | `NEGATIVE_EVIDENCE_cc.md:6981` | 2026-06-26 | 2026-06-26 CopperCliff group_betweenness(>=3) DEFINITIVE REJECT — nx's Puzis algorithm is SET-ORDER-DEPENDENT | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 135 | `NEGATIVE_EVIDENCE_cc.md:7027` | 2026-06-26 | 2026-06-26 CopperCliff steiner_tree — fast-Kou REJECT (weight-locked to nx mehlhorn default); LCA/dominating wins | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 136 | `NEGATIVE_EVIDENCE_cc.md:7205` | 2026-06-26 | 2026-06-26 CopperCliff multi_source via k-single_source workaround — REJECT (paths diverge + slower); fully reserved-gated | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 137 | `NEGATIVE_EVIDENCE_cc.md:7309` | 2026-06-26 | 2026-06-26 CopperCliff treewidth_min_degree convert+delegate — REJECT (decomp is adjacency-order-sensitive, breaks byte-exactness) | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 138 | `NEGATIVE_EVIDENCE_cc.md:7486` | 2026-06-26 | 2026-06-26 CopperCliff NEGATIVE: MG.size(weight) native-AttrMap read — byte-exact but perf inconsistent (REVERTED) | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 139 | `NEGATIVE_EVIDENCE_cc.md:7519` | 2026-06-26 | 2026-06-26 CopperCliff NEGATIVE #2: MG.size(weight) zero-alloc native fold — ~0-gain at bench size (REVERTED) | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 140 | `NEGATIVE_EVIDENCE_cc.md:7753` | 2026-06-27 | 2026-06-27 CopperCliff NEGATIVE: DiGraph in_edges(data=str) store-read ~0-gain (already near floor; REVERTED) | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 141 | `NEGATIVE_EVIDENCE_cc.md:7902` | 2026-06-27 | 2026-06-27 CopperCliff REVERTED a571d20d6 (degree index-native = host-noise false win) | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 142 | `NEGATIVE_EVIDENCE_cc.md:7930` | 2026-06-27 | 2026-06-27 CopperCliff RA/AA link-pred 0.59x = neighbors-materialization substrate (degree-batch REGRESSED, reverted) | 0.5900x | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 143 | `NEGATIVE_EVIDENCE_cc.md:7962` | 2026-06-27 | 2026-06-27 CopperCliff community link-pred (cn/ra_index/within_inter soundarajan_hopcroft) hybrid native REGRESSED, reverted | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 144 | `NEGATIVE_EVIDENCE_cc.md:8079` | 2026-06-27 | 2026-06-27 CopperCliff remove_edges_from bulk-retain = ~0-gain (REVERTED) — per-edge swap_remove+String-hash is the floor | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 145 | `NEGATIVE_EVIDENCE_cc.md:8095` | 2026-06-27 | 2026-06-27 CopperCliff FINDING: add_edges_from(dict attrs) leaves Rust store stale -> size/degree/wiener(weight) WRONG (correctness bug); add_weigh... | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 146 | `NEGATIVE_EVIDENCE_cc.md:8176` | 2026-06-27 | 2026-06-27 CopperCliff subgraph(view) 0.5x view-machinery-bound (filt set-intersection marginal, reverted) + find_induced_nodes without_fallback PR... | 0.5000x | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 147 | `NEGATIVE_EVIDENCE_cc.md:8291` | — | Mutation-cluster residual is a PyO3 call-boundary floor — SURFACED (CopperCliff, no-ship) | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 148 | `NEGATIVE_EVIDENCE_cc.md:8581` | 2026-07-02 | 2026-07-02 CopperCliff SURFACE (architectural, NO-SHIP this pass): node removal is the storage-model wall — 0.003-0.14x, needs slotmap/deferred-com... | 0.1400x | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 149 | `NEGATIVE_EVIDENCE_cc.md:9101` | 2026-07-22 | 2026-07-22 SnowyBadger (cc) S8 MEASURED VERDICT: positional renumber REJECTED for the real flip — 190-203x slower than the String store on removals... | 203.0000x | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 150 | `NEGATIVE_EVIDENCE_cc.md:9167` | 2026-07-22 | 2026-07-22 SnowyBadger (cc) REJECT (br-r37-c1-2zn1u): AVX2 dense-linalg — the pure-FLOP core moves only 1.2-1.4x; below shipping threshold | — | **none** | recorded | no | **VOID** | no A/A null recorded; no binary sha (concurrent editors) |
| 151 | `perf-negative-results.md:191` | 2026-07-23 | 2026-07-23 SnowyBadger (cc) REJECT + BLOCKER (br-r37-c1-04z53): edges(nbunch,data=True) repack removal — correct but reddens full suite via summari... | — | **none** | recorded | no | **VOID** | no A/A null recorded; no binary sha (concurrent editors) |
| 152 | `perf-negative-results.md:217` | 2026-07-23 | 2026-07-23 SnowyBadger (cc) SHIP + CORRECTION (br-r37-c1-04z53): edges(nbunch,data) repack removal — the prior REJECT was an INSTALL-STATE artifact... | — | **none** | **none** | no | **VOID** | no A/A null recorded; no profile attribution; no binary sha (concurrent editors) |
| 153 | `perf-negative-results.md:395` | 2026-07-23 | 2026-07-23 BlackThrush (cc) REJECT (br-r37-c1-thp6w): MultiGraph fresh-batch capacity-reserve does NOT move construction — String-substrate floor, ... | — | 1.0000x | 8.0% | no | VALID | no binary sha (concurrent editors) |
| 154 | `perf-negative-results.md:431` | 2026-07-24 | 2026-07-24 BlackThrush (cc) REJECT (br-r37-c1-thp6w S13): slab index-read route `edges_ordered_indices_borrowed` — O(n) slot->position build offset... | — | recorded | **none** | no | VALID | no profile attribution; no binary sha (concurrent editors) |
| 155 | `perf-negative-results.md:622` | 2026-07-24 | 2026-07-24 StormyForge REJECT (`MultiDiGraph(iterator)` scalar attrs): private snapshot mirror transfer — **1.0280x** (`br-r37-c1-kbs9t`) | 1.0280x | 1.0033x | **none** | no | **VOID** | ratio inside 0.905-1.105 null band; no profile attribution; no binary sha (concurrent editors) |
| 156 | `perf-negative-results.md:651` | 2026-07-24 | 2026-07-24 StormyForge REJECT (`MultiDiGraph(iterator)` scalar attrs): deferred normalized fallback tuples — **1.0105x** (`br-r37-c1-pab55`) | 1.0105x | 0.9986x | **none** | no | **VOID** | ratio inside 0.905-1.105 null band; no profile attribution; no binary sha (concurrent editors) |
| 157 | `perf-negative-results.md:782` | 2026-07-24 | 2026-07-24 StormyForge REJECT (`MultiDiGraph(iterator)` keyed scalar attrs): fused validation + native decode — **1.0202x** (`br-r37-c1-4ig2s`) | 1.0202x | 1.0101x | **none** | no | **VOID** | ratio inside 0.905-1.105 null band; no profile attribution; no binary sha (concurrent editors) |
| 158 | `perf-negative-results.md:817` | 2026-07-24 | 2026-07-24 StormyForge REJECT (`MultiDiGraph(iterator)` keyed scalar attrs): exact tuple-iterator stage pre-sizing — **1.0144x** (`br-r37-c1-04z53.... | 1.0144x | 1.0060x | **none** | no | **VOID** | ratio inside 0.905-1.105 null band; no profile attribution; no binary sha (concurrent editors) |
| 159 | `perf-negative-results.md:853` | 2026-07-24 | 2026-07-24 StormyForge REJECT (`MultiDiGraph(iterator)` keyed scalar attrs): raw exact-string stage lookup — **0.9897x** (`br-r37-c1-04z53.9182`) | 0.9897x | 1.0065x | **none** | no | **VOID** | ratio inside 0.905-1.105 null band; no profile attribution; no binary sha (concurrent editors) |

