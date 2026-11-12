"""Performance benchmarks comparing FrankenNetworkX against pure NetworkX.

Run with:
    pytest tests/python/test_benchmarks.py --benchmark-only -v
    pytest tests/python/test_benchmarks.py --benchmark-only --benchmark-sort=name
    pytest tests/python/test_benchmarks.py --benchmark-only --benchmark-group-by=param:size

These tests are skipped automatically during regular pytest runs.
To execute them intentionally, pass ``--benchmark-only``.
"""

import pytest

try:
    import franken_networkx as fnx
    import networkx as nx

    FNX_AVAILABLE = True
except ImportError:
    FNX_AVAILABLE = False

pytestmark = [
    pytest.mark.skipif(not FNX_AVAILABLE, reason="fnx not installed"),
    pytest.mark.benchmark(group="fnx"),
]


# ---------------------------------------------------------------------------
# Graph construction helpers
# ---------------------------------------------------------------------------

def _build_fnx_path(n):
    G = fnx.Graph()
    for i in range(n - 1):
        G.add_edge(str(i), str(i + 1))
    return G


def _build_nx_path(n):
    G = nx.Graph()
    for i in range(n - 1):
        G.add_edge(str(i), str(i + 1))
    return G


def _build_fnx_complete(n):
    G = fnx.Graph()
    for i in range(n):
        for j in range(i + 1, n):
            G.add_edge(str(i), str(j))
    return G


def _build_nx_complete(n):
    G = nx.Graph()
    for i in range(n):
        for j in range(i + 1, n):
            G.add_edge(str(i), str(j))
    return G


def _build_fnx_gnp(n, p=0.1, seed=42):
    return fnx.gnp_random_graph(n, p, seed)


def _build_nx_gnp(n, p=0.1, seed=42):
    return nx.gnp_random_graph(n, p, seed)


# Prebuilt graphs at various sizes for algorithm benchmarks
SIZES = [100, 500, 1000]


@pytest.fixture(params=SIZES, ids=[f"n={s}" for s in SIZES])
def size(request):
    return request.param


@pytest.fixture
def fnx_gnp(size):
    return _build_fnx_gnp(size, p=max(0.05, 3.0 / size), seed=42)


@pytest.fixture
def nx_gnp(size):
    return _build_nx_gnp(size, p=max(0.05, 3.0 / size), seed=42)


@pytest.fixture
def fnx_path(size):
    return _build_fnx_path(size)


@pytest.fixture
def nx_path(size):
    return _build_nx_path(size)


# ---------------------------------------------------------------------------
# Graph construction benchmarks
# ---------------------------------------------------------------------------

class TestGraphConstruction:
    """Measure time to construct graphs node-by-node and edge-by-edge."""

    @pytest.mark.parametrize("n", [100, 1000, 5000], ids=["n=100", "n=1000", "n=5000"])
    def test_fnx_add_edges(self, benchmark, n):
        def build():
            G = fnx.Graph()
            for i in range(n - 1):
                G.add_edge(str(i), str(i + 1))
            return G
        benchmark(build)

    @pytest.mark.parametrize("n", [100, 1000, 5000], ids=["n=100", "n=1000", "n=5000"])
    def test_nx_add_edges(self, benchmark, n):
        def build():
            G = nx.Graph()
            for i in range(n - 1):
                G.add_edge(str(i), str(i + 1))
            return G
        benchmark(build)


# ---------------------------------------------------------------------------
# Shortest path benchmarks
# ---------------------------------------------------------------------------

class TestShortestPath:
    """Benchmark shortest_path on various graph sizes."""

    def test_fnx_shortest_path(self, benchmark, fnx_path, size):
        benchmark(fnx.shortest_path, fnx_path, "0", str(size - 1))

    def test_nx_shortest_path(self, benchmark, nx_path, size):
        benchmark(nx.shortest_path, nx_path, "0", str(size - 1))


# ---------------------------------------------------------------------------
# Connected components benchmarks
# ---------------------------------------------------------------------------

class TestConnectedComponents:
    """Benchmark connected_components."""

    def test_fnx_connected_components(self, benchmark, fnx_gnp, size):
        benchmark(fnx.connected_components, fnx_gnp)

    def test_nx_connected_components(self, benchmark, nx_gnp, size):
        benchmark(nx.connected_components, nx_gnp)


# ---------------------------------------------------------------------------
# PageRank benchmarks
# ---------------------------------------------------------------------------

class TestPageRank:
    """Benchmark PageRank computation."""

    def test_fnx_pagerank(self, benchmark, fnx_gnp, size):
        benchmark(fnx.pagerank, fnx_gnp)

    def test_nx_pagerank(self, benchmark, nx_gnp, size):
        benchmark(nx.pagerank, nx_gnp)


# ---------------------------------------------------------------------------
# Betweenness centrality benchmarks
# ---------------------------------------------------------------------------

class TestBetweennessCentrality:
    """Benchmark betweenness centrality (O(VE) — sensitive to graph size)."""

    def test_fnx_betweenness(self, benchmark, fnx_gnp, size):
        benchmark(fnx.betweenness_centrality, fnx_gnp)

    def test_nx_betweenness(self, benchmark, nx_gnp, size):
        benchmark(nx.betweenness_centrality, nx_gnp)


# ---------------------------------------------------------------------------
# Clustering benchmarks
# ---------------------------------------------------------------------------

class TestClustering:
    """Benchmark clustering coefficient."""

    def test_fnx_clustering(self, benchmark, fnx_gnp, size):
        benchmark(fnx.clustering, fnx_gnp)

    def test_nx_clustering(self, benchmark, nx_gnp, size):
        benchmark(nx.clustering, nx_gnp)


# ---------------------------------------------------------------------------
# Is-connected benchmarks
# ---------------------------------------------------------------------------

class TestIsConnected:
    """Benchmark is_connected check."""

    def test_fnx_is_connected(self, benchmark, fnx_gnp, size):
        benchmark(fnx.is_connected, fnx_gnp)

    def test_nx_is_connected(self, benchmark, nx_gnp, size):
        benchmark(nx.is_connected, nx_gnp)


# ---------------------------------------------------------------------------
# Density benchmarks
# ---------------------------------------------------------------------------

class TestDensity:
    """Benchmark density calculation."""

    def test_fnx_density(self, benchmark, fnx_gnp, size):
        benchmark(fnx.density, fnx_gnp)

    def test_nx_density(self, benchmark, nx_gnp, size):
        benchmark(nx.density, nx_gnp)


# ---------------------------------------------------------------------------
# MST benchmarks
# ---------------------------------------------------------------------------

class TestMST:
    """Benchmark minimum spanning tree."""

    def test_fnx_mst(self, benchmark, fnx_gnp, size):
        if fnx.is_connected(fnx_gnp):
            benchmark(fnx.minimum_spanning_tree, fnx_gnp)
        else:
            pytest.skip("graph not connected")

    def test_nx_mst(self, benchmark, nx_gnp, size):
        if nx.is_connected(nx_gnp):
            benchmark(nx.minimum_spanning_tree, nx_gnp)
        else:
            pytest.skip("graph not connected")
