# Reality Check — 2026-09-02

**HEAD:** `ab7303351` (main) · **Beads:** 3,552 closed / 77 in_progress (40 unassigned) / 6 blocked / 2 open ·
**Method:** every claim below was checked against the tree, `gh`, PyPI, or a run on this host on 2026-09-02.
Prior checks: `docs/history/REALITY_CHECK.md` (2026-04-23), `artifacts/reality-check-2026-05-03.md`.

## Headline

The library is real and fast. The product is not shipped, and the evidence pipeline that the README
calls "load-bearing" has never run.

- `pip install franken-networkx` is HTTP 404 on PyPI. The only release, `v0.2.0` (2026-06-21), had
  every wheel job fail (Linux x86_64, musllinux, macOS arm64, Windows, sdist) and publish skipped; the
  GitHub release has zero assets. The bead that tracked shipping (`franken_networkx-ciq6`) is CLOSED.
- CI on `main` has **0 successful runs out of 6,947**. Every sampled failure from 2026-04-17 to
  2026-09-01 died at **G0 docs freshness** (README/FEATURE_PARITY/CHANGELOG lag 410 commits vs a limit
  of 50) with G1–G8 skipped; 96% of runs are cancelled by concurrency. G4 pytest, G4c docs, G4d
  examples, G5 conformance + B4 freshness, G6 perf SLO, G7 UBS, G7b fuzz, G8 RaptorQ have produced no
  evidence on `main`. The nightly Hypothesis workflow is 0/108.
- The code itself is in good shape where it counts: zero `todo!`/`unimplemented!`/TODO in 254 KLOC
  of Rust, `#![forbid(unsafe_code)]` in every crate (the only `unsafe` is a test-only allocator),
  815 GIL-release sites, 33 fuzz binaries, 1,083 Python test files / 10,530 tests, and the live
  coverage generator reports **92.6% strict-present, 0 missing** (README says 82.3%, the committed
  ledger says 84.0%).

## Vision checklist

