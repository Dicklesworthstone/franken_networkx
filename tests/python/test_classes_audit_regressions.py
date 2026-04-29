"""Regression tests for the fnx-classes three-pass audit fixes.

These pin error-contract divergences uncovered while sweeping
the public bulk-mutation API of Graph / DiGraph / MultiGraph /
MultiDiGraph against NetworkX.

- Pass 1 (read every public fn): fnx-classes is internally clean
  (zero unwrap/expect outside test code, clippy-clean), so the
  Pass-1 fixes live in the PyO3 bulk-mutation bindings — those
  ARE the public API surface that drop-in users see.
- Pass 2 (error paths): ``add_edges_from`` with a 3-tuple whose
  third element is a non-dict scalar; ``add_weighted_edges_from``
  with the wrong arity.
- Pass 3 (boundary / data preservation): ``GraphSnapshot``
  silently dropped per-node attributes — covered by a Rust unit
  test rather than a Python regression since the snapshot type
  isn't exposed to Python.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx


# ---------------------------------------------------------------------------
# Pass 1 / 2 — add_edges_from non-dict third element
# ---------------------------------------------------------------------------


class TestAddEdgesFromNonDictThird:
    """nx surfaces a TypeError via ``dict.update`` when the third
    element of an edge tuple isn't a dict (or iterable of pairs).
    fnx previously silently dropped non-dict thirds."""

    @pytest.mark.parametrize("graph_cls", [fnx.Graph, fnx.DiGraph])
    def test_nondict_third_raises_typeerror(self, graph_cls):
        g = graph_cls()
        with pytest.raises(TypeError):
            g.add_edges_from([(0, 1, 1.5)])

    @pytest.mark.parametrize("graph_cls", [fnx.Graph, fnx.DiGraph])
    def test_dict_third_still_works(self, graph_cls):
        g = graph_cls()
        g.add_edges_from([(0, 1, {"weight": 2.5})])
        assert g.get_edge_data(0, 1)["weight"] == 2.5

    @pytest.mark.parametrize("graph_cls", [fnx.Graph, fnx.DiGraph])
    def test_iterable_of_pairs_third_works(self, graph_cls):
        """nx accepts the third element as an iterable of (key, value)
        pairs (anything ``dict.update`` can consume)."""
        g = graph_cls()
        g.add_edges_from([(0, 1, [("weight", 2.5), ("color", "red")])])
        d = g.get_edge_data(0, 1)
        assert d["weight"] == 2.5 and d["color"] == "red"


# ---------------------------------------------------------------------------
# Pass 2 — add_weighted_edges_from arity error wording
# ---------------------------------------------------------------------------


class TestAddWeightedEdgesFromArity:
    """nx raises ``ValueError("not enough values to unpack (expected
    3, got N)")`` when a weighted-edge tuple has the wrong arity. fnx
    previously used a custom message that wouldn't match drop-in tests
    pinning nx's wording."""

    @pytest.mark.parametrize("graph_cls", [fnx.Graph, fnx.DiGraph,
                                            fnx.MultiGraph, fnx.MultiDiGraph])
    def test_two_tuple_arity_message(self, graph_cls):
        g = graph_cls()
        with pytest.raises(
            ValueError,
            match=r"not enough values to unpack \(expected 3, got 2\)",
        ):
            g.add_weighted_edges_from([(0, 1)])

    @pytest.mark.parametrize("graph_cls", [fnx.Graph, fnx.DiGraph])
    def test_one_tuple_arity_message(self, graph_cls):
        g = graph_cls()
        with pytest.raises(
            ValueError,
            match=r"not enough values to unpack \(expected 3, got 1\)",
        ):
            g.add_weighted_edges_from([(0,)])

    @pytest.mark.parametrize("graph_cls", [fnx.Graph, fnx.DiGraph])
    def test_valid_tuple_still_works(self, graph_cls):
        g = graph_cls()
        g.add_weighted_edges_from([(0, 1, 2.5)])
        assert g.get_edge_data(0, 1)["weight"] == 2.5

    @pytest.mark.parametrize("graph_cls", [fnx.Graph, fnx.DiGraph])
    def test_message_matches_networkx(self, graph_cls):
        """Exercise both libraries' add_weighted_edges_from with the
        same bad input and assert their ValueError messages agree."""
        nx_cls = {
            fnx.Graph: nx.Graph,
            fnx.DiGraph: nx.DiGraph,
        }[graph_cls]
        fg = graph_cls()
        ng = nx_cls()
        try:
            ng.add_weighted_edges_from([(0, 1)])
            pytest.fail("nx unexpectedly accepted the bad tuple")
        except ValueError as exc:
            nx_msg = str(exc)
        try:
            fg.add_weighted_edges_from([(0, 1)])
            pytest.fail("fnx unexpectedly accepted the bad tuple")
        except ValueError as exc:
            fnx_msg = str(exc)
        assert fnx_msg == nx_msg, f"fnx={fnx_msg!r} nx={nx_msg!r}"
