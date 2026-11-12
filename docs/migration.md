# Migration From NetworkX

There are two migration paths:

- Backend mode: keep `import networkx as nx` and configure the backend.
- Standalone mode: switch to `import franken_networkx as fnx` and use the Rust-backed graph types directly.

See [backend.md](backend.md) for dispatch details and [quickstart.md](quickstart.md) for runnable examples.

## Side-By-Side Patterns

| Pattern | NetworkX | FrankenNetworkX standalone | FrankenNetworkX backend |
| --- | --- | --- | --- |
| Create an undirected graph | `nx.Graph()` | `fnx.Graph()` | `nx.Graph()` |
| Create a directed graph | `nx.DiGraph()` | `fnx.DiGraph()` | `nx.DiGraph()` |
| Create a multigraph | `nx.MultiGraph()` | `fnx.MultiGraph()` | `nx.MultiGraph()` |
| Add a weighted edge | `G.add_edge("a", "b", weight=2.0)` | same | same |
| Generate a path graph | `nx.path_graph(10)` | `fnx.path_graph(10)` | `nx.path_graph(10)` |
| Generate a random graph | `nx.gnp_random_graph(100, 0.05, seed=7)` | `fnx.gnp_random_graph(100, 0.05, seed=7)` | `nx.gnp_random_graph(100, 0.05, seed=7)` |
| Shortest path | `nx.shortest_path(G, s, t)` | `fnx.shortest_path(G, s, t)` | `nx.shortest_path(G, s, t, backend="franken_networkx")` |
| Weighted shortest path | `nx.shortest_path(G, s, t, weight="weight")` | same | same |
| Shortest-path length | `nx.shortest_path_length(G, s, t)` | `fnx.shortest_path_length(G, s, t)` | `nx.shortest_path_length(G, s, t, backend="franken_networkx")` |
| Connected components | `list(nx.connected_components(G))` | `list(fnx.connected_components(G))` | `list(nx.connected_components(G, backend="franken_networkx"))` |
| PageRank | `nx.pagerank(G)` | `fnx.pagerank(G)` | `nx.pagerank(G, backend="franken_networkx")` |
| Betweenness centrality | `nx.betweenness_centrality(G)` | `fnx.betweenness_centrality(G)` | `nx.betweenness_centrality(G, backend="franken_networkx")` |
| Topological sort | `list(nx.topological_sort(D))` | `list(fnx.topological_sort(D))` | `list(nx.topological_sort(D, backend="franken_networkx"))` |
| Minimum spanning tree | `nx.minimum_spanning_tree(G)` | `fnx.minimum_spanning_tree(G)` | `nx.minimum_spanning_tree(G, backend="franken_networkx")` |
| Maximum flow value | `nx.maximum_flow_value(D, s, t)` | `fnx.maximum_flow_value(D, s, t)` | `nx.maximum_flow_value(D, s, t, backend="franken_networkx")` |
| Node-link JSON | `nx.node_link_data(G)` | `fnx.node_link_data(G)` | `nx.node_link_data(G)` |
| Read edgelist | `nx.read_edgelist(path)` | `fnx.read_edgelist(path)` | `nx.read_edgelist(path)` |
| Write edgelist | `nx.write_edgelist(G, path)` | `fnx.write_edgelist(G, path)` | `nx.write_edgelist(G, path)` |
| Numpy adjacency | `nx.to_numpy_array(G)` | `fnx.to_numpy_array(G)` | `nx.to_numpy_array(G, backend="franken_networkx")` |
| Per-call acceleration | n/a | n/a | `backend="franken_networkx"` |

## Minimal Migration Example

```python
import franken_networkx as fnx
import networkx as nx

fnx_graph = fnx.path_graph(5)
assert fnx.shortest_path(fnx_graph, 0, 4) == [0, 1, 2, 3, 4]

nx.config.backend_priority = ["franken_networkx"]
nx_graph = nx.path_graph(5)
assert nx.shortest_path(nx_graph, 0, 4, backend="franken_networkx") == [0, 1, 2, 3, 4]
```

## Choosing a Mode

Use standalone mode when:

- you want explicit control over graph types,
- you are writing new code and can standardize on `fnx`,
- you want to avoid any ambiguity about which calls dispatch where.

Use backend mode when:

- you already have a NetworkX application,
- you want incremental adoption,
- you want to preserve existing imports and data loading patterns.

## Known Differences and Current Limitations

- Backend acceleration only applies to functions registered in the backend interface and supported by the current argument shape.
- Some callback-heavy surfaces still delegate to NetworkX for compatibility.
- Standalone I/O is intentionally close to NetworkX, but not every keyword has landed yet. For example, `fnx.read_edgelist()` currently exposes a smaller keyword surface than `nx.read_edgelist()`.
- Drawing functions still delegate to NetworkX and matplotlib.

## Recommended Migration Sequence

1. Start by enabling backend mode in a benchmark or smoke-test slice of your application.
2. Verify the specific hot algorithms you care about are in the supported set.
3. Move high-volume code paths to standalone `fnx` imports when you want tighter control over graph creation, serialization, or typing.
4. Keep parity tests around any code that depends on tie-break behavior or exact serialized output.