| # | Goal (source) | Status | Sev | Beads | Evidence |
|---|---|---|---|---|---|
| 1 | `pip install franken-networkx`, prebuilt wheels for 5 platforms (README top, Deployment) | NOT_SHIPPED | Critical | NO_BEAD (ciq6 false-closed) | PyPI 404; release run all wheel jobs failed; `gh release view v0.2.0` no assets |
| 2 | Standalone API: quick start / tutorial run as written | PARTIAL | Major | none | shortest_path, components, karate, Louvain parity, planarity, pickle, GraphML round-trip verified; `fnx.pagerank` needs scipy (routes to `_pagerank_scipy`), so the quick start and all 4 `examples/*.py` fail on a bare install |
| 3 | NetworkX backend with zero call-site changes | WORKING | – | – | entry points registered; `backend=` and `backend_priority` dispatch verified; 313 algorithms (README: 316) |
| 4 | Observable-behaviour parity contract enforced by the Python suite | PARTIAL | Major | 25+ parked in_progress | suite is 3x larger than README says; targeted run 234 pass / 10 fail (6 env, 4 real); open P1/P2 parity defects in the class core (see below) |
| 5 | Five auto-generated ledgers "fail CI on drift" | NOT AS CLAIMED | Major | NO_BEAD | only pytest checks them and pytest never runs in CI; delegation/upstream/api-ergonomics ledgers last regenerated 2026-05-22; `test_generated_coverage_matrix_document_is_current` fails on main |
| 6 | CGSE: every algorithm call emits a ComplexityWitness; complexity bound is a CI gate | PARTIAL | Major | NO_BEAD | 13 policies, 12-algorithm registry OK; 22 `cgse_begin` / 42 `cgse_publish` sites across 654 pub fns; Python can inspect policies but cannot collect witnesses; no CI job asserts bounds |
| 7 | Strict/Hardened modes "both available at runtime" | PARTIAL (Rust-only) | Major | NO_BEAD (D1–D4 closed) | `Graph` carries mode + `RuntimePolicy`; readwrite readers take a mode; `fnx-python` hardcodes `Strict` (46 refs); `fnx.Graph(mode="hardened")` silently becomes a graph attribute |
| 8 | RaptorQ sidecars, scrub reports, decode proofs for long-lived artifacts | UNPROVEN | Major | NO_BEAD | crate exists (956 lines, used by no other crate); only G8 exercises it; `artifacts/conformance/latest` dated 2026-05-10 |
| 9 | Differential conformance harness + fresh artifacts + freshness gate (roadmap #2) | UNPROVEN | Major | NO_BEAD | `fnx-conformance` 26 KLOC and `verify_conformance_freshness.py` exist; G5 never runs; artifacts 4 months stale |
| 10 | CI gate topology G0–G8 "load-bearing" | NOT AS CLAIMED | Critical | NO_BEAD | see headline; even with G0 fixed, G4c/G4d install no scipy and would fail on pagerank |
| 11 | Performance: measured wins, honest loss table, reproducible | PARTIAL | Major | p80x1 (38 closed / 10 open) | kernel wins reproduce here (see probe); README loss table omits the worst defects found after 2026-08-19; "reproduce with `perf_harness.py marshaling`" does not reproduce the table; quiescence gate unsatisfiable on a shared host |
| 12 | Native planarity (roadmap #3) | MOSTLY DONE | Minor | closed | `is_planar` → native `is_planar_lr` (K5, Petersen, K3,3 correct); `check_planarity` certificate still delegates; README still calls it a roadmap item |
| 13 | Community detection native | PARTIAL | Minor | none open | Louvain native only for plain unweighted `Graph` w/o self-loops, else nx; label propagation is pure Python; greedy modularity always nx; FEATURE_PARITY.md wrongly says Rust covers all three |
| 14 | Security doctrine (fuzz, fail-closed, threat notes) | PARTIAL | Minor | – | 33 fuzz bins, nightly fuzz jobs pass; strict fail-closed at Rust level; hardened unreachable from Python; risk notes dated 2026-04-15 |
| 15 | V1 spec acceptance gates A–D | 1 of 4 evidenced | Critical | NO_BEAD | B (fuzz) passes nightly; A (parity report), C (SLO budgets), D (scrub-clean durability) have no current evidence |
| 16 | Docs are the measuring stick (G0's purpose) | STALE | Major | NO_BEAD | see "README claims vs tree" |
| 17 | Work graph keeps a swarm pointed at the vision | DEGRADED | Major | – | `br ready` pool is 2 items; 77 in_progress (40 unassigned) act as a parking lot; no roadmap item has an open bead |

## What is working (verified today)

- Rebuilt the extension at HEAD (`maturin develop --uv --release`, 4 min) and ran: README quick start
  (minus pagerank), backend dispatch both ways, karate tutorial numbers (34/78, diameter 5, radius 3),
  Louvain seed=7 partition identical to nx, `is_planar` on K5/Petersen/K4, exception identity,
  pickling, GraphML round-trip, MultiGraph key collision parity, 16 concurrent Dijkstra calls.
- `tests/python/test_multigraph_row_view_contract.py` (bead r638d "MAIN RED") passes at HEAD.
  `test_error_messages.py` and `test_thread_safety.py` pass except one scipy-dependent test.
- 1-in-10 sample of the suite (109 files, 7.5 min): **6,074 passed, 260 failed, 122 errors, 33
  skipped**. Re-running the failing files with one-line tracebacks: every failure in the spectral,
  matrix, communicability, Fiedler, structural-holes, centrality and adjacency-matrix files is
  `ModuleNotFoundError: No module named 'scipy'` (the shared venv has no scipy); three
  exception-type-parity rows fail only because nx and fnx raise in a different order when scipy is
  absent; **one real parity failure**: `test_nbunch_native_walk_mutation_parity.py`
  (`('completes', 17)`), the residue tracked by bead 8c7m5. Plus the four real
  `test_coverage_gaps.py` failures (committed `coverage.md` has drifted from the generator). With
  scipy installed the parity suite is near-green at HEAD; the suite is not the problem.
- Interleaved same-process sanity probe (NOT a gate; loadavg 6–8): SSSP length 6.3x, connected
  components 7.4x, clustering 15x, betweenness k=50 109x, closeness n=220 141x, node_connectivity 33x.
  Losses reproduce too: `add_edge` 0.74x, `G[u][v]` 0.96x, `has_node` 0.80x, and **`remove_node`
  0.016x → 0.0037x from n=1,600 to n=25,600** (super-linear; bead tv8wd).

## What is not working

1. Shipping (goal 1) — nothing outside this checkout can install the library.
2. CI (goal 10) — no gate after G0 has run on `main`; the swarm has been landing ~30 commits/day for
   months with no automated evidence. The concurrency `cancel-in-progress` makes the tip run a lottery.
3. Silent wrong answers from the dual attribute store (beads 303zo, pk1nb): node/edge attributes
   written after construction reach the Python dicts but not the typed Rust store native kernels
   read, and kernels default on miss. A weighted kernel returned the unweighted answer while
   `G.nodes(data=True)` showed the right values. `copy()` repairs the node side only.
4. Parity residues in the class core, all parked in_progress: `copy.copy` shares attr dicts in nx,
   not fnx (all four classes, P1); MDG unkeyed `get_edge_data` returns a constructed dict and is
   O(parallel edges) (P1, worst cell 0.027x); `edges(nbunch)` over-raises during mutation; relabel
   drops subclasses; distance type flattened for bool/Fraction; flow returns `0.0` where nx returns
   `0`; `has_node` raises-and-discards OverflowError on negative ints; two tests fail only in the full
   suite (cross-test pollution).
5. `remove_node` is super-linear on all four classes (P1) — a complexity-class bug, not a constant.
6. pagerank is a scipy sparse power iteration over a natively built CSR (since 2026-05-24), not the
   native Rust kernel the README traces; scipy is optional in `pyproject.toml`, so the README quick
   start, all four examples, and the G4c/G4d jobs (which install only `networkx`) cannot pass.

## README claims vs tree (the G0 gate is right that these are stale)

| Claim | README | Tree today |
|---|---|---|
| Python test files | 377 | 1,083 (10,530 tests) |
| `__all__` exports | 763 | 793 |
| Backend-dispatched algorithms | 316 | 313 |
| Strict coverage | 3,399/4,129 = 82.3%, 700 partial, 30 missing | live generator: 3,823/4,129 = 92.6%, 306 partial, 0 missing (committed ledger: 84.0%) |
| Parity-helper routes | 143 exports / 167 routes | 198 call sites (ledger from 2026-05-22) |
| `__init__.py` size | 1.4 MB | 2.96 MB / 70,851 lines / 1,337 defs |
| fnx-algorithms | ~47 KLOC / 550+ pub fns | 95.7 KLOC (with inline tests) / 654 pub fns |
| TieBreakPolicy variants | 13 (body) / 12 (glossary) | 13 |
| pagerank | "native power iteration", Rust trace | scipy matvec, native CSR build |
| `is_planar` | necessary-only Rust check, native port on roadmap | native LR kernel landed; certificate path delegates |
| Community | "Rust covers louvain/LPA/CNM" (FEATURE_PARITY) | Louvain conditional native, LPA Python, CNM nx |
| `test_conformance.py` (README + AGENTS.md) | exists | does not exist |
| `maturin develop` command (AGENTS.md) | works | needs `--uv` in this venv |
| Known losses table | add_edge, has_node absent, preferential_attachment, read_* | omits remove_node (0.0015x), MDG get_edge_data (0.027x), G[u][v] (0.36x per bead ey6ob) |
| `Graph` struct listing (Memory Model) | `IndexMap<String, IndexSet<String>>` adjacency | `adj_indices: Vec<Vec<usize>>` + `FxIndexMap<(usize,usize), AttrMap>` edges |

## Would finishing every open + in_progress bead close the gap?

No. The 79 non-closed beads are ~90% perf micro-levers and class-core parity residues. Zero of them
cover: wheels/PyPI, a green CI, README/ledger refresh, the Hardened-mode Python toggle, conformance
or RaptorQ artifact refresh, an SLO report, scipy-free examples/docs jobs, or remaining community
natives. The P1 correctness beads that do exist (303zo, pk1nb, copyshare, f3i50, tv8wd) are parked
in_progress with no assignee movement since 2026-08-24/27.

## Bridge plan (ordered by vision impact)

**P0 — ship and prove**
1. Release pipeline: diagnose the five failed wheel jobs on the `v0.2.0` run, fix, cut `v0.2.1`
   (or `v0.3.0`) with wheels + sdist, run `scripts/test_pypi_install.sh`, publish. Success: clean venv
   on Linux/macOS/Windows, `pip install 'franken-networkx[all]'`, README quick start runs verbatim.
   Reopen or replace `franken_networkx-ciq6`.
2. Green CI: refresh README/FEATURE_PARITY/CHANGELOG with the numbers above (that alone clears G0);
   add scipy to G4c/G4d (or make the quick start and examples scipy-free); run G4 and fix the real
   reds (coverage drift, cross-test pollution beads 2i3mf/1q2wo); then decide, through the joint
   decision protocol, whether a 50-commit docs-lag gate is the right instrument for a 30-commit/day
   swarm. Do not weaken it silently.
3. Ledger truth: regenerate `delegation_ledger`, `upstream_divergence_ledger`,
   `api_ergonomics_audit`, `raw_vs_public_audit`, `coverage.md`; add each generator's `--check` to CI
   so "drift fails CI" is literally true.

**P1 — the contract in the class core**
4. Dual-store fix (303zo + pk1nb): one authoritative attribute store, or a write-through flush on
   every Python-side attribute write; every native kernel that reads attrs gets a negative test a
   naive implementation fails.
5. Land the parked P1/P2 parity beads (copyshare-2h5uj, f3i50/himzq, u5tyh/8c7m5, k9sxj, 3dtn4,
   7aymx, qan46) and `remove_node` (tv8wd).

**P1 — vision features with no bead**
6. Hardened mode from Python: `mode=` on constructors and `read_*`, evidence-ledger export, the
   ≥24 strict + ≥24 hardened fixtures the README promises.
7. CGSE honesty: either wire witnesses per family and expose `collect_witnesses` from Python, or
   scope the README claim to the 12 reference algorithms; put the complexity-bound assertion in a
   real CI job.
8. Evidence refresh: run G5 and G8 locally now, commit the dashboard/sidecars or the freshness
   report; make B4 part of the pre-release checklist.
9. Perf claims: finish `p80x1`; add remove_node / get_edge_data / G[u][v] to the loss table; fix the
   reproduction instruction; record the quiescence-gate policy (dedicated host window vs balanced
   square) as a decision, not a retry loop.

**P2 — tail**
10. Community natives (weighted/self-loop Louvain, Rust LPA, CNM), `check_planarity` embedding,
    GraphMLReader surface (ozpfa), Partition inner classes; census of the 198 parity-helper routes.
11. Work-graph hygiene: triage the 77 in_progress (return unassigned ones to open or close on
    evidence), file beads for every NO_BEAD row above, keep `br ready` non-empty.
12. Docs: AGENTS.md test file names and `--uv`; README memory-model struct; glossary 12→13.

## Blockers

- Process: a permanently red G0 means no gate produces evidence and nobody is alarmed by it; the
  suite-wide AGENTS.md already names the failure mode (conformance metastasis: rigor became the
  product).
- Shipping: the SHIP bead was closed on "operational steps remaining", which hid a failing release
  workflow for five months.
- Environment: the shared venv lacks scipy and hypothesis; the stale-`.so` guard blocks pytest for
  everyone until someone rebuilds (done today at 22:51 local).
- Architecture: two attribute stores; PyO3 per-call floors; a 70k-line `__init__.py` that UBS cannot
  scan (bead iwlu9).
