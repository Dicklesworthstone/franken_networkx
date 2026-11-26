"""Golden-output coverage for ``franken_networkx.describe``."""

from __future__ import annotations

import io
from contextlib import redirect_stdout
from pathlib import Path

import franken_networkx as fnx


GOLDEN_DIR = Path(__file__).with_name("goldens")


def test_describe_social_graph_matches_golden_output():
    graph = fnx.Graph(name="Golden Social")
    graph.add_edges_from(
        [
            ("alice", "bob"),
            ("bob", "carol"),
            ("carol", "alice"),
        ]
    )
    graph.add_node("dave")

    actual = io.StringIO()
    with redirect_stdout(actual):
        fnx.describe(graph)

    expected = (GOLDEN_DIR / "describe_social_graph.txt").read_text(
        encoding="utf-8"
    )
    if fnx._networkx_release() >= (3, 7):
        # The golden is NetworkX 3.6's format; 3.7 appends the density.
        expected += "Density                        : 0.5\n"
    assert actual.getvalue() == expected


def _describe_text(graph):
    actual = io.StringIO()
    with redirect_stdout(actual):
        assert fnx.describe(graph) is None
    return actual.getvalue()


_PATH3_BEFORE_3_7 = (
    "Number of nodes                : 3\n"
    "Number of edges                : 2\n"
    "Directed                       : False\n"
    "Multigraph                     : False\n"
    "Tree                           : True\n"
    "Bipartite                      : True\n"
    "Average degree (min, max)      : 1.33 (1, 2)\n"
    "Number of connected components : 1\n"
)
_DIRECTED_BEFORE_3_7 = (
    "Number of nodes                         : 3\n"
    "Number of edges                         : 3\n"
    "Directed                                : True\n"
    "Multigraph                              : False\n"
    "Tree                                    : False\n"
    "Bipartite                               : False\n"
    "Average degree (min, max)               : 2.00 (2, 2)\n"
    "Number of strongly connected components : 1\n"
    "Number of weakly connected components   : 1\n"
)
_SINGLE_BEFORE_3_7 = (
    "Number of nodes                : 1\n"
    "Number of edges                : 0\n"
    "Directed                       : False\n"
    "Multigraph                     : False\n"
    "Tree                           : True\n"
    "Bipartite                      : True\n"
    "Average degree (min, max)      : 0.00 (0, 0)\n"
    "Number of connected components : 1\n"
)


def test_describe_density_line_follows_the_networkx_release(monkeypatch):
    """NetworkX 3.7 added a ``Density`` row after the component counts;
    describe prints the installed release's format."""
    path = fnx.path_graph(3)
    cycle = fnx.DiGraph([(0, 1), (1, 2), (2, 0)])
    single = fnx.empty_graph(1)
    monkeypatch.setattr(fnx, "_networkx_release", lambda: (3, 6))
    assert _describe_text(path) == _PATH3_BEFORE_3_7
    assert _describe_text(cycle) == _DIRECTED_BEFORE_3_7
    assert _describe_text(single) == _SINGLE_BEFORE_3_7
    monkeypatch.setattr(fnx, "_networkx_release", lambda: (3, 7))
    assert _describe_text(path) == (
        _PATH3_BEFORE_3_7 + "Density                        : 0.6666666666666666\n"
    )
    assert _describe_text(cycle) == (
        _DIRECTED_BEFORE_3_7 + "Density                                 : 0.5\n"
    )
    assert _describe_text(single) == (
        _SINGLE_BEFORE_3_7 + "Density                        : 0\n"
    )
