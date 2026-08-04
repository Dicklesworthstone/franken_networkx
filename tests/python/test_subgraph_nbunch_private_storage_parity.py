"""Parity lock for br-r37-c1-w4754 — nbunch filtering when NetworkX private storage
is assigned.

networkx's ``nbunch_iter`` is deliberately asymmetric: a SEQUENCE nbunch is filtered
against ``self._adj``, while the single-node form tests ``nbunch in self`` (``_node``).
Those two mappings hold the same keys on any ordinary graph, so the asymmetry is
invisible — until a caller assigns NetworkX private storage to one of them and they
disagree.

fnx filtered the sequence form against the graph itself, so an assigned ``_node`` key
with no adjacency row survived into the induced subgraph where networkx drops it:
``g.subgraph(["private"])`` returned ``['private']`` against networkx's ``[]``.

The negative case is ``test_mixed_private_node_and_adj_storage_keeps_its_nodes``: a fix
that simply returned an empty subgraph whenever private storage is present would pass
every other test here and fail that one, because with ``_adj`` assigned as well the
mapping's nodes DO have adjacency rows and must survive.

Every expectation below is taken from the live networkx oracle in the same test run,
never hard-coded, so the file cannot drift from networkx's actual behavior.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

CLASS_NAMES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


def _build(mod, name, *, assign_adj=False):
    """A graph with a native node plus assigned private node storage."""
    graph = getattr(mod, name)()
    graph.add_node("native")
    graph._node = {"p1": {}, "p2": {"tag": 1}}
    if assign_adj:
        graph._adj = {"p1": {"p2": {}}, "p2": {"p1": {}}}
        if name in ("DiGraph", "MultiDiGraph"):
            graph._succ = graph._adj
            graph._pred = {"p1": {"p2": {}}, "p2": {"p1": {}}}
    return graph


def _summary(graph, nbunch):
    sub = graph.subgraph(nbunch)
    return (
        sorted(str(node) for node in sub.nodes),
        "p1" in sub,
        "native" in sub,
        len(sub),
    )


@pytest.mark.parametrize("name", CLASS_NAMES)
@pytest.mark.parametrize(
    "nbunch",
    [
        pytest.param(["p1", "p2"], id="sequence-of-mapping-keys"),
        pytest.param(["native"], id="sequence-of-native-key"),
        pytest.param(["p1", "native", "absent"], id="sequence-mixed"),
        pytest.param([], id="sequence-empty"),
    ],
)
def test_sequence_nbunch_matches_networkx_under_private_node_storage(name, nbunch):
    """A sequence nbunch filters against the adjacency mapping, as networkx does."""
    expected = _summary(_build(nx, name), nbunch)
    actual = _summary(_build(fnx, name), nbunch)
    assert actual == expected, (
        f"{name}: subgraph({nbunch!r}) diverges from networkx — "
        f"fnx {actual} vs nx {expected}"
    )


@pytest.mark.parametrize("name", CLASS_NAMES)
@pytest.mark.parametrize(
    "nbunch",
    [
        pytest.param("p1", id="single-mapping-key"),
        pytest.param("native", id="single-native-key"),
    ],
)
def test_single_node_nbunch_keeps_networkx_asymmetry(name, nbunch):
    """The single-node form tests ``nbunch in self`` — ``_node``, not ``_adj``.

    networkx really does answer differently for ``subgraph("p1")`` and
    ``subgraph(["p1"])`` here, so a fix that routed BOTH forms through the adjacency
    mapping would be wrong in the other direction.
    """
    expected = _summary(_build(nx, name), nbunch)
    actual = _summary(_build(fnx, name), nbunch)
    assert actual == expected, (
        f"{name}: subgraph({nbunch!r}) diverges from networkx — "
        f"fnx {actual} vs nx {expected}"
    )


@pytest.mark.parametrize("name", CLASS_NAMES)
def test_mixed_private_node_and_adj_storage_keeps_its_nodes(name):
    """NEGATIVE CASE — an empty-subgraph shortcut would fail exactly here.

    With ``_adj`` assigned too, the mapping's nodes have adjacency rows, so networkx
    keeps them and so must fnx.
    """
    expected = _summary(_build(nx, name, assign_adj=True), ["p1", "p2"])
    actual = _summary(_build(fnx, name, assign_adj=True), ["p1", "p2"])
    assert actual == expected, (
        f"{name}: subgraph over mixed private node+adj storage diverges from "
        f"networkx — fnx {actual} vs nx {expected}"
    )
    # Guard the guard: the oracle really does keep these nodes, so this case is a
    # live negative and not a vacuous comparison of two empty subgraphs.
    assert expected[0] == ["p1", "p2"], f"{name}: oracle unexpectedly empty"


@pytest.mark.parametrize("name", CLASS_NAMES)
def test_ordinary_graphs_are_untouched_by_the_adjacency_filter(name):
    """No private storage means no behavior change — including the large-nbunch path.

    ``_subgraph_filter_from_nbunch`` builds ``set(container)`` once when the nbunch is
    at least a quarter of the graph, so both the per-node and the set-membership
    branches need covering.
    """
    gnx = getattr(nx, name)()
    gfx = getattr(fnx, name)()
    for graph in (gnx, gfx):
        graph.add_edges_from((str(i), str(i + 1)) for i in range(40))

    for nbunch in (
        [str(i) for i in range(40)],  # large -> set(container) branch
        ["3", "4", "5"],  # small -> per-node branch
        ["3", "missing"],
        [],
    ):
        expected = _summary(gnx, nbunch)
        actual = _summary(gfx, nbunch)
        assert actual == expected, (
            f"{name}: ordinary-graph subgraph({nbunch!r}) diverges — "
            f"fnx {actual} vs nx {expected}"
        )
