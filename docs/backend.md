# Backend Integration

FrankenNetworkX plugs into the NetworkX backend protocol so you can keep a `networkx`-shaped application while accelerating supported calls in Rust.

For direct imports, see [quickstart.md](quickstart.md). For migration patterns, see [migration.md](migration.md).

## Install and Enable

```bash
pip install franken-networkx
```

```python
import networkx as nx

nx.config.backend_priority = ["franken_networkx"]
```

Once that is set, supported algorithms can dispatch into FrankenNetworkX either implicitly or with an explicit `backend="franken_networkx"` override.

## Per-Call Dispatch

```python
import networkx as nx

nx.config.warnings_to_ignore.add("cache")
path_graph = nx.path_graph(8)
cycle_graph = nx.cycle_graph(6)

path = nx.shortest_path(path_graph, 0, 7, backend="franken_networkx")
pagerank = nx.pagerank(cycle_graph, backend="franken_networkx")
components = list(nx.connected_components(path_graph, backend="franken_networkx"))

assert path == list(range(8))
assert abs(sum(pagerank.values()) - 1.0) < 1e-9
assert len(components) == 1
```

## Introspecting the Backend Interface

```python
from franken_networkx.backend import BackendInterface

fnx_graph = BackendInterface.convert_from_nx(path_graph)
roundtrip = BackendInterface.convert_to_nx(fnx_graph)

assert BackendInterface.can_run("shortest_path", (fnx_graph, 0, 7), {})
assert BackendInterface.should_run("pagerank", (fnx_graph,), {})
assert list(roundtrip.nodes()) == list(path_graph.nodes())
```

## What Dispatches Today

The backend registry covers the library's high-value algorithm families, including:

- shortest path and traversal,
- connectivity and cuts,
- centrality and clustering,
- flow and spanning tree surfaces,
- DAG utilities,
- graph generators and conversion helpers.

The authoritative supported surface lives in [`python/franken_networkx/backend.py`](../python/franken_networkx/backend.py) and the top-level list in [README.md](../README.md).

## Fallback Model

FrankenNetworkX is fail-closed about unsupported paths:

- unsupported backend calls stay in NetworkX,
- callback-heavy or custom-cost paths may delegate back to NetworkX,
- drawing APIs continue to use NetworkX and matplotlib.

This keeps compatibility predictable while still accelerating the common cases.

## When To Prefer Backend Mode

Backend mode is the right choice when:

- you already have a large NetworkX codebase,
- you want a low-risk acceleration path,
- you want to opt into Rust without changing import sites everywhere.

If you are starting greenfield work or want explicit control over graph types, use standalone `import franken_networkx as fnx`.
