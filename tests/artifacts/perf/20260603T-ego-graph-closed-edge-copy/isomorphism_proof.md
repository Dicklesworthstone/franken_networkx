# ego_graph Closed Simple Graph Edge-Copy Proof

Bead: `br-r37-c1-04z53.27`

Target: `ego_graph(Graph, 0, radius=2)` on `barabasi_albert_graph(3000, 4, seed=42)`.

## Profile-Backed Target

Baseline cProfile showed 9 `ego_graph` calls taking `0.574s` cumulative. The simple-Graph edge copy paid both public iterator overhead and repeated insertion overhead:

- `Graph.add_edge` wrapper: `0.209s` cumulative.
- Raw `Graph.add_edge`: `0.173s`.
- `_FailFastEdgeIterator.__next__`: `0.139s`.
- Repeated `len`: `0.098s`.
- `EdgeDataView._materialize`: `0.083s`.

## Lever Kept

For the simple-Graph copy path only, use one closed internal edge-copy fast path:

1. Get `G.edges(data=True)`.
2. If it is exactly the module-local `EdgeDataView`, consume the already-defined `_materialize()` list instead of the public fail-fast iterator.
3. Filter eligible edges in the same order.
4. Preserve current non-string attr-key keyword-expansion behavior by using `graph.add_edge(u, v, **data)` for those edge dicts.
5. Bulk-insert the remaining empty or string-keyed attr dicts with one `graph.add_edges_from(edges_to_add)`.

## Behavior Isomorphism

Ordering: `_materialize()` is the exact list wrapped by the public iterator, and `edges_to_add` preserves that source order before `add_edges_from`.

Tie-breaking: BFS node discovery, radius filtering, `nodes_within`, final node order, center removal, and multigraph behavior are unchanged.

Attribute semantics: edge data with non-string keys still routes through `add_edge(**data)`, preserving the current keyword-expansion error behavior. Empty and string-keyed edge data follow the same observable attr copy contract through `add_edges_from`.

Floating point: this unweighted radius case performs no floating-point accumulation in the changed path.

RNG: the library path uses no RNG. The benchmark graph seed is fixed at `42`.

Golden output: baseline, NetworkX comparison, candidate repeat-9, and candidate repeat-21 all emitted digest `a66fe1d2d36fe1f69a5966fab6d739d8b5b34ed0aae622b17565fbba8ce603d6`.

## Benchmark Result

Baseline fnx repeat-9 mean: `0.045851581998350516s`.

NetworkX repeat-9 mean: `0.020990028110746708s`.

Candidate fnx repeat-9 mean: `0.04422494622283719s`.

Candidate fnx repeat-21 mean: `0.04233674376224544s`.

Hyperfine baseline: `577.3 ms +/- 59.0 ms`.

Hyperfine candidate: `508.7 ms +/- 21.2 ms`.

Hyperfine candidate repeat-20: `526.5 ms +/- 25.6 ms`.

Focused profile: `ego_graph` cumulative time improved from `0.574s` to `0.425s`; total function calls dropped from `1333325` to `840998`.

Score: Impact 2 x Confidence 4 / Effort 2 = 4.0.

Verdict: productive; source change kept.

## Verification

- `rch exec -- .venv/bin/python -m py_compile python/franken_networkx/__init__.py`: passed.
- `rch exec -- .venv/bin/python -m pytest tests/python/test_quickwin_rewire_parity.py::test_ego_graph_matches_nx tests/python/test_review_mode_regression_lock.py::test_ego_graph_missing_source_and_nan_radius_match_nx -q`: 2 passed.
- `sha256sum -c tests/artifacts/perf/20260603T-ego-graph-closed-edge-copy/artifact_sha256.txt`: passed.
- `RCH_ENV_ALLOWLIST=CARGO_TARGET_DIR rch exec -- cargo fmt --package fnx-python --check`: passed.
- `RCH_ENV_ALLOWLIST=CARGO_TARGET_DIR rch exec -- cargo check -p fnx-python --all-targets`: passed.
- `timeout 180 ubs python/franken_networkx/__init__.py tests/artifacts/perf/20260603T-ego-graph-edgedataview-materialize/isomorphism_proof.md`: timed out while scanning the large Python wrapper before producing findings.
- `timeout 60 ubs tests/artifacts/perf/20260603T-ego-graph-closed-edge-copy/isomorphism_proof.md`: exited 0 with no recognizable language to scan.
