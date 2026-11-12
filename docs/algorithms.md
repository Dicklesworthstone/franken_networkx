# Algorithm Reference

This page is a fast map of the most important algorithm families exposed by FrankenNetworkX.

For the full function inventory, see [README.md](../README.md). For migration advice, see [migration.md](migration.md).

## Complexity Notes

The table below uses the dominant textbook bound for the current algorithm path exposed by the library. It is intended as a planning aid, not a formal performance contract.

| Family | Representative functions | Typical complexity | Notes |
| --- | --- | --- | --- |
| Unweighted shortest path | `shortest_path`, `single_source_shortest_path`, `has_path` | `O(V + E)` | Breadth-first traversal on unweighted graphs |
| Weighted shortest path | `dijkstra_path`, `shortest_path(..., weight=...)`, `multi_source_dijkstra` | `O((V + E) log V)` | Priority-queue based |
| Bellman-Ford | `bellman_ford_path` | `O(VE)` | Supports negative weights without negative cycles |
| Connectivity | `connected_components`, `is_connected`, `bridges`, `articulation_points` | `O(V + E)` | Deterministic component traversal |
| Directed connectivity | `strongly_connected_components`, `weakly_connected_components`, `condensation` | `O(V + E)` | SCC/WCC and condensed DAG generation |
| Centrality | `pagerank`, `closeness_centrality`, `harmonic_centrality`, `betweenness_centrality` | graph- and iteration-dependent | Use the benchmark gate for tail behavior |
| Clustering | `clustering`, `triangles`, `transitivity` | roughly `O(sum d(v)^2)` | Density-sensitive |
| Flow and cut | `maximum_flow`, `maximum_flow_value`, `minimum_cut` | algorithm-dependent | Current common path is aligned with Edmonds-Karp style bounds |
| Trees | `minimum_spanning_tree`, `number_of_spanning_trees`, `is_tree` | `O(E log V)` or better, depending on function | Covers weighted and structural tree utilities |
| DAG | `topological_sort`, `dag_longest_path`, `transitive_closure`, `transitive_reduction` | `O(V + E)` to graph-dependent | Deterministic ordering matters for parity |
| Community | `girvan_newman`, `greedy_modularity_communities`, `label_propagation_communities` | graph-dependent | Use on moderate graph sizes first |
| Isomorphism | `is_isomorphic`, `could_be_isomorphic`, `fast_could_be_isomorphic` | graph-dependent | Exact and heuristic surfaces coexist |

## Weighted Shortest Path

```python
import franken_networkx as fnx

graph = fnx.Graph()
graph.add_edge("a", "b", weight=2.0)
graph.add_edge("b", "c", weight=1.5)
graph.add_edge("a", "c", weight=10.0)

path = fnx.shortest_path(graph, "a", "c", weight="weight")
length = fnx.shortest_path_length(graph, "a", "c", weight="weight")

assert path == ["a", "b", "c"]
assert abs(length - 3.5) < 1e-9
```

## Centrality

```python
cycle = fnx.cycle_graph(6)
scores = fnx.pagerank(cycle)

assert len(scores) == 6
assert abs(sum(scores.values()) - 1.0) < 1e-9
```

## Flow

```python
flow_graph = fnx.DiGraph()
flow_graph.add_edge("s", "a", capacity=3)
flow_graph.add_edge("s", "b", capacity=2)
flow_graph.add_edge("a", "b", capacity=1)
flow_graph.add_edge("a", "t", capacity=2)
flow_graph.add_edge("b", "t", capacity=3)

value = fnx.maximum_flow_value(flow_graph, "s", "t")

assert value == 5
```

## DAG Utilities

```python
dag = fnx.DiGraph()
dag.add_edges_from(
    [
        ("ingest", "normalize"),
        ("normalize", "score"),
        ("score", "publish"),
    ]
)

order = list(fnx.topological_sort(dag))
closure = fnx.transitive_closure(dag)

assert order == ["ingest", "normalize", "score", "publish"]
assert closure.has_edge("ingest", "publish")
```

## Serialization and Conversion

Algorithm work often sits next to I/O and conversion calls:

- `node_link_data` and `node_link_graph` for JSON-friendly structures,
- `read_edgelist`, `write_edgelist`, `read_graphml`, `write_graphml`,
- `to_numpy_array`, `from_numpy_array`, `to_scipy_sparse_array`.

See [quickstart.md](quickstart.md) for a small round-trip example and [contributing.md](contributing.md) for where these surfaces live in the Rust workspace.
