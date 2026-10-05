"""Thread-safety tests for GIL release in algorithm bindings.

Verifies that py.allow_threads() correctly releases and re-acquires the GIL,
and that concurrent Python threads can safely call FrankenNetworkX operations.

Run with: python -m pytest tests/python/test_thread_safety.py -v
"""

import concurrent.futures
import json
import os
import subprocess
import sys
import threading

import pytest

try:
    import franken_networkx as fnx
except ImportError:
    pytest.skip("franken_networkx not installed", allow_module_level=True)


# ---------------------------------------------------------------------------
# Shared fixtures — read-only graphs built once per module
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def large_path():
    """Path graph with 200 nodes."""
    g = fnx.Graph()
    for i in range(200):
        g.add_node(i)
    for i in range(199):
        g.add_edge(i, i + 1, weight=1.0)
    return g


@pytest.fixture(scope="module")
def large_complete():
    """Complete graph K_30."""
    g = fnx.Graph()
    for i in range(30):
        for j in range(i + 1, 30):
            g.add_edge(i, j, weight=1.0)
    return g


@pytest.fixture(scope="module")
def connected_graph():
    """A connected graph with some structure."""
    g = fnx.Graph()
    # Ring of 50 nodes
    for i in range(50):
        g.add_edge(i, (i + 1) % 50, weight=1.0)
    # Cross edges for richer structure
    for i in range(0, 50, 5):
        g.add_edge(i, (i + 25) % 50, weight=2.0)
    return g


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NUM_WORKERS = 4
ITERATIONS = 100


