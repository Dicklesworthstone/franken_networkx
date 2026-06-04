import argparse
import json
import statistics
import time


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


def build_graph(module, graph_type, nodes, edges, seed):
    rng = DeterministicRng(seed)
    graph = getattr(module, graph_type)()
    warm_nodes = [5, 2, 9, 1, 7, 30, 3, 0]
    for node in warm_nodes:
        graph.add_node(node, label=f"n{node}", payload=[node, node + 1])
    graph.add_nodes_from((node, {"label": f"bulk{node}"}) for node in range(nodes))
    graph.graph["payload"] = {"nested": [1, 2, 3], "name": graph_type}
    for edge_index in range(edges):
        source = rng.randbelow(nodes)
        target = rng.randbelow(nodes)
        key = rng.randbelow(4)
        if edge_index % 4 == 0:
            graph.add_edge(source, target, key=key, weight=rng.random_float(), tag="float")
        elif edge_index % 4 == 1:
            graph.add_edge(source, target, key=key, weight=rng.randint(1, 18))
        elif edge_index % 4 == 2:
            graph.add_edge(source, target, key=key, key_attr=f"k{edge_index}")
        else:
            graph.add_edge(source, target, key=key, payload=[source, target])
    return graph


def run_once(graph, operation, subgraph_size, seed):
    if operation == "copy":
        result = graph.copy()
    elif operation == "subgraph_copy":
        rng = DeterministicRng(seed)
        keep = sorted(rng.sample_range(graph.number_of_nodes(), subgraph_size))
        result = graph.subgraph(keep).copy()
    else:
        raise ValueError(f"unknown operation: {operation}")
    return result.number_of_nodes(), result.number_of_edges()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--library", choices=["fnx", "nx"], default="fnx")
    parser.add_argument("--graph-type", choices=["MultiGraph", "MultiDiGraph"], default="MultiGraph")
    parser.add_argument("--operation", choices=["copy", "subgraph_copy"], default="copy")
    parser.add_argument("--nodes", type=int, default=1200)
    parser.add_argument("--edges", type=int, default=8000)
    parser.add_argument("--subgraph-size", type=int, default=500)
    parser.add_argument("--iters", type=int, default=5)
    parser.add_argument("--seed", type=int, default=411)
    args = parser.parse_args()

    if args.library == "fnx":
        import franken_networkx as graph_module
    else:
        import networkx as graph_module

    graph = build_graph(graph_module, args.graph_type, args.nodes, args.edges, args.seed)
    warm_nodes, warm_edges = run_once(graph, args.operation, args.subgraph_size, args.seed)
    samples = []
    for iteration in range(args.iters):
        started = time.perf_counter()
        node_count, edge_count = run_once(
            graph,
            args.operation,
            args.subgraph_size,
            args.seed + iteration,
        )
        samples.append(time.perf_counter() - started)
        if node_count == 0 and edge_count == 0 and warm_nodes + warm_edges < 0:
            raise AssertionError("unreachable guard")

    record = {
        "library": args.library,
        "graph_type": args.graph_type,
        "operation": args.operation,
        "nodes": args.nodes,
        "edges": args.edges,
        "subgraph_size": args.subgraph_size,
        "iters": args.iters,
        "mean_seconds": statistics.fmean(samples),
        "median_seconds": statistics.median(samples),
        "min_seconds": min(samples),
        "max_seconds": max(samples),
        "samples_seconds": samples,
        "result_nodes": warm_nodes,
        "result_edges": warm_edges,
    }
    print(json.dumps(record, sort_keys=True))


if __name__ == "__main__":
    main()
