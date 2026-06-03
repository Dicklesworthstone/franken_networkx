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

## Isomorphism + golden proof

Bit-exact vs networkx across {undirected,directed} x default/custom field
names x attrs/no-attrs/singleton; multigraph fallback; native-path-taken spy
check (test_toplevel_json_data_native_parity, 5 cases).

GOLDEN sha256 (n=300 m=3000 undirected, attrs, json sort_keys):
  adjacency_data: 9efefe16fe92ad18... (nx == fnx)
  node_link_data: 5fc78a486f64a69d... (nx == fnx)

289 existing conversion/json/readwrite tests pass.