# Fresh interpreters are essential: an already initialized pool hides first-use
# failure. These are real OS limits, not a mocked ThreadPoolBuildError.
_RESOURCE_PROBE = r'''
import concurrent.futures, hashlib, io, json, os, platform, resource, sys, threading, time
from pathlib import Path
import franken_networkx as fnx
import franken_networkx._fnx as native
import networkx as nx

limit = 2 * 1024**3
resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
identity = dict(host=platform.node(), python=sys.executable, nx_version=nx.__version__,
                so_sha256=hashlib.sha256(Path(native.__file__).read_bytes()).hexdigest(),
                address_space_limit=limit, cpu_count=os.cpu_count(),
                affinity_count=len(os.sched_getaffinity(0)),
                requested_threads=os.environ.get("RAYON_NUM_THREADS", "default"))
mode, concurrent_first = sys.argv[1], sys.argv[2] == "concurrent"
graph = fnx.karate_club_graph()
oracle = nx.karate_club_graph()
expected_diameter = nx.diameter(oracle)
before = list(graph.edges())
pool_graph = fnx.cycle_graph(520)

def first_call(graph=graph):
    with fnx.compatibility_mode(mode):
        assert fnx.get_compatibility_mode() == mode
        result = fnx.diameter(graph)
        assert fnx.diameter(pool_graph) == 260
        assert fnx.get_compatibility_mode() == mode
        assert result == expected_diameter
        return result

if concurrent_first:
    barrier = threading.Barrier(3)
    def simultaneous():
        barrier.wait(timeout=10)
        return first_call()
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as workers:
        assert list(workers.map(lambda _: simultaneous(), range(3))) == [expected_diameter] * 3
else:
    first_call()
first_call()
assert list(graph.edges()) == before
print(json.dumps(dict(case_id="karate-default-first-use", n=len(graph), m=graph.number_of_edges(),
                      result=expected_diameter, mode=mode, concurrent=concurrent_first, **identity)), flush=True)

# Cross the production parallel thresholds, with independently constructed
# oracle graphs. Integer-valued distances/clustering are compared exactly;
# floats retain their original source-ordered arithmetic (no widened epsilon).
graph = fnx.cycle_graph(520)
oracle = nx.cycle_graph(520)
operations = [
    ("eccentricity", lambda api, g: api.eccentricity(g)),
    ("diameter", lambda api, g: api.diameter(g)),
    ("closeness", lambda api, g: api.closeness_centrality(g)),
    ("harmonic", lambda api, g: api.harmonic_centrality(g)),
    ("betweenness", lambda api, g: api.betweenness_centrality(g)),
    ("edge_betweenness", lambda api, g: api.edge_betweenness_centrality(g)),
    ("clustering", lambda api, g: api.clustering(g)),
    ("triangles", lambda api, g: api.triangles(g)),
    ("transitivity", lambda api, g: api.transitivity(g)),
    ("aspl", lambda api, g: api.average_shortest_path_length(g)),
    ("all_pairs_bfs", lambda api, g: dict(api.all_pairs_shortest_path_length(g))),
    ("all_pairs_dijkstra", lambda api, g: dict(api.all_pairs_dijkstra_path_length(g))),
    ("sampled_betweenness", lambda api, g: api.betweenness_centrality(g, k=2, seed=17)),
    ("load", lambda api, g: api.load_centrality(g)),
    ("weighted_betweenness", lambda api, g: api.betweenness_centrality(g, weight="weight")),
    ("weighted_edge_betweenness", lambda api, g: api.edge_betweenness_centrality(g, weight="weight")),
    ("weighted_load", lambda api, g: api.load_centrality(g, weight="weight")),
    ("weighted_percolation", lambda api, g: api.percolation_centrality(g, states={i: 1.0 for i in g}, weight="weight")),
]
for name, operation in operations:
    start = time.monotonic()
    expected = operation(nx, oracle)
    nx_seconds = time.monotonic() - start
    start = time.monotonic()
    with fnx.compatibility_mode(mode):
        actual = operation(fnx, graph)
        assert fnx.get_compatibility_mode() == mode
    assert actual == expected, (name, actual, expected)
    print(json.dumps(dict(case_id=name, n=len(graph), m=graph.number_of_edges(),
                          fnx_seconds=time.monotonic()-start, nx_seconds=nx_seconds,
                          mode=mode, equal=True, **identity)), flush=True)

# Parser shares the worker pool; retain line/node/edge order on fallback too.
content = "".join(f"{i} {i+1}\n" for i in range(12000))
with fnx.compatibility_mode(mode):
    parsed = fnx.read_edgelist(io.BytesIO(content.encode()), data=False)
reference = nx.read_edgelist(io.BytesIO(content.encode()), data=False)
assert list(parsed.nodes()) == list(reference.nodes())
assert list(parsed.edges()) == list(reference.edges())
print(json.dumps(dict(case_id="ordered-edgelist", n=len(parsed), m=parsed.number_of_edges(),
                      mode=mode, equal=True, **identity)), flush=True)

# An algorithm error must still propagate, and must not poison the next call.
broken = fnx.Graph([(0, 1), (2, 3)])
try:
    fnx.diameter(broken)
except fnx.NetworkXError:
    pass
else:
    raise AssertionError("disconnected graph was accepted")
assert first_call() == expected_diameter
names = [p.read_text().strip() for p in Path("/proc/self/task").glob("*/comm")]
effective = sum(name.startswith("fnx-rayon-") for name in names)
print(json.dumps(dict(case_id="usable-after-capacity-and-algorithm-error",
                      effective_worker_threads=effective, peak_rss_kb=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                      task_names=names, **identity)), flush=True)
'''


