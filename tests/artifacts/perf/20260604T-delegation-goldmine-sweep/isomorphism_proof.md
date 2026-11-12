# Directed Group Degree Centrality Native Formula

Bead: `br-r37-c1-qx7na`

## Profile Target

- Candidate sweep baseline found `group_degree_centrality_directed` with matching FNX/NetworkX digest and a 50k-node directed path target at FNX `0.485378729s` vs NetworkX `0.000013373s`.
- cProfile confirmed the hot path was parity conversion: `group_degree_centrality -> _call_networkx_for_parity -> _networkx_graph_for_parity -> _fnx_to_nx`, with `_fnx_to_nx` at `2.077s` over three calls.
- Baseline hyperfine process envelope: `1.475118s +/- 0.241817s`.

## Lever

For directed `Graph` variants, compute NetworkX's exact scalar formula locally:

```python
neighbors = set().union(*(set(G.neighbors(node)) for node in S)) - set(S)
return len(neighbors) / (len(G.nodes()) - len(S))
```

Undirected inputs still use `_raw_group_degree_centrality`.

## Behavior Invariants

- Directed semantics: `G.neighbors(node)` means successors, matching NetworkX `DiGraph.neighbors`.
- MultiDiGraph semantics: parallel edges collapse to unique successor nodes through `set(G.neighbors(node))`, matching NetworkX.
- Duplicate entries in `S` remain observable in `len(S)` while `set(S)` removes group members from the neighbor union, matching the oracle formula.
- Missing and unhashable group nodes still flow through `G.neighbors(node)` and preserve the existing NetworkX-style error path.
- Ordering and tie-breaking are not observable because the result is a scalar.
- Floating-point behavior is unchanged except for the final integer division used by the oracle formula.
- RNG is not touched.

## Results

- Confirmed direct FNX mean: `0.485378729s -> 0.000015890s` (`30545.90x`).
- Confirmed FNX/NetworkX digest: `b8a0af485a42df9bad73eed59e213bacf3cfaf8abbf42628d03a263a485d1e41`.
- Confirmed after ratio: FNX `0.349x` of NetworkX on the 50k-node target.
- After hyperfine process envelope: `0.782188s +/- 0.0387s` (`1.89x` process-envelope win; graph construction and import dominate after the lever).
- After cProfile removes `_call_networkx_for_parity` and `_fnx_to_nx` from the measured target stack.

## Score

Impact `5` x Confidence `5` / Effort `1` = `25.0`; keep.
