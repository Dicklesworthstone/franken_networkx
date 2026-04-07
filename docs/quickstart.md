# Quickstart

FrankenNetworkX supports two modes:

- Standalone mode, where you import `franken_networkx` directly.
- Backend mode, where you keep importing `networkx` and dispatch supported calls into Rust.

For a broader map of the project, see [README.md](../README.md), [backend.md](backend.md), and [migration.md](migration.md).

## Installation

```bash
pip install franken-networkx
```

If you are developing locally from source, use:

```bash
maturin develop --features pyo3/abi3-py310
```

## Standalone Usage

```python
import franken_networkx as fnx

graph = fnx.Graph()
graph.add_edge("sfo", "oak", weight=14.0)
graph.add_edge("oak", "berkeley", weight=9.0)
graph.add_edge("sfo", "berkeley", weight=30.0)

path = fnx.shortest_path(graph, "sfo", "berkeley", weight="weight")
pagerank = fnx.pagerank(graph)
components = [sorted(component) for component in fnx.connected_components(graph)]

assert path == ["sfo", "oak", "berkeley"]
assert components == [["berkeley", "oak", "sfo"]]
assert abs(sum(pagerank.values()) - 1.0) < 1e-9
```

## NetworkX Backend Mode

```python
import networkx as nx

nx.config.backend_priority = ["franken_networkx"]
nx.config.warnings_to_ignore.add("cache")

graph = nx.path_graph(8)
path = nx.shortest_path(graph, 0, 7, backend="franken_networkx")
components = list(nx.connected_components(graph, backend="franken_networkx"))

assert path == list(range(8))
assert len(components) == 1
```

## Social Network Analysis

```python
club = fnx.karate_club_graph()
leaders = sorted(fnx.pagerank(club).items(), key=lambda item: item[1], reverse=True)[:5]
first_split = tuple(sorted(group) for group in next(fnx.girvan_newman(club)))

assert len(leaders) == 5
assert len(first_split) >= 2
```

This gives you a practical pattern for:

- graph loading/generation,
- deterministic centrality,
- community extraction that you can feed into downstream reporting.

## Weighted Road Routing

```python
roads = fnx.Graph()
roads.add_edge("warehouse", "north_hub", minutes=4.0)
roads.add_edge("north_hub", "clinic", minutes=6.0)
roads.add_edge("warehouse", "south_hub", minutes=7.0)
roads.add_edge("south_hub", "clinic", minutes=3.0)
roads.add_edge("north_hub", "south_hub", minutes=5.0)

best_route = fnx.shortest_path(roads, "warehouse", "clinic", weight="minutes")

assert best_route == ["warehouse", "north_hub", "clinic"]
```

## Biological Network Pattern

Use bipartite graphs when the two node sets represent different entity types, then compute clustering on a projected interaction graph.

```python
associations = fnx.Graph()
associations.add_edges_from(
    [
        ("gene:TP53", "pathway:apoptosis"),
        ("gene:BRCA1", "pathway:dna_repair"),
        ("gene:TP53", "pathway:dna_repair"),
        ("gene:EGFR", "pathway:signaling"),
    ]
)
left, right = fnx.bipartite_sets(associations)

interaction = fnx.Graph()
interaction.add_edges_from(
    [
        ("TP53", "BRCA1"),
        ("BRCA1", "RAD51"),
        ("TP53", "RAD51"),
        ("EGFR", "GRB2"),
    ]
)
clustering = fnx.clustering(interaction)

assert fnx.is_bipartite(associations)
assert "gene:TP53" in left or "gene:TP53" in right
assert clustering["TP53"] >= 0.0
```

## Serialization Round-Trips

```python
payload = fnx.node_link_data(roads)
restored = fnx.node_link_graph(payload)

assert restored.number_of_nodes() == roads.number_of_nodes()
assert restored.number_of_edges() == roads.number_of_edges()
```

For file-based examples, see [examples/basic_usage.py](../examples/basic_usage.py) and [examples/social_network.py](../examples/social_network.py).
