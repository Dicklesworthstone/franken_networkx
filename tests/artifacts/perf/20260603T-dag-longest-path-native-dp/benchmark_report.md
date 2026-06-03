# br-r37-c1-pzutt: dag_longest_path native predecessor DP

## Target

- Bead: `br-r37-c1-pzutt`
- Fixture: deterministic 400-node DiGraph DAG, edge probability `0.02`, seed `20260603`
- Operation: `dag_longest_path(G)` plus `dag_longest_path_length(G)` per repeat
- Profile-backed hotspot: baseline cProfile spent `1.794s / 80 repeats` in `dag_longest_path`; the dominant cost was `G.pred[v].items()` through `AtlasView` and `_private_pred_mapping`, not topological sorting.

## Baseline

- FNX direct rch timing: `1.732626609998988s / 200` = `0.00866313304999494s` per call pair
- NetworkX oracle rch timing: `0.4071009359904565s / 200` = `0.0020355046799522825s` per call pair
- Hyperfine baseline via rch, 80 repeats through a `HEAD` import overlay: `1.00276056072s +/- 0.04292952114874328s`
- Golden SHA: `5b8012a4dd619416733afe7f6475760247475c466e9c3975cfb60f6827688161`

## Change

Use the existing safe-Rust `_native_in_edges_data_key(weight, default_weight)` snapshot for exact `DiGraph` and computed topological order. Build a Python predecessor map once, then run NetworkX's same stable DP over predecessor order.

Fallbacks are unchanged for multigraphs, views/subclasses, undirected graphs, explicit `topo_order`, and any graph without the native helper.

## After

- FNX direct rch timing: `0.49907358398195356s / 200` = `0.002495367919909768s` per call pair
- Direct self-speedup: `3.47x`
- Hyperfine after via rch, 80 repeats: `0.4922190647400001s +/- 0.027970053887369572s`
- Hyperfine self-speedup: `2.04x`
- Golden SHA: `5b8012a4dd619416733afe7f6475760247475c466e9c3975cfb60f6827688161`
- Score: Impact `3.47` x Confidence `4` / Effort `1` = `13.9`; keep.

