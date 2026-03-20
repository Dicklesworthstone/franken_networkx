"""Shared pytest fixtures and helpers for FrankenNetworkX conformance tests.

These tests compare FrankenNetworkX output against NetworkX oracle values
to verify algorithm correctness across the Python binding layer.
"""

import logging
import time
from functools import wraps

import pytest

log = logging.getLogger("fnx_conformance")


def _benchmark_mode_enabled(config: pytest.Config) -> bool:
    """Return true when pytest-benchmark execution was explicitly requested."""
    return bool(getattr(config.option, "benchmark_only", False))


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip benchmark-marked tests unless the caller opted into benchmark mode."""
    if _benchmark_mode_enabled(config):
        return

    skip_benchmark = pytest.mark.skip(
        reason="benchmark tests are opt-in; rerun with --benchmark-only"
    )
    for item in items:
        if "benchmark" in item.keywords:
            item.add_marker(skip_benchmark)

# ---------------------------------------------------------------------------
# Graph builder fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fnx():
    """Import and return the franken_networkx module."""
    import franken_networkx as _fnx
    return _fnx


@pytest.fixture
def nx():
    """Import and return the networkx module."""
    import networkx as _nx
    return _nx


@pytest.fixture
def path_graph(fnx, nx):
    """Path graph: a-b-c-d-e (5 nodes, 4 edges)."""
    G_fnx = fnx.Graph()
    G_nx = nx.Graph()
    edges = [("a", "b"), ("b", "c"), ("c", "d"), ("d", "e")]
    for u, v in edges:
        G_fnx.add_edge(u, v)
        G_nx.add_edge(u, v)
    return G_fnx, G_nx


@pytest.fixture
def cycle_graph(fnx, nx):
    """Cycle graph: a-b-c-d-e-a (5 nodes, 5 edges)."""
    G_fnx = fnx.Graph()
    G_nx = nx.Graph()
    nodes = ["a", "b", "c", "d", "e"]
    for i in range(len(nodes)):
        u, v = nodes[i], nodes[(i + 1) % len(nodes)]
        G_fnx.add_edge(u, v)
        G_nx.add_edge(u, v)
    return G_fnx, G_nx


@pytest.fixture
def complete_graph(fnx, nx):
    """Complete graph K5 (5 nodes, 10 edges)."""
    G_fnx = fnx.Graph()
    G_nx = nx.Graph()
    nodes = ["a", "b", "c", "d", "e"]
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            G_fnx.add_edge(nodes[i], nodes[j])
            G_nx.add_edge(nodes[i], nodes[j])
    return G_fnx, G_nx


@pytest.fixture
def star_graph(fnx, nx):
    """Star graph: center 'a' connected to b, c, d, e (5 nodes, 4 edges)."""
    G_fnx = fnx.Graph()
    G_nx = nx.Graph()
    for leaf in ["b", "c", "d", "e"]:
        G_fnx.add_edge("a", leaf)
        G_nx.add_edge("a", leaf)
    return G_fnx, G_nx


@pytest.fixture
def weighted_graph(fnx, nx):
    """Weighted graph: diamond with varying weights."""
    G_fnx = fnx.Graph()
    G_nx = nx.Graph()
    edges = [
        ("a", "b", 1.0), ("a", "c", 4.0),
        ("b", "c", 2.0), ("b", "d", 5.0),
        ("c", "d", 1.0),
    ]
    for u, v, w in edges:
        G_fnx.add_edge(u, v, weight=w)
        G_nx.add_edge(u, v, weight=w)
    return G_fnx, G_nx


@pytest.fixture
def disconnected_graph(fnx, nx):
    """Disconnected graph: {a-b-c} and {d-e}."""
    G_fnx = fnx.Graph()
    G_nx = nx.Graph()
    for u, v in [("a", "b"), ("b", "c"), ("d", "e")]:
        G_fnx.add_edge(u, v)
        G_nx.add_edge(u, v)
    return G_fnx, G_nx


@pytest.fixture
def triangle_graph(fnx, nx):
    """Triangle graph: a-b-c-a (3 nodes, 3 edges)."""
    G_fnx = fnx.Graph()
    G_nx = nx.Graph()
    for u, v in [("a", "b"), ("b", "c"), ("a", "c")]:
        G_fnx.add_edge(u, v)
        G_nx.add_edge(u, v)
    return G_fnx, G_nx


# ---------------------------------------------------------------------------
# Comparison helpers
# ---------------------------------------------------------------------------

def assert_dicts_close(fnx_dict, nx_dict, atol=1e-6, label=""):
    """Assert two dicts have the same keys and values within tolerance."""
    fnx_keys = set(str(k) for k in fnx_dict.keys())
    nx_keys = set(str(k) for k in nx_dict.keys())
    assert fnx_keys == nx_keys, f"{label}: key mismatch — fnx={fnx_keys}, nx={nx_keys}"
    for k in nx_dict:
        fnx_val = fnx_dict.get(k, fnx_dict.get(str(k)))
        nx_val = nx_dict[k]
        assert abs(fnx_val - nx_val) < atol, (
            f"{label}[{k}]: fnx={fnx_val}, nx={nx_val}, diff={abs(fnx_val - nx_val)}"
        )


def assert_sets_equal(fnx_set, nx_set, label=""):
    """Assert two sets/lists contain the same elements (order-independent)."""
    fnx_s = set(str(x) for x in fnx_set)
    nx_s = set(str(x) for x in nx_set)
    assert fnx_s == nx_s, f"{label}: fnx={fnx_s}, nx={nx_s}"
