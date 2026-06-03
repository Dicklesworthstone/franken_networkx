# Benchmark report: quotient raw trusted edge insertion

Bead: `br-r37-c1-04z53.43`

## Target

After `br-r37-c1-04z53.40`, focused cProfile still showed the default
quotient edge insertion boundary as the shifted hotspot:

- `quotient_graph`: `0.11845837798318826s`
- `_add_default_undirected_bucketed_edges`: `0.077s`
- public `add_edges_from`: `0.070s`

Candidate lever: call captured `_GRAPH_RAW_ADD_EDGES_FROM(H, edge_bunch)` for
the internally generated simple-undirected default quotient `edge_bunch`, and
leave every fallback/public path unchanged.

## Baseline

- Direct FNX mean, 10 samples: `0.08058842989848927s`
- Direct NetworkX mean, 10 samples: `2.230865502593224s`
- Golden digest: `34c9c354b368f5ae22d72d7f4635d9b9d263215bb31a2cf673e2e5203c2a5c52`
- Focused hyperfine mean: `0.4235102938333333s +/- 0.018315981090441812s`
- Focused hyperfine median: `0.42483377930000005s`

## Candidate

- Direct FNX mean, 10 samples: `0.08403222350461874s`
- Direct NetworkX mean, 10 samples: `2.278953605107381s`
- FNX confirm mean, 30 samples: `0.08557084476439437s`
- Golden digest: `34c9c354b368f5ae22d72d7f4635d9b9d263215bb31a2cf673e2e5203c2a5c52`
- Focused hyperfine mean: `0.42451979044666666s +/- 0.02034896179444217s`
- Focused hyperfine median: `0.42338767018s`
- Focused cProfile `quotient_graph`: `0.10452611499931663s`
- Focused cProfile `_add_default_undirected_bucketed_edges`: `0.062s`

## Restored

- Source restoration proof: `git diff HEAD -- python/franken_networkx/__init__.py`
  was empty after manually restoring `H.add_edges_from(edge_bunch)`.
- Restored FNX mean, 3 samples: `0.08170925732702017s`
- Restored NetworkX mean, 3 samples: `2.2159716926689725s`
- Restored golden digest:
  `34c9c354b368f5ae22d72d7f4635d9b9d263215bb31a2cf673e2e5203c2a5c52`

## Decision

Rejected. The candidate improved cProfile cumulative time for the Python
boundary, but direct timing and focused hyperfine did not show a real win.

Score: Impact 0 x Confidence 4 / Effort 1 = `0.0`.

Next primitive: replace the Python tuple `edge_bunch` handoff with a safe-Rust
trusted quotient edge-batch builder that inserts block-pair edges directly from
pre-resolved block node labels and aggregate totals. Target: remove the Python
tuple decode/membrane path, not another public/raw wrapper swap.
