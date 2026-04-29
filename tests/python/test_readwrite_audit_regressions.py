"""Regression tests for the fnx-readwrite three-pass audit fixes.

These tests pin parser / writer error contracts to the wording
NetworkX uses, so future drift between the in-house Rust path and
the upstream nx behavior surfaces as a test failure rather than as
a silent divergence.

- Pass 1 (clippy ``manual_filter`` cleanups) is style-only — no
  behavioral test needed.
- Pass 2 (GML structural validation): duplicate node id, unbalanced
  brackets, stray ']' tokens.
- Pass 3 (boundary checks): create_using type validation, GraphML
  writer rejection of unsupported value types.
"""

from __future__ import annotations

import io

import networkx as nx
import pytest

import franken_networkx as fnx


# ---------------------------------------------------------------------------
# Pass 2 — GML structural-error parity
# ---------------------------------------------------------------------------


class TestGmlStructuralErrorParity:
    """The Python ``parse_gml`` runs the Rust reader in strict mode so
    structural errors surface as ``NetworkXError`` matching nx."""

    def test_duplicate_node_id_raises_networkx_error_matching_nx(self):
        gml = (
            'graph [ node [ id 0 label "a" ]'
            ' node [ id 0 label "a2" ] ]'
        )
        with pytest.raises(fnx.NetworkXError, match=r"node id 0 is duplicated"):
            fnx.parse_gml(gml)
        # Mirror: nx itself raises the same base type with the same wording.
        with pytest.raises(nx.NetworkXError, match=r"node id 0 is duplicated"):
            nx.parse_gml(gml)

    def test_unbalanced_graph_block_raises_networkx_error(self):
        with pytest.raises(fnx.NetworkXError):
            fnx.parse_gml("graph [ node [ id 0 ")

    def test_extra_closing_bracket_raises_networkx_error(self):
        with pytest.raises(fnx.NetworkXError):
            fnx.parse_gml("graph [ ] ]")

    def test_stray_closing_bracket_in_prologue_raises(self):
        with pytest.raises(fnx.NetworkXError):
            fnx.parse_gml("] graph [ ]")

    def test_empty_gml_raises_networkx_error_matching_nx(self):
        with pytest.raises(fnx.NetworkXError, match=r"input contains no graph"):
            fnx.parse_gml("")
        with pytest.raises(nx.NetworkXError, match=r"input contains no graph"):
            nx.parse_gml("")

    def test_valid_gml_round_trip_still_works(self):
        text = (
            'graph [ node [ id 0 label "a" ]'
            ' node [ id 1 label "b" ]'
            ' edge [ source 0 target 1 ] ]'
        )
        g = fnx.parse_gml(text)
        assert g.number_of_nodes() == 2
        assert g.number_of_edges() == 1


# ---------------------------------------------------------------------------
# Pass 3 — create_using validation
# ---------------------------------------------------------------------------


class TestCreateUsingTypeValidation:
    """parse_edgelist / parse_adjlist must raise ``TypeError`` with nx's
    wording when ``create_using`` is neither a Graph type nor instance.
    Previously fnx leaked an internal ``AttributeError: 'int' object
    has no attribute 'clear'`` for invalid arguments.
    """

    @pytest.mark.parametrize(
        "bad",
        [42, "string", 3.14, ["list"], {"dict": True}],
    )
    def test_parse_edgelist_invalid_create_using_raises(self, bad):
        with pytest.raises(
            TypeError,
            match=r"create_using is not a valid NetworkX graph type or instance",
        ):
            fnx.parse_edgelist(["0 1"], create_using=bad)

    @pytest.mark.parametrize(
        "bad",
        [42, 3.14],
    )
    def test_parse_adjlist_invalid_create_using_raises(self, bad):
        with pytest.raises(
            TypeError,
            match=r"create_using is not a valid NetworkX graph type or instance",
        ):
            fnx.parse_adjlist(["0 1"], create_using=bad)

    def test_parse_edgelist_valid_create_using_still_works(self):
        g = fnx.parse_edgelist(["0 1", "2 3"], create_using=fnx.DiGraph)
        assert g.is_directed()
        assert g.number_of_edges() == 2


# ---------------------------------------------------------------------------
# Pass 3 — GraphML writer attribute-type validation
# ---------------------------------------------------------------------------


class TestGraphmlWriterTypeValidation:
    """nx raises ``NetworkXError("GraphML writer does not support
    <class 'X'> as data values.")`` when an attribute value's type
    can't be encoded in GraphML. fnx silently coerced None / set /
    tuple / list to ``str(value)``, diverging from nx parity."""

    @pytest.mark.parametrize(
        "value,kind_pattern",
        [
            (b"bytes", r"bytes"),
            (None, r"NoneType"),
            ({"a", "b"}, r"set"),
            ((1.0, 2.0), r"tuple"),
            (["a", "b"], r"list"),
        ],
    )
    def test_unsupported_edge_attr_type_raises(self, value, kind_pattern):
        g = fnx.Graph()
        g.add_edge(0, 1, x=value)
        buf = io.BytesIO()
        with pytest.raises(
            fnx.NetworkXError,
            match=r"GraphML writer does not support .*" + kind_pattern,
        ):
            fnx.write_graphml(g, buf)

    @pytest.mark.parametrize(
        "value,kind_pattern",
        [
            (b"bytes", r"bytes"),
            (None, r"NoneType"),
            ({"a"}, r"set"),
        ],
    )
    def test_unsupported_node_attr_type_raises(self, value, kind_pattern):
        g = fnx.Graph()
        g.add_node(0, payload=value)
        buf = io.BytesIO()
        with pytest.raises(
            fnx.NetworkXError,
            match=r"GraphML writer does not support .*" + kind_pattern,
        ):
            fnx.write_graphml(g, buf)

    def test_unsupported_graph_attr_type_raises(self):
        g = fnx.Graph()
        g.graph["payload"] = b"bytes"
        buf = io.BytesIO()
        with pytest.raises(
            fnx.NetworkXError,
            match=r"GraphML writer does not support .*bytes",
        ):
            fnx.write_graphml(g, buf)

    def test_supported_types_pass_through(self):
        g = fnx.Graph()
        g.add_edge(0, 1, w=1.5, label="x", flag=True, count=42)
        g.add_node(2, name="payload")
        buf = io.BytesIO()
        fnx.write_graphml(g, buf)
        # Round-trip restores the same number of edges/nodes
        text = buf.getvalue().decode("utf-8")
        round_trip = fnx.parse_graphml(text)
        assert round_trip.number_of_nodes() == 3
        assert round_trip.number_of_edges() == 1
