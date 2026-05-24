#!/usr/bin/env python3
"""Benchmark BFS and connected_components performance: fnx vs nx."""

import time
import networkx as nx
import franken_networkx as fnx

def benchmark_connected_components(n_nodes, edge_prob, seed=42):
    """Benchmark connected_components on a random graph."""
    import random
    random.seed(seed)

    # Create identical graphs
    nxG = nx.gnp_random_graph(n_nodes, edge_prob, seed=seed)
    fnxG = fnx.gnp_random_graph(n_nodes, edge_prob, seed=seed)

    # Warm up
    list(nx.connected_components(nxG))
    list(fnx.connected_components(fnxG))

    # Benchmark nx
    iterations = 10
    start = time.perf_counter()
    for _ in range(iterations):
        list(nx.connected_components(nxG))
    nx_time = (time.perf_counter() - start) / iterations

    # Benchmark fnx
    start = time.perf_counter()
    for _ in range(iterations):
        list(fnx.connected_components(fnxG))
    fnx_time = (time.perf_counter() - start) / iterations

    return nx_time, fnx_time

def benchmark_bfs_edges(n_nodes, edge_prob, seed=42):
    """Benchmark bfs_edges on a random graph."""
    nxG = nx.gnp_random_graph(n_nodes, edge_prob, seed=seed)
    fnxG = fnx.gnp_random_graph(n_nodes, edge_prob, seed=seed)

    # Warm up
    list(nx.bfs_edges(nxG, 0))
    list(fnx.bfs_edges(fnxG, 0))

    # Benchmark nx
    iterations = 10
    start = time.perf_counter()
    for _ in range(iterations):
        list(nx.bfs_edges(nxG, 0))
    nx_time = (time.perf_counter() - start) / iterations

    # Benchmark fnx
    start = time.perf_counter()
    for _ in range(iterations):
        list(fnx.bfs_edges(fnxG, 0))
    fnx_time = (time.perf_counter() - start) / iterations

    return nx_time, fnx_time

def benchmark_shortest_path(n_nodes, edge_prob, seed=42):
    """Benchmark single_source_shortest_path_length on a random graph."""
    nxG = nx.gnp_random_graph(n_nodes, edge_prob, seed=seed)
    fnxG = fnx.gnp_random_graph(n_nodes, edge_prob, seed=seed)

    # Warm up
    dict(nx.single_source_shortest_path_length(nxG, 0))
    dict(fnx.single_source_shortest_path_length(fnxG, 0))

    # Benchmark nx
    iterations = 10
    start = time.perf_counter()
    for _ in range(iterations):
        dict(nx.single_source_shortest_path_length(nxG, 0))
    nx_time = (time.perf_counter() - start) / iterations

    # Benchmark fnx
    start = time.perf_counter()
    for _ in range(iterations):
        dict(fnx.single_source_shortest_path_length(fnxG, 0))
    fnx_time = (time.perf_counter() - start) / iterations

    return nx_time, fnx_time

def main():
    print("BFS/Traversal Performance Benchmark: fnx vs nx")
    print("=" * 60)

    test_cases = [
        (500, 0.02),
        (1000, 0.01),
        (2000, 0.005),
        (5000, 0.002),
    ]

    print("\n--- connected_components ---")
    print(f"{'Nodes':>8} {'Edges':>8} {'nx (ms)':>10} {'fnx (ms)':>10} {'Ratio':>8}")
    for n, p in test_cases:
        nx_t, fnx_t = benchmark_connected_components(n, p)
        edges = int(n * (n-1) * p / 2)
        ratio = fnx_t / nx_t if nx_t > 0 else float('inf')
        print(f"{n:>8} {edges:>8} {nx_t*1000:>10.3f} {fnx_t*1000:>10.3f} {ratio:>8.2f}x")

    print("\n--- bfs_edges ---")
    print(f"{'Nodes':>8} {'Edges':>8} {'nx (ms)':>10} {'fnx (ms)':>10} {'Ratio':>8}")
    for n, p in test_cases:
        nx_t, fnx_t = benchmark_bfs_edges(n, p)
        edges = int(n * (n-1) * p / 2)
        ratio = fnx_t / nx_t if nx_t > 0 else float('inf')
        print(f"{n:>8} {edges:>8} {nx_t*1000:>10.3f} {fnx_t*1000:>10.3f} {ratio:>8.2f}x")

    print("\n--- single_source_shortest_path_length ---")
    print(f"{'Nodes':>8} {'Edges':>8} {'nx (ms)':>10} {'fnx (ms)':>10} {'Ratio':>8}")
    for n, p in test_cases:
        nx_t, fnx_t = benchmark_shortest_path(n, p)
        edges = int(n * (n-1) * p / 2)
        ratio = fnx_t / nx_t if nx_t > 0 else float('inf')
        print(f"{n:>8} {edges:>8} {nx_t*1000:>10.3f} {fnx_t*1000:>10.3f} {ratio:>8.2f}x")

if __name__ == "__main__":
    main()