@pytest.mark.skipif(sys.platform != "linux", reason="real Linux address-space/task probes")
@pytest.mark.parametrize("threads", [None, "1", "2", "4096"])
@pytest.mark.parametrize("mode", ["strict", "hardened"])
def test_parallel_first_use_under_real_capacity_limit(threads, mode, tmp_path):
    """Capacity failure must yield correct serial results, not PanicException."""
    env = os.environ.copy()
    env.pop("RAYON_NUM_THREADS", None)
    env.pop("RAYON_RS_NUM_CPUS", None)
    env.update(OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1")
    if threads is not None:
        env["RAYON_NUM_THREADS"] = threads
    result = subprocess.run(
        [sys.executable, "-I", "-c", _RESOURCE_PROBE, mode,
         "concurrent" if mode == "hardened" else "serial"],
        env=env, capture_output=True, text=True, timeout=90, check=False,
    )
    (tmp_path / "probe.stdout.jsonl").write_text(result.stdout)
    (tmp_path / "probe.stderr.log").write_text(result.stderr)
    print(result.stdout, end="")
    print(result.stderr, end="", file=sys.stderr)
    assert result.returncode == 0, result.stderr
    assert "PanicException" not in result.stderr
    records = [json.loads(line) for line in result.stdout.splitlines()]
    assert len(records) == 21
    assert records[-1]["case_id"] == "usable-after-capacity-and-algorithm-error"
    if threads in ("1", "2"):
        assert records[-1]["effective_worker_threads"] == int(threads)
    if threads == "4096":
        assert "using serial kernels" in result.stderr
        assert records[-1]["effective_worker_threads"] == 0


# ---------------------------------------------------------------------------
# Concurrent read-only algorithm tests
# ---------------------------------------------------------------------------

class TestConcurrentShortestPath:
    """Multiple threads computing shortest paths on a shared graph."""

    def test_concurrent_shortest_path(self, large_path):
        """Concurrent shortest_path calls should all return correct results."""
        barrier = threading.Barrier(NUM_WORKERS)
        results = []
        errors = []

        def worker():
            try:
                barrier.wait(timeout=5)
                for _ in range(ITERATIONS):
                    path = fnx.shortest_path(large_path, 0, 199, weight="weight")
                    assert len(path) == 200
                    assert path[0] == 0
                    assert path[-1] == 199
                results.append(True)
            except Exception as e:
                errors.append(e)

        with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_WORKERS) as pool:
            futures = [pool.submit(worker) for _ in range(NUM_WORKERS)]
            concurrent.futures.wait(futures)

        assert not errors, f"Thread errors: {errors}"
        assert len(results) == NUM_WORKERS

    def test_concurrent_has_path(self, large_path):
        """Concurrent has_path calls."""
        barrier = threading.Barrier(NUM_WORKERS)
        errors = []

        def worker():
            try:
                barrier.wait(timeout=5)
                for _ in range(ITERATIONS):
                    assert fnx.has_path(large_path, 0, 199)
                    assert fnx.has_path(large_path, 50, 100)
            except Exception as e:
                errors.append(e)

        with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_WORKERS) as pool:
            futures = [pool.submit(worker) for _ in range(NUM_WORKERS)]
            concurrent.futures.wait(futures)

        assert not errors, f"Thread errors: {errors}"


class TestConcurrentCentrality:
    """Multiple threads computing centrality metrics."""

    def test_concurrent_betweenness(self, connected_graph):
        """Concurrent betweenness_centrality calls."""
        barrier = threading.Barrier(NUM_WORKERS)
        results = []
        errors = []

        def worker():
            try:
                barrier.wait(timeout=5)
                for _ in range(ITERATIONS // 10):  # Betweenness is expensive
                    bc = fnx.betweenness_centrality(connected_graph)
                    assert len(bc) == 50
                    assert all(0 <= v <= 1 for v in bc.values())
                results.append(True)
            except Exception as e:
                errors.append(e)

        with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_WORKERS) as pool:
            futures = [pool.submit(worker) for _ in range(NUM_WORKERS)]
            concurrent.futures.wait(futures)

        assert not errors, f"Thread errors: {errors}"
        assert len(results) == NUM_WORKERS

    def test_concurrent_pagerank(self, connected_graph):
        """Concurrent pagerank calls."""
        barrier = threading.Barrier(NUM_WORKERS)
        errors = []

        def worker():
            try:
                barrier.wait(timeout=5)
                for _ in range(ITERATIONS // 5):
                    pr = fnx.pagerank(connected_graph)
                    assert len(pr) == 50
                    total = sum(pr.values())
                    assert abs(total - 1.0) < 0.01
            except Exception as e:
                errors.append(e)

        with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_WORKERS) as pool:
            futures = [pool.submit(worker) for _ in range(NUM_WORKERS)]
            concurrent.futures.wait(futures)

        assert not errors, f"Thread errors: {errors}"

    def test_concurrent_degree_centrality(self, connected_graph):
        """Concurrent degree_centrality calls."""
        barrier = threading.Barrier(NUM_WORKERS)
        errors = []

        def worker():
            try:
                barrier.wait(timeout=5)
                for _ in range(ITERATIONS):
                    dc = fnx.degree_centrality(connected_graph)
                    assert len(dc) == 50
            except Exception as e:
                errors.append(e)

        with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_WORKERS) as pool:
            futures = [pool.submit(worker) for _ in range(NUM_WORKERS)]
            concurrent.futures.wait(futures)

        assert not errors, f"Thread errors: {errors}"


