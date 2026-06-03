# Top-level adjacency_data / node_link_data native wiring (br-r37-c1-9kpev)

Lever: route the TOP-LEVEL `fnx.adjacency_data` and `fnx.node_link_data` (what
`nx.adjacency_data` / `nx.node_link_data` resolve to) through the native
`_fnx.adjacency_data_simple` / `_fnx.node_link_data_simple` kernels (shipped in
7a6be7d5e / 38f9fa162 for the json_graph module wrappers), gated on exact
simple Graph / DiGraph. Multigraphs and subclasses / filtered views keep the
per-edge AdjacencyView / EdgeView Python loops.

NOTE: the code change itself was swept into commit ce5819966 by the repo's
commit daemon (it `git add -A`'d an uncommitted working-tree edit under an
unrelated DAG message). The change is live and correct on origin/main; this
artifact + the regression test document it under the right bead.

## Benchmark (python time.perf_counter, n=1500 m=12000 undirected, attrs)

| function           | nx      | fnx before | fnx after |
|--------------------|---------|------------|-----------|
| adjacency_data     | 8.8 ms  | ~94 ms     | 18.2 ms   |
| node_link_data     | 7.0 ms  | ~15 ms     | 9.9 ms    |

Top-level now matches the json_graph module path (18.2 vs 15.9 ms; 9.9 vs
9.7 ms). adjacency_data self-speedup ~5x.

Fresh rch closeout sample on current head (2026-06-03 17:49 EDT,
n=1500 m=12000 undirected, attrs, 15 direct reps) confirmed the top-level
wrappers still route through the native kernels:

| function                     | mean |
|------------------------------|------|
| networkx adjacency_data      | 7.43 ms |
| fnx adjacency_data           | 12.80 ms |
| fnx json_graph adjacency_data| 10.86 ms |
| networkx node_link_data      | 5.64 ms |
| fnx node_link_data           | 7.41 ms |
| fnx json_graph node_link_data| 7.14 ms |

Fresh cProfile over 20 top-level calls each showed the wrapper gap is closed:
`_fnx.adjacency_data_simple` consumed 0.227s / 20 calls and
`_fnx.node_link_data_simple` consumed 0.170s / 20 calls; the former
AdjacencyView / EdgeView loops are no longer in the top stack.

Fresh rch hyperfine process envelope (including import + graph construction +
20 calls) was: networkx adjacency 223.1 ms +/- 31.0 ms, fnx adjacency
363.7 ms +/- 20.2 ms, networkx node_link 189.3 ms +/- 10.8 ms, fnx node_link
363.8 ms +/- 19.8 ms. That residual is Python object materialization/import
and native PyDict copy cost, not a missing top-level delegation.

## Isomorphism + golden proof

Bit-exact vs networkx across {undirected,directed} x default/custom field
names x attrs/no-attrs/singleton; multigraph fallback; native-path-taken spy
check (test_toplevel_json_data_native_parity, 5 cases).

GOLDEN sha256 (n=300 m=3000 undirected, attrs, json sort_keys):
  adjacency_data: 9efefe16fe92ad18... (nx == fnx)
  node_link_data: 5fc78a486f64a69d... (nx == fnx)

Fresh current-head golden sha256 (n=300 m=3000 undirected, attrs,
json sort_keys, same edge/node insertion order):
  adjacency_data: d2ada9cae07ad5d7035835af20c39240622f06289b3a34bd701e6c77b7d00679
  node_link_data: e50e92a03d3874ab631ec7d00d6b0383071c7a60a611d4e77412678f05316715

Ordering / tie-break proof: exact `Graph` / `DiGraph` only; node order follows
stored node insertion order, undirected edge order follows the native
NetworkX-compatible seen-source traversal in `node_link_data_simple`, and
multigraphs/subclasses still fall back to the old Python loops. Floating-point
payload values are copied without arithmetic; RNG is used only by the benchmark
graph generator, seeded deterministically.

Validation: rch `pytest tests/python/test_toplevel_json_data_native_parity.py -q`
passed (`5 passed`); rch `py_compile` passed for the wrapper and regression
test. 289 existing conversion/json/readwrite tests passed in the original
artifact run.
