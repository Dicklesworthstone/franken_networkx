# FrankenNetworkX Reality Check

> Historical audit below. The [2026-10-04 audit](#reality-check-2026-10-04)
> supersedes its current-state conclusions, especially zero-delegation and
> functional-parity claims. Historical findings are retained, not rewritten.

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