class TestConcurrentClustering:
    """Concurrent clustering computations."""

    def test_concurrent_clustering(self, connected_graph):
        """Concurrent clustering coefficient calls."""
        barrier = threading.Barrier(NUM_WORKERS)
        errors = []

        def worker():
            try:
                barrier.wait(timeout=5)
                for _ in range(ITERATIONS // 5):
                    cc = fnx.clustering(connected_graph)
                    assert len(cc) == 50
            except Exception as e:
                errors.append(e)

        with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_WORKERS) as pool:
            futures = [pool.submit(worker) for _ in range(NUM_WORKERS)]
            concurrent.futures.wait(futures)

        assert not errors, f"Thread errors: {errors}"

    def test_concurrent_transitivity(self, connected_graph):
        """Concurrent transitivity calls."""
        barrier = threading.Barrier(NUM_WORKERS)
        errors = []

        def worker():
            try:
                barrier.wait(timeout=5)
                for _ in range(ITERATIONS):
                    t = fnx.transitivity(connected_graph)
                    assert 0 <= t <= 1
            except Exception as e:
                errors.append(e)

        with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_WORKERS) as pool:
            futures = [pool.submit(worker) for _ in range(NUM_WORKERS)]
            concurrent.futures.wait(futures)

        assert not errors, f"Thread errors: {errors}"


class TestConcurrentConnectivity:
    """Concurrent connectivity checks."""

    def test_concurrent_is_connected(self, connected_graph):
        """Concurrent is_connected calls."""
        barrier = threading.Barrier(NUM_WORKERS)
        errors = []

        def worker():
            try:
                barrier.wait(timeout=5)
                for _ in range(ITERATIONS):
                    assert fnx.is_connected(connected_graph)
            except Exception as e:
                errors.append(e)

        with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_WORKERS) as pool:
            futures = [pool.submit(worker) for _ in range(NUM_WORKERS)]
            concurrent.futures.wait(futures)

        assert not errors, f"Thread errors: {errors}"

    def test_concurrent_connected_components(self, connected_graph):
        """Concurrent connected_components calls."""
        barrier = threading.Barrier(NUM_WORKERS)
        errors = []

        def worker():
            try:
                barrier.wait(timeout=5)
                for _ in range(ITERATIONS):
                    comps = list(fnx.connected_components(connected_graph))
                    assert len(comps) == 1
                    assert len(comps[0]) == 50
            except Exception as e:
                errors.append(e)

        with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_WORKERS) as pool:
            futures = [pool.submit(worker) for _ in range(NUM_WORKERS)]
            concurrent.futures.wait(futures)

        assert not errors, f"Thread errors: {errors}"


