#!/usr/bin/env python3
"""
Rigorous profiling benchmark comparing fnx vs nx.

Methodology:
- 20+ runs per scenario to get stable statistics
- Reports p50/p95/p99 latencies
- Graph sizes chosen to exercise real-world load (1K-10K nodes)
- Covers hot algorithm families: centrality, clustering, shortest-path, traversal
"""

import sys
import time
import statistics
import platform
import json
from datetime import datetime, timezone

sys.path.insert(0, '/data/projects/franken_networkx/python')

import networkx as nx
import franken_networkx as fnx


def measure(fn, runs=25, warmup=3):
    """Run fn multiple times, return (p50, p95, p99, min, max) in ms."""
    for _ in range(warmup):
        fn()

    times = []
    for _ in range(runs):
        start = time.perf_counter()
        fn()
        elapsed = (time.perf_counter() - start) * 1000
        times.append(elapsed)

    times.sort()
    n = len(times)
    p50 = times[n // 2]
    p95 = times[int(n * 0.95)]
    p99 = times[int(n * 0.99)]
    return {
        'p50': round(p50, 3),
        'p95': round(p95, 3),
        'p99': round(p99, 3),
        'min': round(min(times), 3),
        'max': round(max(times), 3),
        'mean': round(statistics.mean(times), 3),
        'stdev': round(statistics.stdev(times), 3) if len(times) > 1 else 0,
    }


def environment_fingerprint():
    """Capture environment details for reproducibility."""
    return {
        'python_version': platform.python_version(),
        'platform': platform.platform(),
        'processor': platform.processor(),
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'nx_version': nx.__version__,
    }


def run_benchmarks():
    """Run all benchmark scenarios."""

    # Graph fixtures
    print("Building test graphs...")
    G_ba_1k = nx.barabasi_albert_graph(1000, 5, seed=42)
    G_ba_5k = nx.barabasi_albert_graph(5000, 5, seed=42)
    G_ws_1k = nx.watts_strogatz_graph(1000, 6, 0.3, seed=42)
    G_er_2k = nx.erdos_renyi_graph(2000, 0.01, seed=42)

    fnx_ba_1k = fnx.barabasi_albert_graph(1000, 5, seed=42)
    fnx_ba_5k = fnx.barabasi_albert_graph(5000, 5, seed=42)
    fnx_ws_1k = fnx.watts_strogatz_graph(1000, 6, 0.3, seed=42)
    fnx_er_2k = fnx.erdos_renyi_graph(2000, 0.01, seed=42)

    # DiGraph for directed algorithms
    DG_nx = nx.DiGraph(G_ba_1k)
    DG_fnx = fnx.DiGraph(fnx_ba_1k)

    scenarios = [
        # (name, nx_fn, fnx_fn, description)
        (
            "betweenness_centrality_1k",
            lambda: nx.betweenness_centrality(G_ba_1k),
            lambda: fnx.betweenness_centrality(fnx_ba_1k),
            "Betweenness centrality on 1K-node BA graph"
        ),
        (
            "closeness_centrality_1k",
            lambda: nx.closeness_centrality(G_ba_1k),
            lambda: fnx.closeness_centrality(fnx_ba_1k),
            "Closeness centrality on 1K-node BA graph"
        ),
        (
            "degree_centrality_5k",
            lambda: nx.degree_centrality(G_ba_5k),
            lambda: fnx.degree_centrality(fnx_ba_5k),
            "Degree centrality on 5K-node BA graph"
        ),
        (
            "clustering_1k",
            lambda: nx.clustering(G_ba_1k),
            lambda: fnx.clustering(fnx_ba_1k),
            "Local clustering coefficients on 1K-node BA graph"
        ),
        (
            "average_clustering_1k",
            lambda: nx.average_clustering(G_ba_1k),
            lambda: fnx.average_clustering(fnx_ba_1k),
            "Average clustering coefficient on 1K-node BA graph"
        ),
        (
            "transitivity_1k",
            lambda: nx.transitivity(G_ws_1k),
            lambda: fnx.transitivity(fnx_ws_1k),
            "Global transitivity on 1K-node WS graph"
        ),
        (
            "shortest_path_length_1k",
            lambda: nx.shortest_path_length(G_ba_1k, 0, 500),
            lambda: fnx.shortest_path_length(fnx_ba_1k, 0, 500),
            "Single-pair shortest path on 1K BA graph"
        ),
        (
            "all_pairs_shortest_path_length_500",
            lambda: dict(nx.all_pairs_shortest_path_length(nx.barabasi_albert_graph(500, 3, seed=42))),
            lambda: dict(fnx.all_pairs_shortest_path_length(fnx.barabasi_albert_graph(500, 3, seed=42))),
            "All-pairs shortest path lengths on 500-node BA graph"
        ),
        (
            "dijkstra_path_1k",
            lambda: nx.dijkstra_path(G_ba_1k, 0, 500),
            lambda: fnx.dijkstra_path(fnx_ba_1k, 0, 500),
            "Dijkstra single-pair path on 1K BA graph"
        ),
        (
            "bfs_edges_1k",
            lambda: list(nx.bfs_edges(G_ba_1k, 0)),
            lambda: list(fnx.bfs_edges(fnx_ba_1k, 0)),
            "BFS traversal edges on 1K BA graph"
        ),
        (
            "dfs_edges_1k",
            lambda: list(nx.dfs_edges(G_ba_1k, 0)),
            lambda: list(fnx.dfs_edges(fnx_ba_1k, 0)),
            "DFS traversal edges on 1K BA graph"
        ),
        (
            "connected_components_2k",
            lambda: list(nx.connected_components(G_er_2k)),
            lambda: list(fnx.connected_components(fnx_er_2k)),
            "Connected components on 2K ER graph"
        ),
        (
            "number_connected_components_2k",
            lambda: nx.number_connected_components(G_er_2k),
            lambda: fnx.number_connected_components(fnx_er_2k),
            "Count connected components on 2K ER graph"
        ),
        (
            "core_number_1k",
            lambda: nx.core_number(G_ba_1k),
            lambda: fnx.core_number(fnx_ba_1k),
            "K-core decomposition on 1K BA graph"
        ),
        (
            "pagerank_1k",
            lambda: nx.pagerank(G_ba_1k),
            lambda: fnx.pagerank(fnx_ba_1k),
            "PageRank on 1K BA graph"
        ),
        (
            "is_connected_5k",
            lambda: nx.is_connected(G_ba_5k),
            lambda: fnx.is_connected(fnx_ba_5k),
            "Connectivity check on 5K BA graph"
        ),
        (
            "diameter_1k",
            lambda: nx.diameter(G_ba_1k),
            lambda: fnx.diameter(fnx_ba_1k),
            "Graph diameter on 1K BA graph"
        ),
        (
            "is_biconnected_1k",
            lambda: nx.is_biconnected(G_ba_1k),
            lambda: fnx.is_biconnected(fnx_ba_1k),
            "Biconnectivity check on 1K BA graph"
        ),
        (
            "strongly_connected_1k",
            lambda: nx.is_strongly_connected(DG_nx),
            lambda: fnx.is_strongly_connected(DG_fnx),
            "Strong connectivity on 1K directed BA graph"
        ),
        (
            "weakly_connected_1k",
            lambda: nx.is_weakly_connected(DG_nx),
            lambda: fnx.is_weakly_connected(DG_fnx),
            "Weak connectivity on 1K directed BA graph"
        ),
    ]

    results = []
    print(f"\nRunning {len(scenarios)} benchmark scenarios (25 runs each)...\n")
    print(f"{'Scenario':<35} {'NX p50':>10} {'FNX p50':>10} {'Ratio':>8} {'Status':<12}")
    print("-" * 80)

    for name, nx_fn, fnx_fn, desc in scenarios:
        try:
            nx_stats = measure(nx_fn)
            fnx_stats = measure(fnx_fn)

            ratio = fnx_stats['p50'] / nx_stats['p50'] if nx_stats['p50'] > 0 else float('inf')

            if ratio < 0.9:
                status = "FASTER"
            elif ratio <= 1.1:
                status = "PARITY"
            elif ratio <= 2.0:
                status = "SLOWER"
            else:
                status = "REGRESS"

            print(f"{name:<35} {nx_stats['p50']:>9.2f}ms {fnx_stats['p50']:>9.2f}ms {ratio:>7.2f}x {status:<12}")

            results.append({
                'scenario': name,
                'description': desc,
                'nx': nx_stats,
                'fnx': fnx_stats,
                'ratio': round(ratio, 3),
                'status': status,
            })
        except Exception as e:
            print(f"{name:<35} ERROR: {e}")
            results.append({
                'scenario': name,
                'description': desc,
                'error': str(e),
            })

    return results


def main():
    print("=" * 80)
    print("FrankenNetworkX vs NetworkX Profiling Benchmark")
    print("=" * 80)

    env = environment_fingerprint()
    print(f"\nEnvironment:")
    print(f"  Python: {env['python_version']}")
    print(f"  Platform: {env['platform']}")
    print(f"  NetworkX: {env['nx_version']}")
    print(f"  Timestamp: {env['timestamp']}")

    results = run_benchmarks()

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    faster = [r for r in results if r.get('status') == 'FASTER']
    parity = [r for r in results if r.get('status') == 'PARITY']
    slower = [r for r in results if r.get('status') == 'SLOWER']
    regress = [r for r in results if r.get('status') == 'REGRESS']
    errors = [r for r in results if 'error' in r]

    print(f"\n  FASTER (< 0.9x):  {len(faster)}")
    print(f"  PARITY (0.9-1.1x): {len(parity)}")
    print(f"  SLOWER (1.1-2x):  {len(slower)}")
    print(f"  REGRESS (> 2x):   {len(regress)}")
    print(f"  ERRORS:           {len(errors)}")

    if regress:
        print("\n  REGRESSIONS (need investigation):")
        for r in sorted(regress, key=lambda x: x.get('ratio', 0), reverse=True):
            print(f"    - {r['scenario']}: {r['ratio']:.1f}x slower")

    # Write detailed JSON report
    report = {
        'environment': env,
        'results': results,
        'summary': {
            'faster': len(faster),
            'parity': len(parity),
            'slower': len(slower),
            'regress': len(regress),
            'errors': len(errors),
        }
    }

    report_path = '/data/projects/franken_networkx/docs/profiling_benchmark_report.json'
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    print(f"\nDetailed report written to: {report_path}")


if __name__ == '__main__':
    main()
