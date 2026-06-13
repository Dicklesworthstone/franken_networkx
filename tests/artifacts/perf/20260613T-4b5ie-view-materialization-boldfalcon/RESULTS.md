# br-r37-c1-4b5ie node-data mirror proof

Lever: cache `PyGraph` node-data `dict.items()` behind `nodes_seq` and route
`NodeView.items()` through it. Values are the existing live per-node Python
attribute dicts.

Baseline target was profile-backed:

- `nodes_data`: `NodeDataView.__iter__ -> _materialize -> _mapping_items_view -> NodeView.items`
- `adjacency`: `_simple_graph_adjacency -> _fnx.to_dict_of_dicts_undirected`

Bench harness:

- `view_materialization_harness.py --nodes 800`
- graph: `connected_watts_strogatz_graph(800, 6, 0.3, seed=0)`
- candidate extension sha256: `6f49a22690537d323fd19e0283cf11ba5218c9622d4cc692e38aed89cf5ab619`

Results:

| operation | baseline mean | candidate mean | speedup | output sha256 |
| --- | ---: | ---: | ---: | --- |
| `list(G.nodes(data=True))` | `0.00012883230418083257s` | `0.000014273831096943468s` | `9.025769136950213x` | `da353a1409c48846152b6904699af3c0edf6a50cd9d6c2954a9a923b3a8fdc7d` |
| `dict(G.adjacency())` | `0.00009773603208304849s` | `0.00008998595393495634s` | `1.086125420792828x` | `05e5b22eb7a79e6009ddaeb9620bcef89b14f7c3e7bb0f83139b862817d6512b` |

Golden proof:

- `baseline_golden.json` sha256: `e48e74c7624b404732f32f54747686431bde9733cf1e3072d3c61e80eda12e53`
- `candidate_golden_node_data_mirror.json` sha256: `e48e74c7624b404732f32f54747686431bde9733cf1e3072d3c61e80eda12e53`
- Ordering/tie-breaking: golden rows compare ordered FNX rows to ordered NetworkX rows.
- Attribute liveness: golden rows and direct candidate parity assertions cover live attr dict mutation.
- Floating point/RNG: no floating-point arithmetic or RNG is changed by the lever; the harness seed is fixed only for graph construction.

Validation:

- `rch exec -- cargo check -p fnx-python --lib`: pass; existing `fnx-generators` unused-return warnings only.
- Candidate-loaded direct assertions from `test_nodes_data_view_liveness_parity.py`: pass.
- Candidate-loaded selected view pickle assertions from `test_view_pickle_parity.py`: pass.
- `git diff --check`: pass.
- `ubs crates/fnx-python/src/{lib.rs,views.rs,algorithms.rs,generators.rs,readwrite.rs}`: no critical findings; shadow-workspace fmt/clippy/check/test-build clean.

Known unrelated gate debt:

- `cargo fmt -p fnx-python --check` reports pre-existing formatting drift in `fnx-python`.
- `rch exec -- cargo clippy -p fnx-python --lib -- -D warnings` fails on pre-existing `fnx-generators` unused-return warnings.

Score:

- Impact `9.03`, confidence `0.90`, effort `1.0`: `8.13`.