class TestConcurrentMixedAlgorithms:
    """Different algorithms running simultaneously."""

    def test_mixed_algorithms_concurrent(self, connected_graph):
        """Different algorithm calls interleaved across threads."""
        barrier = threading.Barrier(NUM_WORKERS)
        errors = []

        def worker_shortest_path():
            try:
                barrier.wait(timeout=5)
                for _ in range(ITERATIONS):
                    fnx.shortest_path(connected_graph, 0, 25, weight="weight")
            except Exception as e:
                errors.append(("shortest_path", e))

        def worker_centrality():
            try:
                barrier.wait(timeout=5)
                for _ in range(ITERATIONS // 5):
                    fnx.betweenness_centrality(connected_graph)
            except Exception as e:
                errors.append(("centrality", e))

        def worker_clustering():
            try:
                barrier.wait(timeout=5)
                for _ in range(ITERATIONS // 5):
                    fnx.clustering(connected_graph)
            except Exception as e:
                errors.append(("clustering", e))

        def worker_connectivity():
            try:
                barrier.wait(timeout=5)
                for _ in range(ITERATIONS):
                    fnx.is_connected(connected_graph)
                    fnx.density(connected_graph)
            except Exception as e:
                errors.append(("connectivity", e))

        with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_WORKERS) as pool:
            futures = [
                pool.submit(worker_shortest_path),
                pool.submit(worker_centrality),
                pool.submit(worker_clustering),
                pool.submit(worker_connectivity),
            ]
            concurrent.futures.wait(futures)

        assert not errors, f"Thread errors: {errors}"

    def test_concurrent_distance_measures(self, connected_graph):
        """Concurrent distance measure computations."""
        barrier = threading.Barrier(NUM_WORKERS)
        errors = []

        def worker():
            try:
                barrier.wait(timeout=5)
                for _ in range(ITERATIONS // 5):
                    fnx.eccentricity(connected_graph)
                    fnx.diameter(connected_graph)
                    fnx.radius(connected_graph)
            except Exception as e:
                errors.append(e)

        with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_WORKERS) as pool:
            futures = [pool.submit(worker) for _ in range(NUM_WORKERS)]
            concurrent.futures.wait(futures)

        assert not errors, f"Thread errors: {errors}"


class TestConcurrentGraphCreation:
    """Concurrent graph creation (no shared mutation)."""

    def test_concurrent_independent_graph_creation(self):
        """Each thread creates and operates on its own graph."""
        barrier = threading.Barrier(NUM_WORKERS)
        errors = []

        def worker(thread_id):
            try:
                barrier.wait(timeout=5)
                for _ in range(ITERATIONS // 2):
                    g = fnx.Graph()
                    for i in range(20):
                        g.add_edge(i, (i + 1) % 20, weight=1.0)
                    assert fnx.is_connected(g)
                    path = fnx.shortest_path(g, 0, 10, weight="weight")
                    assert len(path) > 0
                    bc = fnx.betweenness_centrality(g)
                    assert len(bc) == 20
            except Exception as e:
                errors.append((thread_id, e))

        with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_WORKERS) as pool:
            futures = [pool.submit(worker, i) for i in range(NUM_WORKERS)]
            concurrent.futures.wait(futures)

        assert not errors, f"Thread errors: {errors}"


class TestConcurrentResultConsistency:
    """Verify results are consistent across concurrent calls."""

    def test_deterministic_results(self, connected_graph):
        """All threads should get identical results for the same computation."""
        barrier = threading.Barrier(NUM_WORKERS)
        all_results = []
        errors = []

        def worker():
            try:
                barrier.wait(timeout=5)
                dc = fnx.degree_centrality(connected_graph)
                all_results.append(dc)
            except Exception as e:
                errors.append(e)

        with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_WORKERS) as pool:
            futures = [pool.submit(worker) for _ in range(NUM_WORKERS)]
            concurrent.futures.wait(futures)

        assert not errors, f"Thread errors: {errors}"
        assert len(all_results) == NUM_WORKERS
        # All results should be identical.
        reference = all_results[0]
        for i, result in enumerate(all_results[1:], 1):
            assert set(result.keys()) == set(reference.keys()), (
                f"Thread {i} keys differ"
            )
            for k in reference:
                assert abs(result[k] - reference[k]) < 1e-10, (
                    f"Thread {i} value for {k} differs: {result[k]} vs {reference[k]}"
                )
