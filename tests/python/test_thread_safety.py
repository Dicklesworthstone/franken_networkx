"""Thread-safety tests for GIL release in algorithm bindings.

Verifies that py.allow_threads() correctly releases and re-acquires the GIL,
and that concurrent Python threads can safely call FrankenNetworkX operations.

Run with: python -m pytest tests/python/test_thread_safety.py -v
"""

import concurrent.futures
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
