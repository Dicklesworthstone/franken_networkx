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
    assert actual.getvalue() == expected
