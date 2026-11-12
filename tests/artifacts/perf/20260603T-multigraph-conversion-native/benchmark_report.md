# br-r37-c1-e6olo benchmark report

Target: exact `MultiGraph` / `MultiDiGraph` `to_directed()` and `to_undirected()` materializing conversions.

Profile-backed hotspot:
- Before profile: `MultiAdjacencyView` iteration and `_multi_add_edges_from` dominated conversion materialization.
- Lever: exact-type PyO3 deepcopy conversion builders, guarded so views, subclasses, private NetworkX storage, and custom conversion class factories stay on the generic Python path.

Hyperfine command shape:
- `rch exec -- hyperfine --warmup 1 --runs 5 ...`
- Fixture: 160 nodes, 800 edges, 3 conversions per timed command.

| Operation | Before mean | After mean | Speedup |
| --- | ---: | ---: | ---: |
| `mg_to_directed` | 13.882298s | 0.374208s | 37.10x |
| `mg_to_undirected` | 11.305075s | 0.348802s | 32.41x |
| `mdg_to_directed` | 3.858482s | 0.333387s | 11.57x |
| `mdg_to_undirected` | 4.842010s | 0.342098s | 14.15x |

After profile:
- `mg_to_directed`: 0.061534s per conversion under cProfile; native `_native_to_directed_deepcopy` and `copy.deepcopy` dominate.
- `mdg_to_undirected`: 0.035839s per conversion under cProfile; native `_native_to_undirected_deepcopy` and `copy.deepcopy` dominate.

Score:
- Impact: 5
- Confidence: 5
- Effort: 2
- Impact x Confidence / Effort = 12.5

