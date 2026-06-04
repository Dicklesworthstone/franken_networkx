import hashlib
import json

import franken_networkx as fnx
import networkx as nx


class DeterministicRng:
    def __init__(self, seed):
        self.state = seed & ((1 << 64) - 1)

    def next_u64(self):
        self.state = (self.state * 6364136223846793005 + 1442695040888963407) & (
            (1 << 64) - 1
        )
        return self.state

    def randbelow(self, upper):
        return self.next_u64() % upper

    def randint(self, low, high):
        return low + self.randbelow(high - low + 1)

    def random_float(self):
        return (self.next_u64() >> 11) * (1.0 / (1 << 53))

    def sample_range(self, upper, count):
        values = list(range(upper))
        for index in range(count):
            swap = index + self.randbelow(upper - index)
            values[index], values[swap] = values[swap], values[index]
        return values[:count]


def build(graph_type, seed, node_count=40, edge_count=120, selfloops=True):
    rng = DeterministicRng(seed)
    graph = graph_type()
    for node in [5, 2, 9, 1, 7, 30, 3, 0]:
        graph.add_node(node, lbl=f"n{node}")
    graph.add_nodes_from(range(node_count))
    graph.graph["gattr"] = {"nested": [1, 2]}
    graph.graph["v"] = 7
    graph.add_edge(0, 1, key=77, data=[0, 1])
    for _ in range(edge_count):
        source = rng.randint(0, node_count - 1)
        target = rng.randint(0, node_count - 1)
        if not selfloops and source == target:
            target = (target + 1) % node_count
        key = rng.randint(0, 3)
        if key == 0:
            graph.add_edge(source, target, w=rng.random_float())
        elif key == 1:
            graph.add_edge(source, target, w=rng.randint(1, 9), tag="a")
        elif key == 2:
            graph.add_edge(source, target)
        else:
            graph.add_edge(source, target, data=[source, target])
    return graph


def snap(graph):
    return {
        "nodes": list(graph.nodes(data=True)),
        "edges": list(graph.edges(keys=True, data=True)),
        "graph": dict(graph.graph),
        "type": type(graph).__name__,
        "n": graph.number_of_nodes(),
        "m": graph.number_of_edges(),
    }


def require(condition, message):
    if not condition:
        raise AssertionError(message)


records = []
mismatches = 0
cases = [
    ("MultiGraph", fnx.MultiGraph, nx.MultiGraph),
    ("MultiDiGraph", fnx.MultiDiGraph, nx.MultiDiGraph),
]
for label, fnx_type, nx_type in cases:
    for seed in (1, 2, 3):
        for selfloops in (True, False):
            fnx_graph = build(fnx_type, seed, selfloops=selfloops)
            nx_graph = build(nx_type, seed, selfloops=selfloops)
            fnx_copy = fnx_graph.copy()
            nx_copy = nx_graph.copy()
            fnx_snapshot = snap(fnx_copy)
            nx_snapshot = snap(nx_copy)
            if fnx_snapshot != nx_snapshot:
                mismatches += 1
                for key in fnx_snapshot:
                    if fnx_snapshot[key] != nx_snapshot[key]:
                        print(
                            f"  COPY MISMATCH {label} s={seed} "
                            f"selfloops={selfloops} key={key}"
                        )
                        break

            subset = sorted(DeterministicRng(seed).sample_range(40, 18))
            fnx_subcopy = fnx_graph.subgraph(subset).copy()
            nx_subcopy = nx_graph.subgraph(subset).copy()
            if snap(fnx_subcopy) != snap(nx_subcopy):
                mismatches += 1
                print(f"  SUBGRAPH MISMATCH {label} s={seed} selfloops={selfloops}")

            shared = False
            for source, target, key, attrs in fnx_copy.edges(keys=True, data=True):
                if "data" in attrs:
                    require(
                        fnx_copy[source][target][key]["data"]
                        is fnx_graph[source][target][key]["data"],
                        "edge value must be shared",
                    )
                    require(
                        fnx_copy[source][target][key]
                        is not fnx_graph[source][target][key],
                        "edge attrs dict must be independent",
                    )
                    shared = True
                    break
            require(shared, "expected a shared-container edge")
            require(
                fnx_copy.graph["gattr"] is fnx_graph.graph["gattr"],
                "graph attr value shared",
            )
            fnx_copy.add_edge(999, 998)
            require(not fnx_graph.has_edge(999, 998), "copy structurally independent")
            require(type(fnx_copy).__name__ == type(fnx_graph).__name__, "copy type preserved")
            records.append(
                [
                    label,
                    seed,
                    selfloops,
                    [fnx_snapshot["nodes"], fnx_snapshot["edges"], fnx_snapshot["graph"]],
                ]
            )

blob = json.dumps(records, sort_keys=True, default=str).encode()
print(f"mismatches={mismatches}")
print(f"COPY_GOLDEN {hashlib.sha256(blob).hexdigest()}")
