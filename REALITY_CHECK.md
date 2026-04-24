# FrankenNetworkX Reality Check

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
