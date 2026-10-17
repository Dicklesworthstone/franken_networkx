# FrankenNetworkX Reality Check

> Historical audits below. The [2026-10-13 audit](#reality-check-2026-10-13)
> supersedes the [2026-10-04 audit](#reality-check-2026-10-04) and the 2026-04-24
> audit on current-state conclusions. Historical findings are retained verbatim.

*Generated 2026-04-24 via `/reality-check-for-project` skill (cc-networkx).*

Prior audit: [`audit_networkx_reality.md`](audit_networkx_reality.md) from
2026-04-22. This pass updates figures after the subsequent review / fuzzing /
conformance waves and re-probes the project against its stated vision.

## Vision (from README.md)

> FrankenNetworkX is a high-performance, Rust-backed drop-in replacement for
> NetworkX. Use it as a standalone library **or** as a NetworkX backend with
> zero code changes.

Implicit contract:

1. Public API surface matches `networkx.__dict__` — any `nx.X` has a
   `franken_networkx.X` or resolves transparently via attribute fallback.
2. Observable outputs match NetworkX for scoped algorithms (tie-break,
   iteration order, return types, exception classes).
3. A curated set of algorithms dispatches to the Rust backend when
   `backend_priority = ["franken_networkx"]` is active.
4. Four graph classes (`Graph` / `DiGraph` / `MultiGraph` / `MultiDiGraph`)
   with unified method + algorithm surface.

## Surface-Area Coverage

Measured against installed `networkx==3.6.1` and `franken_networkx` HEAD.

| Metric | Count |
|---|---|
| `franken_networkx.__all__` public exports | **801** |
| Names in `dir(networkx)` (public, non-dunder) | 944 |
| Names in `dir(franken_networkx)` (public) | 1023 |
| Names in `dir(nx)` but **not** in `dir(fnx)` | **0** |
| Callable / class nx names missing from `fnx.__all__` (excluding submodules) | **0** |

The gap between 944 and 801 is entirely submodule re-exports
(`nx.bipartite`, `nx.community`, `nx.drawing`, `nx.algorithms`, `nx.classes`,
`nx.convert`, etc.) and a handful of internal helpers like `_dispatchable`.
Every public **callable** in the nx surface is reachable from
`franken_networkx`.

### Coverage matrix (from `docs/coverage.md`)

| Category | Count | % |
|---|---|---|
| `RUST_NATIVE`    | 107 | 13% |
| `PY_WRAPPER`     | 671 | 83% |
| `NX_DELEGATED`   | **0** | 0% |
| `CLASS`          | 21 | 2% |
| `CONSTANT`       | 2 | 0% |
| **Total**        | **801** | |

`NX_DELEGATED = 0` — no public export calls back into networkx at runtime.
This gate is enforced by
`test_public_coverage_has_no_networkx_delegated_exports`. The two residual
delegates from the 2026-04-22 audit (`current_flow_closeness_centrality`,
`edge_current_flow_betweenness_centrality`) have been reclassified to
`PY_WRAPPER` — they now run through a Python-side solver path rather than
calling `networkx.*` directly.

## Parity Suite Pass/Fail

`pytest tests/python/` on 2026-04-24:

```
3967 passed, 72 skipped, 1 xfailed, 32 warnings in 173.22s
```

- 0 failures, 0 errors.
- The `xfailed` is the single known-upstream-disagreement test.
- Skips are environment-conditional fixtures (e.g. GEXF LXML-only paths) and
  the scipy-sparse round-trip cases when scipy isn't present.

## Conformance Probe — 5 Random NX APIs

Picks span one generator, three algorithms (centrality + helper families),
one class method, and one graph mutation helper. All exercised against
`networkx 3.6.1` and `franken_networkx` HEAD.

| API | Kind | fnx vs nx | Notes |
|---|---|---|---|
| `wheel_graph(8)` | generator | ✅ match | identical node/edge set |
| `harmonic_centrality(path_graph(6))` | algorithm | ✅ match | value-level equality within 1e-9 |
| `set_node_attributes(path_graph(4), {0:"a",1:"b"}, name="color")` | helper | ✅ match | identical attribute map |
| `MultiDiGraph.in_edges(node=2, keys=True)` | class method | ✅ match | identical edge tuple set (class attribute is `cached_property`; signature introspection uses `inspect.signature` on the instance) |
| `load_centrality(path_graph(6))` | algorithm | ✅ match | value-level equality within 1e-9 |

All 5 probes pass. Extended 20-API sweep run alongside as a bonus sanity
check (`density`, `degree_histogram`, `reciprocity`, `is_empty`,
`number_of_isolates`, `common_neighbors`, `non_neighbors`, `relabel_nodes`,
`convert_node_labels_to_integers`, `to_dict_of_lists`,
`from_dict_of_lists`, `edges`, `is_tree`, `is_forest`, `girth`, `triangles`,
`articulation_points`, `bridges`, `degree_centrality`): all 20 match.

## Genuine Gaps Found This Pass

### `franken_networkx-1uoos` — shortest_path(G) arg-less return type

- **Severity:** MEDIUM
- **Symptom:** `fnx.shortest_path(G)` (no `source`, no `target`) returns
  a nested dict-of-dicts, whereas `nx.shortest_path(G)` returns a generator
  yielding `(source, paths_dict)` pairs (it delegates to
  `nx.all_pairs_shortest_path` / `_dijkstra_path` / `_bellman_ford_path`
  per `method`).
- **Impact:** Callers iterating the result, calling `next()`, or feeding
  it to APIs expecting a generator saw a `dict_items`-like surprise or
  silently-different ordering semantics. `shortest_path_length(G)` was
  already correct; `shortest_path(G, target=x)` was already correct.
- **Fix shipped this session:** wrapper at
  `python/franken_networkx/__init__.py:1840` checks `source is None and
  target is None` and converts the Rust-returned dict to a generator of
  `(src, paths)` pairs before returning.
- **Regression test:** `tests/python/test_coverage_gaps.py::TestShortestPathVariants::test_shortest_path_argless_returns_generator`.

No other gaps found across the 25 probes run this session.

## Unsurprising Findings (worth recording)

- `fnx.MultiDiGraph.in_edges` is a method on instances but a
  `cached_property` descriptor on the **class**. Attempts to inspect it via
  `cls.in_edges.fget` fail; use `inspect.signature(instance.in_edges)` or
  access as a bound method. This mirrors networkx's own usage pattern and is
  not a bug.
- `fnx` exposes 1023 top-level names vs nx's 944 — the extra ~80 are
  fnx-specific additions (e.g., the CGSE / durability / dispatch helpers
  carried in `__all__`) plus some re-exports. `__all__` intentionally
  advertises only 801 of them.

## What Works (high-confidence)

- Drop-in replacement contract: every nx public callable is reachable.
- Zero delegates to networkx at runtime per coverage gate.
- 3967-test parity suite green.
- 4 graph classes (`Graph`, `DiGraph`, `MultiGraph`, `MultiDiGraph`) with
  unified mutation + algorithm dispatch.
- Backend-mode registration in package metadata (`backend.py`).
- 107 native Rust exports covering the hot algorithm paths
  (shortest path, connectivity, centrality, clustering, matching, flow,
  spanning trees, Euler, DAG, traversal, link-prediction, community core,
  distance, efficiency, boundary, clique, isolates, bipartite recognition,
  core-number, predicates).

## What's Missing / Surprising

- **[MEDIUM][1uoos]** `shortest_path(G)` return type (fixed inline this
  session).
- **[family-level, tracked in FEATURE_PARITY.md]** Bipartite projections,
  community detection beyond the 4 native variants, and current-flow
  centrality are still Python-layer implementations rather than native Rust.
  These are `PY_WRAPPER`s rather than `NX_DELEGATED` — i.e., they are
  functional but slower than the native hot paths. Tracked as
  in_progress family items in `FEATURE_PARITY.md`, not separate beads.
- **[non-defect]** Hand-authored mock finders (2026-04-22
  `audit_networkx_reality.md`) list `fnx-algorithms/src/test_dijkstra.rs:11`
  and a topo-sort placeholder in `fnx-conformance/src/lib.rs:2336`; these
  are test scaffolding / fixture placeholders, not production mocks.

## Dependency Status (cross-reference)

Per the 2026-04-23 `UPGRADE_LOG.md` sweep: every external direct dep in the
main workspace is pinned to its current crates.io latest stable. `asupersync`
remains pinned at `0.3.1` in `Cargo.lock`. 0 bumps available.

## Bottom Line

FrankenNetworkX **meets its stated vision** as a drop-in NetworkX
replacement at the API-surface level. Zero runtime delegates, full
callable parity, and a 3967-test parity suite in the green. One real
return-type divergence was found and fixed inline during this pass. The
remaining work sits at the **performance parity** layer
(`PY_WRAPPER` → `RUST_NATIVE` rewrites) rather than the functional-parity
layer.

---

## Reality check 2026-10-04

### Verdict and evidence boundary

FrankenNetworkX is a substantial, usable graph library, not a scaffold. It does
not yet deliver the complete conjunction of NetworkX-observable compatibility,
native execution, incumbent-beating end-to-end performance, comprehensive CGSE
witnesses, hardened resource safety, and release-bound durable evidence.
Neither API coverage nor a closed-bead percentage measures that conjunction.

This audit read the complete suite AGENTS.md, repository AGENTS.md, README.md,
all six active planning documents, the zero-copy and integer-adjacency design
notes, SECURITY.md, and the historical reality/bridge reports. Implementation
inspection covered graph classes/bindings, representative public wrappers,
backend dispatch, runtime policy, CGSE, conformance, durability, packaging,
Python runners, SLO workloads, and the installed DSR gate implementation.
Keyword and Rust AST scans found no `todo!` or `unimplemented!` calls in the
examined core source directories; this is not an exhaustive proof of absence
of unfinished behavior. Idempotent runtime adapter no-ops are not stubs.

Snapshot: main at `ceac89454af2ffaddffdd708b4945def7525e5bd`, with peer changes
already present in digraph.rs, __init__.py, view tests, tracker files, and an
untracked preflow_push.rs. Those changes were preserved. Python probes loaded
CPython 3.14.3, NetworkX 3.6.1, editable fnx 0.2.3, and this extension:

```
/data/projects/franken_networkx/python/franken_networkx/_fnx.abi3.so
sha256 a595804fcb1f92e4de647dd1b1861488bff5e298fd53b9e543a6e84bb7926a55
```

The loaded extension's relationship to the dirty Rust source was not certified.
Source inspection, this editable installation, the published 0.2.3 wheels, and
historical DSR receipts are separate evidence classes throughout this report.

### Numbered vision checklist

`WORKING` below means the stated bounded workflow was exercised; it does not
mean every input or platform passed. `PARTIAL` describes implemented but
incomplete capability; `UNPROVEN` means the full claimed acceptance is missing.

| # | Testable goal and source | Status | Evidence and remaining gap | Existing coverage |
|---|---|---|---|---|
| 1 | Standalone analytics and NetworkX backend, README quick start/tutorial | WORKING, bounded | Four graph types passed weighted path + weight mutation + node-link JSON round trip. Explicit nx backend path returned the same path. Karate PageRank, Louvain, diameter and GraphML round trip completed with two Rayon threads. | hhj5p.1, sfq4w.2, wvztf.5 |
| 2 | Full scoped NetworkX observable semantics, README compatibility; spec sections 4/15 | PARTIAL | Shallow copy topology/attribute aliasing differs; 3/12 flow dictionaries differ despite equal optimum; active iterator/view/order/float issues remain. | copyshare-2h5uj, yr2oc.3, uh5ua, himzq, u5tyh, hrejw, ygt3z, vbjbk |
| 3 | Honest API and execution ownership, README coverage/native notes | PARTIAL | 843 exports and 315 registered backend algorithms measured. README's 4,129 applicable declaration rows are not behavioral tests. NetworkX callbacks and SciPy routes remain; broad "zero delegates" is false today. | vbneu.2, sfq4w.4/.6, 8813x.2 |
| 4 | Native Rust kernels with safe core interfaces, AGENTS architecture/unsafe rule | WORKING substrate; PARTIAL ownership | Real Rust implementations and `forbid(unsafe_code)` in all 11 core crate roots. Public PageRank uses SciPy iteration; simple_cycles delegates; Python and dependency internals are not proven by the core unsafe ban. | sfq4w.4/.6, 1g0lj |
| 5 | CGSE canonical policies and per-family complexity witnesses, README CGSE; spec sections 7/14 | PARTIAL | Registry has 12 reference algorithms. Loaded public BFS emitted one witness; SCC, Prim, weighted source-target shortest_path and max_weight_matching emitted none in these probes. Collection is opt-in. Wider families remain unfinished. | csmqh.1, bieu0.1/.2, wvztf.3 |
| 6 | Fresh live-oracle conformance and replayable schemas, spec sections 8/15/19 | PARTIAL | Rust fixture harness, Python parity suites and upstream ratchet are real. Frozen fixture freshness/schema/public-route equivalence still need release-bound acceptance. Passing a fixture test alone does not establish live-oracle freshness. | csmqh.3, hhj5p.1 |
| 7 | Strict/hardened parsing with bounded, visible recovery, README modes; spec section 5 | WORKING bounded; UNPROVEN universal safety | Strict rejected a malformed edge-list row; hardened retained two valid edges, warned, and logged recovery. Algorithm kernels do not yet branch on mode. Under 2 GiB address space, diameter raised a Rayon initialization PanicException; two threads resolved this diagnostic. | Closed 9a8bo/nro4w.10 cover reader exposure; new resource follow-up needed |
| 8 | Performance SLOs at declared scale with live incumbent, spec section 17 | UNPROVEN | Component workload is 20 paths of 250 nodes (4,980 edges), not a million-edge graph; shortest-path workload is an unweighted 90x90 grid. The SLO worker times fnx alone. No new speedup claim is made on this busy host. | csmqh.4, vbneu.4, p80x1 |
| 9 | Efficient storage, views, mutation, and memory, README performance; AGENTS performance loop | PARTIAL | Dense adjacency and caches exist; duplicate stores, exposure-dependent fast-path losses, view/mutation costs and shallow-copy architecture remain. Historic 3.4x attributed-memory cost is not a fresh measurement here. | sfq4w.1/.3, yr2oc.1/.3, 49u7h, igdzi, 9iii7 |
| 10 | RaptorQ coverage of all five required artifact classes, AGENTS durability; spec section 9 | PARTIAL | Encoder, scrub recovery, bounded decode drills and proof types are real. Summary sidecars do not prove every fixture/baseline/manifest/ledger/snapshot is covered, nor that released evidence is repaired/replayed. | csmqh.2 |
| 11 | Fail-closed, version-controlled, source-bound DSR gates, AGENTS authority; spec section 18 | PARTIAL | Host selects nine checks; committed registration selects four. Dry run executes zero checks. Live run is not green. Installed DSR source snapshot hashes Git porcelain path/status output, not dirty file contents, and does not bind the editable extension's bytes. | hhj5p.1; new exact-candidate proof follow-up needed |
| 12 | Installable six-platform wheels and source archive, README distribution/DSR | PARTIAL, shipped wheels | Public PyPI 0.2.3 has six wheels and no sdist. Root LICENSE omission blocks the source archive. Packaged fnx-conformance oracle embeds a file outside its crate boundary. Availability is not requalification of this dirty checkout. | euaqe is broad shipping coverage; concrete packaging follow-ups needed |
| 13 | Explicit Python/NetworkX version contract, README ABI3; pyproject dependencies | UNPROVEN beyond pinned lane | ABI3 tags establish an ABI floor, not behavioral parity across CPython 3.10-3.14. Metadata permits NetworkX >=3.4 without an upper bound; 3.7 null-graph/API removals and older-CPython summation need separate qualification. | vbjbk is a different 3.14 tolerance-polish scope; concrete version follow-ups needed |

Bead shorthand is the unique suffix of an ID beginning `br-r37-c1-`; full IDs
remain authoritative in `.beads/issues.jsonl` and `br show`.

### Runtime observations (diagnostics, not replacement quality gates)

Probes used `ulimit -v 2097152`, 90-120 second timeouts, and one OpenBLAS/OMP
thread. The final tutorial also set `RAYON_NUM_THREADS=2`. All data and I/O were
in memory; no scratch-file cleanup or package/environment mutation was needed.

1. Graph, DiGraph, MultiGraph, MultiDiGraph: a->b->c->d weighted path matched;
   changing a-b weight to 4.0 changed shortest distance to 7.0 in both libraries;
   node-link JSON round-trip payload equality passed for all four classes.
2. `copy.copy`: adding a node or changing an edge weight through the copy affected
   NetworkX's original, but not fnx's original. This confirms existing copyshare
   work, not a new duplicate bug. A first probe typo used a multiedge key for a
   simple graph; that probe error was corrected and is not a product finding.
3. Twelve independently constructed 8-node directed flow twins, seeds 0-11,
   capacities 1-9, edge probability .32: seeds 1, 3, 6 had unequal complete flow
   dictionaries and equal flow values. Matching only the optimum is insufficient
   for the documented observable contract. uh5ua already owns this repair.
4. `from franken_networkx._fnx import cgse` is the documented CGSE import. With
   `collect_witnesses`, BFS emitted `(insertion_order, 5, n_plus_m)`; the four
   public routes named in checklist row 5 emitted zero. An initial diagnostic
   incorrectly tried `fnx.cgse`; that import mistake is not a product defect.
5. Malformed edge-list `a b / lonely / b c`: strict raised OSError; hardened
   produced edges a-b,b-c, a RuntimeWarning and a full_validate recovery record.
6. Karate workflow: both libraries produced 34 nodes, 78 edges, diameter 5,
   the same four sorted Louvain communities (seed 7), PageRank sum
   0.9999999999999999, and GraphML round-trip counts 34/78. This checks values and
   counts, not byte-identical XML serialization or every PageRank entry.
7. Before limiting Rayon threads, diameter on that small tutorial graph raised
   `PanicException: ThreadPoolBuildError ... Resource temporarily unavailable`
   under the 2 GiB limit. The same bounded workflow completed with two threads.
   This is a resource-constrained failure, not evidence of default-host failure.

### DSR and historical evidence

Audit command: `timeout --signal=TERM --kill-after=20s 1200s dsr quality --tool
franken_networkx`. Its bounded runtime is an audit limit, not a product gate
relaxation. Logs are retained at:

```
/home/ubuntu/.local/state/dsr/quality-logs/franken_networkx/20261004T184758-3679903/
```

The run finished in 1,021,301 ms (about 17 minutes), exit 1, before the audit
timeout. Its receipt reports **invalidated-moving-source**, nine executed
command invocations, four passed and five failed. Executed commands do not
mean their tests reached execution:

| Check | Result | What this actually establishes |
|---|---|---|
| 1 fmt | FAIL, exit 1 | Peer digraph.rs formatting delta; not repaired by this audit. |
| 2 check | FAIL, exit 1 | hz4 source transfer timed out before remote Cargo started; no compiler result. |
| 3 Clippy | PASS | Workspace/all-targets diagnostic completed through DSR. |
| 4 Rust tests | PASS | 11 core crates; 1,806 reported passes, zero failures, 246 ignored across 62 terminal groups; ovh-a. Not fnx-python/complete Python parity. |
| 5 fuzz replay | PASS | 33 targets, zero failures, 367.4 CPU-seconds; bounded fuzz exercise, not exhaustive safety proof. |
| 6 docs | PASS | 22 Markdown documents and four examples; not universal truth verification of README claims. |
| 7 guarded Python smoke | REFUSED, exit 4 | Extension older than Rust sources; zero tests ran. |
| 8 upstream NetworkX | REFUSED, exit 1 | Same stale-extension guard; no current upstream suite count. |
| 9 complete Python parity | REFUSED, exit 1 | 1,114 files enumerated into 28 shards; every shard returned nonzero before tests. Zero passed/failed is zero executed, not green. |

No direct Cargo/RCH quality path was invoked by this audit. No gates were
removed, repaired, or weakened. The current Python failure is an admission
refusal, not newly measured assertion failures. The earlier bounded probes
remain diagnostic observations of the identified stale editable installation.

A genuine historical nine-check PASS receipt exists at
`20260924T135151-356076/receipt.json`, source
`9298c0816691d05970f706d50c436ee9fca45658`. It records 33 fuzz targets with zero
failures, 267 guarded tests passed/1 skipped, upstream 6,815 passed/80 skipped,
and 68,372 Python tests passed/1,505 skipped/29 xfailed across 1,103 files.
These counts differ from the README's other historical snapshot and do not
qualify October 4 source. The neighboring failed/planted-failure and
invalidated-moving-source receipts are negative evidence, not competing green
receipts to cherry-pick. A live check failure caused by transfer infrastructure
is not a compiler-error diagnosis.

New report/tracker edits can themselves change DSR's source-status snapshot;
any moving-source aggregate must remain invalid. The snapshot implementation
also misses content changes that leave the same dirty paths/statuses, which
requires an upstream DSR/integration fix rather than pretending the current
receipt certifies exact source bytes.

### Shipped reality and external follow-ups

Verified live on October 4: [PyPI 0.2.3](https://pypi.org/project/franken-networkx/0.2.3/)
lists six wheels uploaded October 3 and no source distribution. The GitHub
[0.2.3 release](https://github.com/Dicklesworthstone/franken_networkx/releases/tag/v0.2.3)
exists at cec922a. This is a real shipped product, not a claim that HEAD is
unreleased everywhere or that all release/vision gates passed.

- [Issue 7](https://github.com/Dicklesworthstone/franken_networkx/issues/7):
  the signed source archive declares a root LICENSE missing from the archive;
  PyPI rejected it. Fix the recipe and use a new version; preserve immutable
  0.2.3 assets, signatures, and tag.
- [Issue 6](https://github.com/Dicklesworthstone/franken_networkx/issues/6):
  optional `feature_behavioral_oracle` embeds a repository-level script outside
  fnx-conformance's package boundary. Workspace compilation does not prove the
  extracted registry binary builds. This is not a demonstrated default-library
  regression.
- [Issue 5](https://github.com/Dicklesworthstone/franken_networkx/issues/5):
  pinned NetworkX 3.6.1 and newer 3.7 are different qualification lanes; null-graph
  eccentricity behavior and removed APIs need deliberate version-aware tests.
- [Issue 4](https://github.com/Dicklesworthstone/franken_networkx/issues/4) and
  current CHANGELOG retain incomplete full-parity evidence and exact arithmetic
  limitations. Its old "release blocked" title predates the actual publication;
  it is failure provenance, not evidence that 0.2.3 is absent from PyPI today.

This audit did not publish, replace, install or rebuild release artifacts.
It did not independently authenticate/download all public wheel bytes; public
listing and issue evidence must not be inflated into a new DSR verification.

### Coverage of the work graph

Initial JSONL inventory: 3,853 records, 3,757 closed, 50 open, 41 in progress,
5 blocked. `br ready --json` returned 37 records. BV agreed with the 96 remaining
records and detected no cycles; `br dep cycles --json` returned zero cycles.
Doctor was degraded only on stale recovery artifacts/warnings, not a diagnosed
JSONL/database corruption; no repair or cleanup was attempted.

Existing work covers most algorithm/view/storage/native/performance gaps.
Completing the existing 96 records **would not alone prove the whole vision**:
specific package-boundary, version-lane, resource-failure, and exact-source
acceptance were missing, several old descriptions allow de-scoping/deletion,
and the shipping node does not enforce the full V1 evidence conjunction.
Closed-state counts and BV's ETA are not delivery proof. Its initial estimate
was 11,745 work-minutes with average confidence .464, not a release commitment.

### Bridge plan: preserve scope, make acceptance real

| Wave | Work | Proof required before that wave is called complete |
|---|---|---|
| A: immediate truth and reproducibility | Complete hhj5p.1 configuration convergence; bind evidence to source/extension bytes; fix the concrete source-package and version-lane gaps. Keep runtime delegation and historical receipts labeled. | Frozen source/content/lock/config/interpreter/oracle/ELF manifest; negative stale-artifact and same-dirty-path probes; fully classified DSR inventory. |
| B: exact observable behavior | Existing uh5ua, copyshare, multigraph mirrors, iterator exhaustion, held-row and float work, plus older-CPython arithmetic and NetworkX 3.7 qualification. | Unit + guarded differential tests preserve result types, full dictionaries, aliases, exception precedence, ordering and appropriate numeric contracts; a terminal complete suite in each admitted lane. |
| C: structural speed and memory | Existing authoritative attribute store, tombstones/generational indices, copy sharing, exposure-coherent views, bulk backend conversion and routing; remaining native families. | Before/after complete-result equality; live NetworkX in the same invocation; cold/warm/cache-off and touched/untouched histories; memory and adversarial-scale curves. No self-speedup promoted to incumbent win. |
| D: crown jewels and security | Existing csmqh.1/.3 public witnesses/live oracle, bieu0 family coverage, csmqh.2 all required durable bundles, csmqh.4 real SLO scale; resource-failure handling. | Public route witnesses and bound negatives; fresh oracle/schema checks; recovery at admitted packet loss and failure beyond it; explicit resource refusal without panic; spec-scale live-incumbent SLO results. |
| E: release/system closure | Extend existing euaqe acceptance and explicit graph blockers for the full V1 claim, while keeping ordinary 0.x availability distinct. | DSR-bound wheel/sdist and crate packaging checks, clean-environment six-platform/interpreter smoke, public hash verification, durable evidence bundle. No release mutation in this audit. |

Tests remain inside their owning implementation beads, as required by the
suite's no-scope-splitting rule. A separate system acceptance node may check
cross-component delivery but cannot substitute for any implementation proof.
Append new evidence to existing beads instead of duplicating their owned work.

### Planning protocol and refinement record

The following skill templates govern the graph changes in this audit. They are
retained verbatim; suite authority overrides their generic suggestion to split
tests into separate implementation companions.

Phase 3a:

```
OK so please take ALL of that and elaborate on it and use it to create a comprehensive and granular
set of beads for all this with tasks, subtasks, and dependency structure overlaid, with detailed
comments so that the whole thing is totally self-contained and self-documenting (including relevant
background, reasoning/justification, considerations, etc.-- anything we'd want our "future self" to
know about the goals and intentions and thought process and how it serves the over-arching goals of
the project.) The beads should be so detailed that we never need to consult back to the original
markdown plan document. Remember to ONLY use the `br` tool to create and modify the beads and add
the dependencies.
```

Phase 5 (applied at each refinement round):

```
Check over each bead super carefully-- are you sure it makes sense? Is it optimal? Could we change
anything to make the system work better for users? If so, revise the beads. It's a lot easier and
faster to operate in "plan space" before we start implementing these things! DO NOT OVERSIMPLIFY
THINGS! DO NOT LOSE ANY FEATURES OR FUNCTIONALITY! Also make sure that as part of the beads we
include comprehensive unit tests and e2e test scripts with great, detailed logging so we can be
sure that everything is working perfectly after implementation. Make sure to ONLY use the `br` cli
tool for all changes, and you can and should also use the `bv` tool to help diagnose potential
problems with the beads.
```

### Three ambition passes: concrete deltas

1. Applied the skill's "That's a decent start but ... light years away from
   being OPTIMAL ... revise ... in-place" escalation. The initial package and
   version fixes were insufficient: added a source-to-loaded-ELF-to-public-bytes
   identity chain, because an unchanged dirty pathname digest can hide source
   movement. This became hhj5p.8, not a claim that the defect was fixed here.
2. Applied "That's a lot better than before but STILL ... far cry from being
   OPTIMAL ... MUCH, MUCH, MUCH better". Preserved the structural storage lever
   and required construction/touch/copy/delete histories, public parameter-route
   witnesses, cold/warm full-job cost, original SLO scale, and all five artifact
   classes. Existing implementation beads received these acceptance notes; no
   duplicate micro-optimization campaign or optional de-scope path was added.
3. Applied the domain-depth "Now, TRULY think even harder ... REALLY RUMINATE
   ON THIS!!! DIG DEEP!!" escalation. Refined equivalence from final graph
   isomorphism to observable execution traces: labels, insertion/set order,
   aliases, mutations, generator state and interpreter arithmetic. Differential
   shrinking must preserve the triggering trace. Statistical shared-host work
   must prove its assumptions/calibration without bypassing admission. Added
   the installed cross-component acceptance journey, joining actual feature
   evidence rather than substituting another count or schema for delivery.

### Refinement ledger (same frozen Phase 5 prompt each round)

| Round | Finding and actual revision |
|---|---|
| 1 | Added explicit unchecked positive/negative acceptance items to all six new repair beads; kept unit/integration/E2E tests and retained logging inside each implementation bead. |
| 2 | Added real blocking edges to the installed V1 journey while leaving independent repairs ready. Shipping depends on source-license and artifact-identity repair; optional oracle packaging is a full-V1 requirement, not a fabricated default-library regression. Corrected a rejected bieu0 prefix typo; no dangling edge was created. |
| 3 | Promoted mandatory CGSE, durability and spec-scale SLO work to P1; ruled out de-scoping/deletion as a substitute for implementation. Clarified constrained-resource controls, version admission and stale-ELF refusal versus source-content proof. |
| 4 | Attached final DSR negative evidence. Read back all seven new descriptions and checked exact preservation, acceptance fields, open states and dependencies. Exported JSONL and verified BV agrees with its 3,860 records. |
| 5 | Found missing semantic/complexity prerequisites: C-level multigraph dict serialization, held rows, equal-label identity, community set order, dense deletion indices and empirical complexity. Added existing owned nodes, not new duplicates. Preserved the pre-existing 49u7h/5cqna performance dependency and flagged it for owner review. |
| 6 | Rechecked coverage, negative cases, ownership, scope, dependency direction, independent readiness and evidence classes. No further revision needed. `br dep cycles` with and without closed nodes both returned zero; six new repairs are ready and V1 acceptance is not ready. |

### Concrete new work (all remain open; none implemented by this audit)

| Full Bead ID | Priority | Self-contained scope |
|---|---|---|
| br-r37-c1-rc0923-epic-evidence-authority-hhj5p.5 | P1 | Root/license metadata correctness in wheel/sdist, negative published-archive probe, isolated source build. |
| br-r37-c1-rc0923-epic-crown-jewels-csmqh.5 | P2 | Extracted registry oracle package builds and executes without an ancestor repository script. |
| br-r37-c1-rc0923-epic-evidence-authority-hhj5p.6 | P1 | Separate NetworkX 3.7 behavior/ledger qualification and explicit admitted version range. |
| br-r37-c1-rc0923-epic-evidence-authority-hhj5p.7 | P1 | Same-interpreter exact mixed-weight degree/projection/modularity arithmetic on CPython 3.10-3.14. |
| br-r37-c1-rc0923-epic-crown-jewels-csmqh.6 | P1 | Predictable bounded-memory/thread admission without a Rayon PanicException or poisoned later calls. |
| br-r37-c1-rc0923-epic-evidence-authority-hhj5p.8 | P0 | Actual source-content and loaded-artifact candidate identity across DSR subprocesses and packaged/public bytes. |
| br-r37-c1-rc0923-epic-evidence-authority-hhj5p.9 | P1 | Installed end-to-end semantics, backend, public witnesses, mode/resource behavior and durable replay on one candidate; dependency-blocked on concrete implementations. |

Existing beads received evidence/acceptance notes rather than duplicate tasks:
hhj5p.1, euaqe, csmqh.1/.2/.4, sfq4w.1, 8813x.2, wvztf.1 and vbneu.4.
No existing statuses/assignees changed and no bead was closed. New definitions
include rationale, code surfaces, named probes, unit/differential/E2E testing,
failure diagnostics, source/artifact provenance and safety constraints.

Final JSONL/BV inventory: 3,860 total, 3,757 closed, 57 open, 41 in progress,
5 explicitly blocked; 103 not closed. `br ready` returns 43, including the six
new independent repairs but excluding hhj5p.9. BV's graph source is the SQLite
materialization and its counts agree with authoritative JSONL. Its full
insights cycle metric skips graphs over 2,000 nodes, so the independent `br dep
cycles --include-closed --json` result, not a skipped BV metric, supplies the
complete-graph zero-cycle check.

### Handoff and next action

First address hhj5p.8's exact artifact identity and hhj5p.1's DSR configuration,
then let the owners repair/rebuild their current candidate through DSR and run
the guarded Python gates. Preserve the current stale-ELF refusals as evidence;
do not touch timestamps, override freshness or fix peer files to obtain green.
In parallel, implement the package/version/resource repairs and existing
flow/copy/view work. Attack attributed storage/backend whole-job losses before
widening isolated wins. Full V1 acceptance waits on the explicit graph.

This completes the reality-check skill through an evidence-backed bridge plan,
Beads generation, three ambition passes, six refinement passes and BV/BR graph
validation. It does **not** complete the product, certify the current Python
suite, authenticate every released asset, or implement the open repairs.
Only this historical audit document and owned tracker changes are publication
scope. Peer source, unrelated tracker changes, WAL certificates and recovery
artifacts are intentionally left alone; no file deletion or cleanup occurred.
Publication checks include whitespace validation and JSONL record/scope checks.
The UBS pre-commit attempt returned exit 3 (nothing scanned): Markdown and Beads
JSONL are not scanner-eligible code. This is not a UBS pass, and no no-scan
override was used. No product source was changed by this audit.

---

## Reality check 2026-10-13

### Verdict and delta since 2026-10-04

Nine commits landed on `main` since `250f575aa` (`2026-10-04`):
1. `749ec366a fix(packaging): ship and verify declared licenses` (`hhj5p.5` — closed)
2. `fd249a775 feat(cgse): observe public path and SCC kernels` (`csmqh.1`)
3. `b9001299e feat(cgse): expose bounds and observe public BFS` (`csmqh.1`)
4. `fe6cb4bd1 feat(cgse): observe multigraph shortest paths` (`csmqh.1`)
5. `cdb77b609 fix(dsr): bind wheels to source contents` (`hhj5p.8`)
6. `92125f57c fix(dsr): guard config topology during verification` (`hhj5p.8`)
7. `88ec83296 fix(algorithms): survive worker pool refusal` (`csmqh.6`)
8. `7f2aa2295 fix(algorithms): admit workers before thread creation` (`csmqh.6`)
9. `1013bc156 fix(python): honor interpreter summation policy` (`hhj5p.7`)

However, between `2026-10-05` and `2026-10-13`, **48 modified working-tree files (`+14,169 / -3,804` lines)** and **2 untracked source files** (`crates/fnx-algorithms/src/preflow_push.rs`, `crates/fnx-conformance/src/behavioral_oracle.py`) accumulated across **19 `in_progress` beads** without rebuilding the editable native extension (`python/franken_networkx/_fnx.abi3.so`) or committing completed units. All three compiled shared libraries on disk (`python/franken_networkx/_fnx.abi3.so`, `target/release/lib_fnx.so`, `target/maturin/lib_fnx.so`) remain frozen at `2026-10-04T21:25:29Z` (`sha256: a595804fcb1f92e4de647dd1b1861488bff5e298fd53b9e543a6e84bb7926a55`).

Because `python/franken_networkx/__init__.py` is imported live from the dirty working tree while `_fnx.abi3.so` predates all 9 commits and all 48 dirty files:
- **Live regression in `scripts/verify_docs.py`:** `python3 scripts/verify_docs.py` (which passed on `2026-10-04`) **FAILS today (`exit 1`)** on `docs/quickstart.md` with `TypeError: edge_betweenness_centrality() got an unexpected keyword argument 'source_aware'` because `python/franken_networkx/__init__.py:33579` passes `source_aware=source_aware` to `_raw_edge_betweenness_centrality` (added in working-tree `crates/fnx-python/src/algorithms.rs` for `csmqh.6`, absent from the Oct 4 `.so`). Under `ulimit -v 4194304`, `verify_docs.py` also hits `MemoryError` on `README.md`'s 50,000-node `barabasi_albert_graph(50_000, 5, seed=7)` snippet.
- **Missing native symbols in loaded `.so`:** Working-tree `python/franken_networkx/__init__.py` references `_fnx.copy_readwrite_policy` and `_fnx.validate_graphml`, both absent from the loaded `.so` (`hasattr(_fnx, "copy_readwrite_policy") == False`).
- **Guarded Python suites remain refused:** `scripts/run_pytest_guarded.sh`, `scripts/run_upstream_networkx_suite.py`, and `scripts/run_python_parity_suite.py` all refuse at `tests/python/conftest.py` (`exit 4` / `exit 1`) because `_fnx.abi3.so` is older than `crates/*/src/**/*.rs`.
- **Zero green DSR quality runs since 2026-09-24:** Of the 4 canonical `dsr quality --tool franken_networkx` runs since `2026-10-04`, two (`20261004T184559-3638043`, `20261010T230954-3126900`) were `dry_run: true` (`0` executed checks), `20261004T184758-3679903` failed 4 of 9 checks, and `20261004T224959-886382` ended `invalidated-moving-source` with 5 of 9 checks failed.

### Numbered Vision Checklist (2026-10-13)

| # | Testable goal and source | Status (2026-10-13) | Code & Runtime Evidence (`file:line` and live probes) | Existing Bead(s) |
|---|---|---|---|---|
| 1 | **Standalone analytics & NetworkX backend** (`README.md` Quick Start / Tutorial; Spec §4) | **PARTIAL (Quickstart doc script broken by stale `.so`)** | Weighted `dijkstra_path`, weight mutation, `node_link_data`/`node_link_graph` JSON round-trip on all 4 graph classes and `nx.shortest_path(..., backend="franken_networkx")` pass in live probes. **Regression:** `scripts/verify_docs.py` fails on `docs/quickstart.md` (`edge_betweenness_centrality()` unexpected kwarg `source_aware` against Oct 4 `.so`). | `hhj5p.1`, `hhj5p.10` (new), `sfq4w.2`, `wvztf.5` |
| 2 | **Full scoped NetworkX observable semantics** (`README.md` Compatibility; Spec §§4, 15) | **PARTIAL** | Working-tree Python fixes `json.dumps(fnx.to_dict_of_dicts(mg))` (`5cqna`, `__init__.py:69901-69910, 71710-71755`) and `hasattr(g.to_directed(as_view=True)[0], 'copy')` (`o1z03`, `__init__.py:57920-58089`). Still broken/unwired: (a) `copy.copy(G)` clones structure & dicts in O(V+E) (`crates/fnx-python/src/lib.rs:14553, 20667`; `digraph.rs:9903, 19121`), with false `is`-identity docstrings at `digraph.rs:9900, 19118`; (b) `maximum_flow` disagrees with `nx` on 3/12 directed 8-node twins (seeds 1, 3, 6) while `crates/fnx-algorithms/src/preflow_push.rs` (1,038 lines) sits untracked and unwired into `crates/fnx-algorithms/src/lib.rs`; (c) custom hashable Python node objects with `a == b` and `hash(a) == hash(b)` but different `__repr__` split into two nodes at `crates/fnx-python/src/lib.rs:1119` (`"obj:{hash}:{repr}"`). | `yr2oc.3`, `yr2oc.5` (new), `uh5ua`, `ygt3z`, `5cqna`, `o1z03`, `gue3i`, `pgpg1`, `8xp4a`, `u8rs5`, `cqb4b` |
| 3 | **Honest API, coverage & delegation ownership** (`README.md` Coverage / Delegation; `docs/coverage.md`; `docs/delegation_ledger.md`) | **PARTIAL (Stale docs & uncommitted ledger)** | Runtime has `843` exports in `fnx.__all__` and `315` algorithms in `backend._SUPPORTED_ALGORITHMS`. Working-tree `scripts/delegation_ledger.py` (`+962` lines, `vbneu.2`) combines AST reachability + `sys.monitoring` runtime frame census, but `docs/delegation_ledger.md` was not regenerated. `README.md` falsely claims `313` backend algorithms (6 places), `839` exports (`line 2743`), and claims weighted `louvain_communities`, `matching`, `branchings`, and `greedy_modularity_communities` delegate to NetworkX (`lines 802, 1194, 1261, 2319, 2377, 2684`) despite native ports (`3eedb37ea`, `bd91d3f35`, `7f414a723`). | `vbneu.2`, `8813x.2`, `8813x.4` (new), `sfq4w.4`, `sfq4w.6` |
| 4 | **Native Rust kernels & `#![forbid(unsafe_code)]`** (`AGENTS.md`; `README.md` Architecture) | **WORKING substrate; PARTIAL ownership** | All 11 workspace crates enforce `#![forbid(unsafe_code)]`; `crates/fnx-algorithms/src/` is `100,170` lines (`704` `pub fn`s). `simple_cycles` and `k_components` still delegate to NetworkX (`sfq4w.4`), and `76,280`-line `python/franken_networkx/__init__.py` remains a monolithic God file (`8813x.3`). | `sfq4w.4`, `sfq4w.6`, `8813x.3`, `1g0lj` |
| 5 | **CGSE canonical policies & complexity witnesses** (`README.md` CGSE; Spec §§7, 14) | **PARTIAL (Policy conflict + missing routes + stale `.so`)** | Commits `fd249a775`, `b9001299e`, `fe6cb4bd1` and dirty `crates/fnx-algorithms/src/lib.rs:14159-14167` / `crates/fnx-python/src/algorithms.rs:5852, 7602, 16050, 16253` add witnesses for SCC, unweighted bidirectional BFS, MultiGraph shortest path, unit-weight `dijkstra_path`, and simple-graph Prim — **none of which are in the loaded Oct 4 `.so`**. Even in Rust source: (a) `v1_policy_registry()` (`crates/fnx-cgse/src/lib.rs:475`) registers `Prim => WeightThenLex`, contradicting `prim_spanning_edges_indexed` (`crates/fnx-algorithms/src/lib.rs:14166`) which emits `WeightThenInsertionOrder`; (b) public `max_weight_matching`/`min_weight_matching` (`blossom.rs`), directed/multigraph `eulerian_circuit`, and `MultiGraph` `prim`/`kruskal` emit `0` witnesses; (c) 9 of 13 `TieBreakPolicy` enum variants have 0 callers outside unit tests. | `csmqh.1`, `bieu0.1`, `wvztf.3` |
| 6 | **Live-oracle conformance harness & fresh artifacts** (Spec §§8, 15, 19; Issue #6) | **PARTIAL / FAILING FRESHNESS** | Working tree extracts `crates/fnx-conformance/src/behavioral_oracle.py` (`2,691` lines untracked) and wires `include_str!("../behavioral_oracle.py")` + `--case-file` in `crates/fnx-conformance/src/bin/feature_behavioral_oracle.rs:12-31, 84-106` (`csmqh.5`, uncommitted). However, `python3 scripts/verify_conformance_freshness.py` **FAILS (`exit 1`, 12 errors)**: all 120 `artifacts/conformance/latest/*.report.json` files are from `2026-09-09` (34 days stale vs `__init__.py`), `conformance_dashboard_v1.json` is 156 days old (`2026-05-10`), and `structured_logs.jsonl` schema differs completely from `README.md:2352`. | `csmqh.3`, `csmqh.5`, `8813x.4` (new) |
| 7 | **Strict/hardened mode-split & bounded resource safety** (`README.md` Modes; `SECURITY.md`; Spec §5) | **PARTIAL (Uncommitted Rayon fixes; stale `SECURITY.md`)** | Commits `88ec83296`, `7f2aa2295` and uncommitted `crates/fnx-algorithms/src/lib.rs` + `crates/fnx-python/src/algorithms.rs` (`csmqh.6`) add worker-pool admission checks before Rayon thread creation and bounded-memory APSP chunks, but are not compiled into `_fnx.abi3.so`. `SECURITY.md:9-10, 37-45` falsely marks `< 1.0` unsupported (`:x:`) and links to non-existent `artifacts/cgse/v1/cgse_semantics_threat_model_v1.md` and `artifacts/docs/v1/...`. | `csmqh.6`, `8813x.4` (new) |
| 8 | **Performance SLO gates at Spec §17 scale with live incumbent** (Spec §17; `AGENTS.md` Rule 0.5) | **UNPROVEN / TOY-SIZED** | `artifacts/perf/slo_thresholds.json:7-104` and `scripts/run_perf_slo_gate.py:82-204` remain unchanged: unweighted `90x90` grid (`8,100` nodes) and `400`-node weighted path (`399` edges) instead of large sparse weighted; `20x250` components (`4,980` edges) instead of million-edge; `300`-node GNP PageRank; single `8x8` flow graph (`66` nodes); mean `ops_per_s` floor instead of `p95 regression <= +8%`; and **no `networkx` arm**. `scripts/perf_harness.py` is not wired into DSR and blocks on its 64-core host quiescence gate (`23` beads stalled). | `csmqh.4`, `vbneu.4`, `p80x1` |
| 9 | **Efficient storage, views, mutation & memory** (`README.md` Performance; `PROPOSED_ARCHITECTURE.md`) | **PARTIAL** | Core `remove_node(u)` in `fnx-classes` is O(deg(u)) across all 4 classes (`crates/fnx-classes/src/lib.rs:2947, 4241`; `digraph.rs:1910, 3960`), and working-tree `digraph.rs:206-270, 2451-2499` fixes `csr_cache`/`all_int_cache` `Arc<RwLock>` aliasing across clones. Remaining gaps: (a) dual/triple attribute storage (`inner` `AttrMap` + Python `node_py_attrs`/`edge_py_attrs`) causes ~3.4x attributed-memory blowup (`sfq4w.1`); (b) when `adj_py_keys`/`succ_py_keys`/`pred_py_keys` is non-empty (`0` vs `0.0`), `remove_node` runs a full O(E) `.retain(...)` scan (`crates/fnx-python/src/lib.rs:10183, 16854`; `digraph.rs:7008, 14868`); (c) alternating `remove_node` + `add_node` triggers O(V+E) `compact_before_growth()` on `Graph`/`DiGraph` (`lib.rs:2069, 3020`; `digraph.rs:1463, 1965`). | `sfq4w.1`, `sfq4w.3`, `yr2oc.1`, `yr2oc.3`, `yr2oc.5` (new), `49u7h`, `5cqna`, `8xp4a`, `u8rs5` |
| 10 | **RaptorQ sidecar durability across all 5 artifact classes** (`AGENTS.md` RaptorQ Contract; Spec §9) | **PARTIAL (Code uncommitted; repo sidecars stale/missing)** | Working-tree `crates/fnx-durability/src/lib.rs` (`+955/-23` lines, `csmqh.2`) adds `dropped_source_packets` source-loss decode drills (`lines 308-356, 678-834`), `validate_oti` preflight preventing `raptorq 2.0.1` `u8` source-block wraparound (`lines 200-204, 845-869`), and 5-class `release-bundle`/`verify-release-bundle` (`lines 107-146, 358-654`). In `artifacts/`, **0 of 29** `.raptorq.json` files contain `dropped_source_packets`, **9 of 11** in `artifacts/conformance/latest/` are byte-mismatched against their `2026-09-09` payloads, `bfs_percentiles.raptorq.json` is a 120-byte stub, and `migration_manifests` and `long_lived_snapshots` have **0** sidecars. | `csmqh.2` |
| 11 | **Fail-closed, version-controlled, source-bound DSR gates** (`AGENTS.md` DSR Only; Spec §18) | **PARTIAL (Config diverged; uncommitted evidence hooks)** | Commits `cdb77b609` and `92125f57c` bind candidate inputs, config topology, wheel members, and loaded `_fnx` ELF in `scripts/dsr_release_wheels.py:27-224, 448-598`; working tree adds `release_evidence` archive binding (`+140/-8` lines). However, `.dsr/repos.d/franken_networkx.yaml` (4 Rust checks + `release_contract` + `FNX_DSR_REQUIRE_EVIDENCE=1`) and `/home/ubuntu/.config/dsr/repos.yaml` (9 checks, no `build_cmd` or `release_contract`) are diverged in both directions. | `hhj5p.1`, `hhj5p.8`, `hhj5p.10` (new) |
| 12 | **Installable 6-platform wheels + sdist with `LICENSE`** (`README.md` Distribution; Issue #7) | **PARTIAL (Recipe fixed in `749ec366a`; PyPI `0.2.3` still lacks sdist)** | `hhj5p.5` (`749ec366a`) added `{ path = "LICENSE", format = "sdist" }` (`pyproject.toml:80-83`) and `validate_wheel_licenses`/`validate_sdist_licenses` (`scripts/dsr_release_wheels.py:282-304`). Public PyPI `0.2.3` remains wheel-only until `0.2.4` ships via DSR (`euaqe`). | `hhj5p.5` (closed), `euaqe` |
| 13 | **Explicit Python 3.10–3.14 & NetworkX 3.6/3.7 version contract** (`pyproject.toml`; Issue #5) | **PARTIAL (Commit `1013bc156` + uncommitted tests)** | Commit `1013bc156` (`hhj5p.7`) wired `PythonSum` into `crates/fnx-python/src/{lib.rs,digraph.rs}` to match interpreter `sum()` policy, and working tree adds `test_closeness_harmonic_identities.py` and `test_mixed_weight_degree_type_parity.py` (`hhj5p.6/.7`), but neither is committed or qualified through DSR. | `hhj5p.6`, `hhj5p.7`, `vbjbk` |

---

### Ambition Rounds (Phase 4 — 3 Passes Over the 2026-10-13 Bridge Plan)

#### Ambition Pass 1 — Architectural & Systems Optima (Storage, Canonicalization, Mutation & Shallow-Copy)
- **Critique of Initial Plan:** Wave B and Wave C treated custom-object node-key splitting (`"obj:{hash}:{repr}"` at `crates/fnx-python/src/lib.rs:1119`), `remove_node` $O(E)$ `adj_py_keys` retain scans (`crates/fnx-python/src/lib.rs:10183, 16854`; `digraph.rs:7008, 14868`), $O(V+E)$ `compact_before_growth()` (`crates/fnx-classes/src/lib.rs:2069, 3020`; `digraph.rs:1463, 1965`), and $O(V+E)$ `copy.copy(G)` (`crates/fnx-python/src/lib.rs:14553, 20667`; `digraph.rs:9903, 19121`) as isolated point patches.
- **Architectural Upgrade:**
  1. **Hash-Bucket `PyAny::eq` Canonical Slot Interning (`yr2oc.5`):** Replace `"obj:{hash}:{repr}"` string formatting in `fallback_object_canonical_key` with a per-graph hash-bucket collision table (`FxHashMap<isize, SmallVec<[u32; 1]>>`) that probes existing live fallback objects via `PyAny::eq` (`==`) on hash collision and maps equal objects to a stable `obj_slot:{id}` canonical key. This guarantees exact Python dict-key semantics (`a == b and hash(a) == hash(b)` $\implies$ same node regardless of `__repr__`) while keeping the zero-GIL fast path for `int`, `bool`, `float`, `str`, and `bytes`.
  2. **Incident-Indexed `adj_py_keys` Cleanup & Hysteresis Compaction (`yr2oc.5`):** Remove incident `(u, nbr)` / `(nbr, u)` entries from `adj_py_keys` / `succ_py_keys` / `pred_py_keys` using the neighbor list already collected during `remove_node(u)` (instead of `adj_py_keys.retain(|(a, b), _| ...)` across all $E$ edges), restoring strict $O(\text{deg}(u))$ deletion even when numeric aliases (`0` vs `0.0`) are present. Raise `compact_before_growth()` threshold (`tombstones > live_nodes && tombstones >= 64`) so alternating `remove_node` + `add_node` workloads execute in amortized $O(1)$.
  3. **Shared-Handle Shallow Copy (`yr2oc.3`) & Single-Authority Attribute Store (`sfq4w.1`):** Upgrade `copy.copy(G)` across all 4 classes to share inner adjacency/attribute dictionary handles (`G_shallow.adj[u] is G.adj[u]`), fix the false docstrings in `crates/fnx-python/src/digraph.rs:9900, 19118`, and eliminate dual Rust `AttrMap` + Python `node_py_attrs`/`edge_py_attrs` duplication (`<= 1.25x` RSS vs `nx.Graph`).

#### Ambition Pass 2 — Workload, Provenance, Freshness & Matrix Optima (Binary/Source Convergence, DSR Single-Source Authority & Scale-Realistic SLOs)
- **Critique of Initial Plan:** Rebuilding `_fnx.abi3.so` once does not prevent future working-tree/binary drift from silently breaking `scripts/verify_docs.py` or `scripts/delegation_ledger.py`; keeping two manually-synced DSR YAML files invites recurring config drift; and toy-scale SLO workloads (`90x90`, `20x250`, `8x8`) without a live `networkx` comparator violate `AGENTS.md` Rule 0.5.
- **Systems & Provenance Upgrade:**
  1. **Universal Native-Binary Freshness & Symbol-Table Gate (`hhj5p.10`):** Build a shared preflight check (`assert_native_extension_fresh()`) verifying both mtime (`_fnx.abi3.so` newer than `crates/*/src/**/*.rs` and `Cargo.toml`) and symbol/signature parity (all `_fnx.*` symbols and kwargs referenced in `python/franken_networkx/__init__.py`, including `edge_betweenness_centrality(..., source_aware=...)`, `copy_readwrite_policy`, `validate_graphml`). Wire it into `scripts/verify_docs.py`, `scripts/delegation_ledger.py`, `scripts/generate_coverage_docs.py`, and `tests/python/conftest.py`.
  2. **Single-Source DSR Config & Cryptographic Evidence Binding (`hhj5p.1`, `hhj5p.8`):** Converge `.dsr/repos.d/franken_networkx.yaml` and `/home/ubuntu/.config/dsr/repos.yaml` into a byte-identical 9-check + `build_cmd` + `release_contract` specification verified by `scripts/dsr_release_wheels.py --verify-config-parity`, and bind the 5-class RaptorQ release bundle (`csmqh.2`) to `candidate_input_digest` and the loaded `_fnx` ELF sha256.
  3. **Digest-Stamped Conformance Reports (`csmqh.3`) & Spec §17 Live-Incumbent SLO Gate (`csmqh.4`, `vbneu.4`):** Stamp `artifacts/conformance/latest/*.report.json` and `structured_logs.jsonl` with source-input digests verified by `scripts/verify_conformance_freshness.py`, and upgrade `scripts/run_perf_slo_gate.py` + `artifacts/perf/slo_thresholds.json` to Spec §17 scale ($10^5$-node / $10^6$-edge sparse weighted graphs, multi-seed flow topologies) with a live `networkx` comparator arm in the same invocation and p50/p95/p99 + RSS gates.

#### Ambition Pass 3 — Domain-Specific Graph-Theory, Equivalence & Verification Leapfrog (Residual-Graph Flow Parity, 48-Cell CGSE Witness Matrix & Automated Doc-Truth Lints)
- **Critique of Initial Plan:** Fixing 3 flow seeds or adding isolated CGSE witnesses can leave untested graph-class/weight combinations or allow documentation claims to drift again after the next native port.
- **Domain & Verification Upgrade:**
  1. **Bit-Identical CPython-Set / PyNum Preflow-Push (`uh5ua`, `ygt3z`):** Wire `crates/fnx-algorithms/src/preflow_push.rs` (`CPythonSet` open-addressing perturbation table + `PyNum` exact `int`/`float` promotion) into `crates/fnx-algorithms/src/lib.rs` and `crates/fnx-python/src/algorithms.rs` as the default `preflow_push` kernel for `maximum_flow`, `maximum_flow_value`, `minimum_cut`, and `minimum_cut_value`. Prove 100% parity against `nx.maximum_flow` / `nx.algorithms.flow.preflow_push` across a 1,000-graph twin corpus (directed, undirected-to-directed symmetric capacity, mixed int/float capacities, disconnected/zero-capacity cuts) checking flow value, cut partition, per-arc flow dictionary, and residual `R.graph['flow_value']`.
  2. **48-Cell CGSE Witness & Policy Matrix (`csmqh.1`):** Reconcile `v1_policy_registry()` (`crates/fnx-cgse/src/lib.rs:463-479`) with actual kernel tie-break orderings (`Prim`), instrument public `max_weight_matching`/`min_weight_matching` (`blossom.rs`), directed/multigraph `eulerian_circuit`, and `MultiGraph` `prim`/`kruskal`, and enforce an automated 48-cell matrix test (`12 reference algorithms × 4 graph classes × {unweighted, weighted}` where defined) asserting that `cgse.collect_witnesses()` captures $\ge 1$ witness whose `policy` matches `v1_policy_registry()` and whose `observed_count <= dominant_term_bound`.
  3. **Machine-Enforced Doc-Truth & Spec Invariant Linter (`8813x.4`, `8813x.2`, `vbneu.2`):** Extend `scripts/verify_docs.py` so every doc run automatically cross-checks: (a) `fnx.__all__` (`843`) and `backend._SUPPORTED_ALGORITHMS` (`315`) counts across `README.md` and `docs/`, (b) zero claims in `README.md` that natively-implemented algorithms (e.g. weighted `louvain_communities`, `matching`, `branchings`, `greedy_modularity_communities`) delegate to NetworkX, cross-checked against `scripts/delegation_ledger.py`, (c) every local `artifacts/...` and `docs/...` path cited in `README.md`, `SECURITY.md`, `FEATURE_PARITY.md`, and `COMPREHENSIVE_SPEC_FOR_FRANKENNETWORKX_V1.md` exists on disk, (d) `structured_logs.jsonl` field names in `README.md` match actual JSONL keys, and (e) zero occurrences of bare `pytest tests/python/` without `./scripts/run_pytest_guarded.sh`.

---

### Ambition-Escalated Bridge Plan (2026-10-13 — Final 6-Wave Plan)

1. **Wave 0 — Working-Tree, Native-Extension & Preflight Convergence (`hhj5p.10` [P0]):**
   - Wire `assert_native_extension_fresh()` into `scripts/verify_docs.py`, `scripts/delegation_ledger.py`, and `scripts/generate_coverage_docs.py` (checking both `.so` mtime vs Rust sources and required `_fnx.*` symbols/kwargs such as `edge_betweenness_centrality(..., source_aware=...)`, `copy_readwrite_policy`, and `validate_graphml`).
   - Rebuild `python/franken_networkx/_fnx.abi3.so` locally via `env -u CARGO_TARGET_DIR maturin develop --uv --release --features pyo3/abi3-py310` and bound `verify_docs.py`'s `barabasi_albert_graph` snippet RSS so `python3 scripts/verify_docs.py` passes under a 4 GB `ulimit -v`.
   - Partition and land the 48 dirty tracked files + 2 untracked source files across their 19 owning beads with clean `rch exec -- cargo check/clippy/test` and `./scripts/run_pytest_guarded.sh` verification.
2. **Wave A — Single-Source DSR Authority & Machine-Verified Documentation Truth (`hhj5p.1`, `hhj5p.8`, `8813x.2`, `8813x.4`, `vbneu.2` [P0/P1]):**
   - Unify `.dsr/repos.d/franken_networkx.yaml` and `/home/ubuntu/.config/dsr/repos.yaml` into a single 9-check + `build_cmd` + `release_contract` + `FNX_DSR_REQUIRE_EVIDENCE=1` configuration verified by `scripts/dsr_release_wheels.py`.
   - Regenerate `docs/delegation_ledger.md` from the AST + `sys.monitoring` ledger (`vbneu.2`), reconcile `README.md`, `FEATURE_PARITY.md`, `SECURITY.md`, `COMPREHENSIVE_SPEC_FOR_FRANKENNETWORKX_V1.md`, and `AGENTS.md` (`8813x.2`, `8813x.4`), and enforce doc-truth invariants in `scripts/verify_docs.py`.
3. **Wave B — Exact Observable Graph, Key, Copy & Flow Semantics (`uh5ua`, `ygt3z`, `yr2oc.3`, `yr2oc.5`, `hhj5p.6`, `hhj5p.7`, `5cqna`, `o1z03` [P1]):**
   - Wire `crates/fnx-algorithms/src/preflow_push.rs` (`CPythonSet` + `PyNum`) into `crates/fnx-algorithms/src/lib.rs` and `crates/fnx-python/src/algorithms.rs` (`uh5ua`, `ygt3z`), proving 100% flow-dict and cut parity across a 1,000-seed twin corpus.
   - Replace `"obj:{hash}:{repr}"` fallback key formatting (`crates/fnx-python/src/lib.rs:1119`) with hash-bucket `PyAny::eq` slot interning, eliminate $O(E)$ `adj_py_keys.retain(...)` in `remove_node`, and add hysteresis to `compact_before_growth()` (`yr2oc.5`).
   - Implement shared-handle `copy.copy(G)` across all 4 graph classes (`yr2oc.3`) and qualify Python 3.10–3.14 summation + NetworkX 3.7 compatibility (`hhj5p.6`, `hhj5p.7`).
4. **Wave C — Single-Authority Attribute Storage & Native Algorithm Tail (`sfq4w.1`, `yr2oc.1`, `sfq4w.2`, `sfq4w.4`, `8813x.3` [P1/P2]):**
   - Replace dual Rust `AttrMap` + Python `node_py_attrs`/`edge_py_attrs` storage with a single authoritative store (`<= 1.25x` memory vs `nx.Graph`, `sfq4w.1`) and finish `MultiDiGraph` slot-keyed storage (`yr2oc.1`).
   - Port `simple_cycles` and `k_components` to native Rust (`sfq4w.4`), eliminate the 2x conversion tax (`sfq4w.2`), and split `76,280`-line `python/franken_networkx/__init__.py` into domain modules (`8813x.3`).
5. **Wave D — Crown-Jewel Completeness: 48-Cell CGSE Matrix, 5-Class RaptorQ, Fresh Conformance & Spec §17 SLOs (`csmqh.1`–`.6`, `bieu0.1`, `vbneu.4`, `wvztf.1`–`.6` [P1/P2]):**
   - Reconcile CGSE `v1_policy_registry()` (`Prim`) and complete public Python witness coverage across all 12 reference algorithms $\times$ 4 graph classes (`csmqh.1`).
   - Land `csmqh.2` (`fnx-durability` source-packet drop drills, `validate_oti` guard, 5-class `release-bundle`) and regenerate all stale/mismatched `.raptorq.json` sidecars in `artifacts/`.
   - Land `csmqh.5` (`crates/fnx-conformance/src/behavioral_oracle.py`), regenerate all 120 conformance reports + `conformance_dashboard_v1.json` (`csmqh.3`) so `scripts/verify_conformance_freshness.py` exits `0`, and qualify bounded-memory Rayon admission (`csmqh.6`).
   - Upgrade `scripts/run_perf_slo_gate.py` and `artifacts/perf/slo_thresholds.json` to Spec §17 scale with a live `networkx` comparator arm (`csmqh.4`, `vbneu.4`).
6. **Wave E — Full V1 System Acceptance & Public Release `0.2.4` (`hhj5p.9`, `euaqe` [P0/P1]):**
   - Run `dsr quality --tool franken_networkx` and `dsr build franken_networkx` to green completion (`hhj5p.9`), then publish `0.2.4` via DSR with 6 wheels, sdist (including `LICENSE`), and verified 5-class RaptorQ evidence bundle (`euaqe`).

---

### Beads Created & Updated (2026-10-13 — Phase 3a & Phase 5)

| Bead ID | Action | Pri | Wave | Summary & Key Acceptance Gates |
|---|---|---|---|---|
| `br-r37-c1-rc0923-epic-evidence-authority-hhj5p.10` | **NEW** | P0 | Wave 0 | **Working-tree & native-extension convergence:** shared `assert_native_extension_fresh()` preflight (mtime + `_fnx` symbol/kwarg parity) in `verify_docs.py`, `delegation_ledger.py`, `generate_coverage_docs.py`, `conftest.py`; local `maturin develop --uv --release`; partition 48 dirty + 2 untracked files across 19 beads. Ranks **#1** in `bv --robot-triage` (`score: 0.4523`). |
| `br-r37-c1-rc0923-epic-docs-truth-structure-8813x.4` | **NEW** | P1 | Wave A | **Doc-truth & planning-spec reconciliation:** fix 6 false `louvain_communities` delegation claims, `843` vs `839` exports, `315` vs `313` backend algorithms, `structured_logs.jsonl` schema mismatch, `FEATURE_PARITY.md:160` bare `pytest`, `SECURITY.md` `< 1.0` & broken links; enforce `verify_doc_truth_invariants()` in `verify_docs.py`. |
| `br-r37-c1-epic-storage-architecture-yr2oc.5` | **NEW** | P1 | Wave B | **Canonical Python node-key equality & $O(\text{deg}(u))$ alias cleanup:** replace `"obj:{hash}:{repr}"` (`crates/fnx-python/src/lib.rs:1119`) with hash-bucket `PyAny::eq` slot interning; replace $O(E)$ `adj_py_keys.retain(...)` in `remove_node` with incident neighbor removal; add tombstone hysteresis to `compact_before_growth()`. Ranks **#3** in `bv --robot-triage` `blockers_to_clear`. |
| `br-r37-c1-rc0923-epic-evidence-authority-hhj5p.1` | Updated | P0 | Wave A | Added acceptance criteria, prerequisite (`hhj5p.10`), and 2026-10-13 audit comment on `.dsr/repos.d/franken_networkx.yaml` vs `~/.config/dsr/repos.yaml` bidirectional divergence. |
| `br-r37-c1-rc0923-epic-evidence-authority-hhj5p.8` | Updated | P0 | Wave A | Added 2026-10-13 audit comment tracking uncommitted `release_evidence` archive binding in `scripts/dsr_release_wheels.py` (`+140/-8` lines). |
| `br-r37-c1-rc0923-epic-evidence-authority-hhj5p.9` | Updated | P0 | Wave E | Wired blocking dependencies on `hhj5p.10`, `8813x.4`, `yr2oc.5`, `yr2oc.3`, `8813x.2`, `vbneu.2` and recorded Wave 0–D prerequisites checklist. |
| `br-r37-c1-rc0923-epic-crown-jewels-csmqh.1` | Updated | P1 | Wave D | Added acceptance criteria & audit comment: reconcile `v1_policy_registry()` `Prim` policy (`WeightThenLex` vs `WeightThenInsertionOrder`), instrument `blossom.rs` + directed/multigraph Euler/MST, and enforce 48-cell witness matrix test. |
| `br-r37-c1-rc0923-epic-crown-jewels-csmqh.2` | Updated | P1 | Wave D | Added acceptance criteria & audit comment: land working-tree `fnx-durability` (`dropped_source_packets`, `validate_oti`, 5-class `release-bundle`) and regenerate all 29 `.raptorq.json` sidecars in `artifacts/`. |
| `br-r37-c1-rc0923-epic-crown-jewels-csmqh.3` | Updated | P1 | Wave D | Added acceptance criteria, dependencies (`hhj5p.10`, `csmqh.5`), and audit comment on 120 stale `2026-09-09` reports failing `verify_conformance_freshness.py` (`exit 1`). |
| `br-r37-c1-rc0923-epic-crown-jewels-csmqh.4` | Updated | P1 | Wave D | Added acceptance criteria & audit comment requiring Spec §17 scale ($10^5$-node / $10^6$-edge) and live `networkx` comparator arm in `scripts/run_perf_slo_gate.py`. |
| `br-r37-c1-rc0923-epic-crown-jewels-csmqh.5` | Updated | P1 | Wave D | Added audit comment tracking untracked `crates/fnx-conformance/src/behavioral_oracle.py` (`2,691` lines) and `feature_behavioral_oracle.rs` wiring. |
| `br-r37-c1-rc0923-epic-crown-jewels-csmqh.6` | Updated | P1 | Wave D | Added audit comment tracking uncommitted APSP chunking and `edge_betweenness_centrality(..., source_aware=...)` (`__init__.py:33579`). |
| `br-r37-c1-uh5ua` | Updated | P1 | Wave B | Added acceptance criteria & audit comment: wire untracked `crates/fnx-algorithms/src/preflow_push.rs` (`1,038` lines) into `fnx-algorithms` and `fnx-python`, and verify 1,000-seed flow/cut parity. |
| `br-r37-c1-epic-storage-architecture-yr2oc.3` | Updated | P1 | Wave B | Added acceptance criteria & audit comment on shared-handle `copy.copy(G)` and false docstrings at `crates/fnx-python/src/digraph.rs:9900, 19118`. |
| `br-r37-c1-rc0923-epic-honest-measurement-vbneu.2` | Updated | P1 | Wave A | Added acceptance criteria, prerequisite (`hhj5p.10`), and audit comment to regenerate `docs/delegation_ledger.md` from AST + `sys.monitoring` census. |
| `br-r37-c1-rc0923-epic-docs-truth-structure-8813x.2` | Updated | P1 | Wave A | Added acceptance criteria, prerequisite (`hhj5p.10`), and audit comment on `843` vs `839` export and `315` vs `313` backend count drift. |

---

### Plan-Space Refinement Ledger (Phase 5 — 5 Rounds to Convergence)

- **Pass 1 (Dependency Topology & Wave Ordering):** Inspected `hhj5p.10`, `8813x.4`, `yr2oc.5`, `hhj5p.9`, `euaqe`, `csmqh.3`, `8813x.2`, and `sfq4w.3`. Found that `csmqh.3` (conformance report refresh) and `8813x.2` (generated README numeric tables) lacked blocking edges on `hhj5p.10` (fresh `_fnx.abi3.so`) and `csmqh.5` (crate-local `behavioral_oracle.py`), and `sfq4w.3` (mutation-heavy algorithm sequence performance) lacked a blocking edge on `yr2oc.5` ($O(\text{deg}(u))$ `adj_py_keys` removal). Added 4 dependency edges via `br dep add`; verified `br dep cycles --include-closed --json` = `0`.
- **Pass 2 (Acceptance Criteria & Ambition Pass Alignment):** Inspected `acceptance_criteria` and `prerequisites` on `hhj5p.9`, `hhj5p.10`, `8813x.4`, `yr2oc.5`, `csmqh.1`, `csmqh.2`, `csmqh.3`, `csmqh.4`, and `uh5ua` via `br show`. Populated explicit checklist acceptance criteria and prerequisites via `br update` encoding Ambition Passes 1–3 (48-cell CGSE matrix on `csmqh.1`, 5-class RaptorQ + 29 sidecar refresh on `csmqh.2`, Spec §17 live `networkx` comparator on `csmqh.4`, 1,000-seed `preflow_push.rs` twin corpus on `uh5ua`, Wave 0–D prerequisites on `hhj5p.9`).
- **Pass 3 (Self-Containment & Planted-Regression Negative Gates):** Inspected `hhj5p.1`, `hhj5p.8`, `8813x.2`, `vbneu.2`, and `yr2oc.3` via `br show`. Found `acceptance_criteria: null` on `hhj5p.1`, `8813x.2`, `vbneu.2`, and `yr2oc.3`, and missing blocking edges from `hhj5p.1` and `vbneu.2` to `hhj5p.10`. Updated all 4 beads with positive + planted-drift negative acceptance criteria and wired `hhj5p.1 -> hhj5p.10` and `vbneu.2 -> hhj5p.10`; verified `br dep cycles --include-closed --json` = `0`.
- **Pass 4 (Graph-Aware Triage & Critical-Path Verification via `bv`):** Ran `br sync --flush-only` and `bv --robot-triage`. Confirmed `hhj5p.10` ranks **#1** in both `blockers_to_clear` and `recommendations` (`score: 0.4523`, P0, `actionable: true`), and `yr2oc.5` ranks **#3** in `blockers_to_clear` (`actionable: true`).
- **Pass 5 (Convergence & Invariant Verification):** Re-verified all 5 frozen Phase 5 checklist invariants across all 13 Vision Checklist rows (`0` `NO_BEAD` items, `0` test-only split beads, `0` dependency cycles in `br dep cycles --include-closed --json`, exact 1-to-1 match between `.beads/issues.jsonl` and `bv --robot-triage` counts: `3,863` total = `3,758` closed + `60` `in_progress` + `40` `open` + `5` `blocked`). **Zero changes required — converged.**



