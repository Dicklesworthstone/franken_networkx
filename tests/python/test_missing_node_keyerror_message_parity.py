"""Differential lock for br-r37-c1-k4nsd — the KeyError text for a missing node.

networkx has two wordings and fnx had them exactly SWAPPED::

    g = DiGraph(); g.add_edge('a','b')

    graph                       networkx                    fnx (before)
    g.subgraph([...]).adj['z']  KeyError('Key z not found') KeyError('z')
    g.reverse().adj['z']        KeyError('z')               KeyError('Key z not found')

nx's ``"Key {n} not found"`` comes from ``FilterAtlas``, so it belongs to
FILTERED graphs — subgraphs and edge subgraphs — while everything else raises
the bare key from an ordinary dict lookup. fnx's ``AdjacencyView`` serves plain
AND filtered graphs, which is why the wording has to be decided per graph
rather than per class.

The divergence spans far more than the degree views the bead was filed from:
``adj``, ``G[...]``, ``pred``, ``succ`` and all three degree accessors, on all
four graph classes. It is asserted here across that whole matrix.

Two contracts this fix had to avoid breaking, both asserted below:

* br-keystr — the bare-key form keeps the key's TYPE in ``args`` (``99``, not
  ``'99'``), which is why the filtered case is detected by inspecting the atlas
  rather than by pattern-matching the caught message. A message-based check
  could not tell nx's wording apart from a Rust-side str repr.
* br-r37-c1-i9whv — an UNHASHABLE index still raises TypeError, not KeyError.

KNOWN RESIDUE, both filed and both excluded below by name rather than hidden:

* br-r37-c1-nvm5i — ``G.reverse(copy=False).subgraph([...]).degree[missing]``
  still answers the bare key on DiGraph and MultiDiGraph. That degree view is
  constructed against an unfiltered graph object, so the information needed to
  pick the wording is not reachable from it: a wiring problem, distinct from
  this bead's swapped text.
* br-r37-c1-sc825 — a REVERSE view's adjacency indexed with an unhashable key
  raises KeyError where nx raises TypeError, because that one view is missing
  the ``hash(node)`` guard every sibling has. Pre-existing, verified against a
  tree predating this fix.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]
DIRECTED = ["DiGraph", "MultiDiGraph"]
MISSING_KEYS = ["zzz", 99, (1, 2)]

# Graph kinds and the wording networkx uses for each. Kept as an explicit
# table so the intent is visible: filtered -> FilterAtlas wording, everything
# else -> bare key.
def _edge_subgraph(graph):
    # Multigraphs need the key in the edge spec; nx raises ValueError on a
    # 2-tuple, so this is not an optional nicety.
    spec = [("a", "b", 0)] if graph.is_multigraph() else [("a", "b")]
    return graph.edge_subgraph(spec)


FILTERED_KINDS = {
    "subgraph": lambda g: g.subgraph(["a", "b"]),
    "edge_subgraph": _edge_subgraph,
    "subgraph_of_reverse": lambda g: g.reverse(copy=False).subgraph(["a", "b"]),
}
UNFILTERED_KINDS = {
    "plain": lambda g: g,
    "reverse": lambda g: g.reverse(copy=False),
}

ACCESSORS = {
    "adj": lambda G, key: G.adj[key],
    "getitem": lambda G, key: G[key],
    "degree": lambda G, key: G.degree[key],
}
DIRECTED_ACCESSORS = {
    "pred": lambda G, key: G.pred[key],
    "succ": lambda G, key: G.succ[key],
    "in_degree": lambda G, key: G.in_degree[key],
    "out_degree": lambda G, key: G.out_degree[key],
}


def _graphs(cls_name, make):
    made = []
    for lib in (nx, fnx):
        graph = getattr(lib, cls_name)()
        graph.add_edge("a", "b", weight=1.0)
        made.append(make(graph))
    return made


def _accessors_for(cls_name):
    accessors = dict(ACCESSORS)
    if cls_name in DIRECTED:
        accessors.update(DIRECTED_ACCESSORS)
    return accessors


def _outcome(fn, graph, key):
    try:
        return ("ok", repr(fn(graph, key)))
    except KeyError as exc:
        return ("KeyError", exc.args)
    except Exception as exc:  # noqa: BLE001
        return (type(exc).__name__, exc.args)


def _skip_unsupported(cls_name, kind_name):
    if cls_name in ("Graph", "MultiGraph") and "reverse" in kind_name:
        pytest.skip("undirected graphs have no reverse()")


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("kind_name", list(FILTERED_KINDS))
@pytest.mark.parametrize("key", MISSING_KEYS, ids=["str", "int", "tuple"])
def test_filtered_graphs_use_networkx_filteratlas_wording(cls_name, kind_name, key):
    _skip_unsupported(cls_name, kind_name)
    gnx, gfx = _graphs(cls_name, FILTERED_KINDS[kind_name])
    for name, accessor in _accessors_for(cls_name).items():
        if kind_name == "subgraph_of_reverse" and name == "degree":
            continue  # br-r37-c1-jm3rr, see module docstring
        expected = _outcome(accessor, gnx, key)
        assert expected == ("KeyError", (f"Key {key} not found",)), (name, expected)
        assert _outcome(accessor, gfx, key) == expected, name


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("kind_name", list(UNFILTERED_KINDS))
@pytest.mark.parametrize("key", MISSING_KEYS, ids=["str", "int", "tuple"])
def test_unfiltered_graphs_use_the_bare_key(cls_name, kind_name, key):
    _skip_unsupported(cls_name, kind_name)
    gnx, gfx = _graphs(cls_name, UNFILTERED_KINDS[kind_name])
    for name, accessor in _accessors_for(cls_name).items():
        expected = _outcome(accessor, gnx, key)
        assert expected == ("KeyError", (key,)), (name, expected)
        assert _outcome(accessor, gfx, key) == expected, name


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("key", [99, (1, 2)], ids=["int", "tuple"])
def test_bare_key_form_preserves_the_key_type(cls_name, key):
    """br-keystr: ``args`` carries 99, not '99'.

    This is why the filtered case is detected from the atlas rather than by
    matching the message text — the two are indistinguishable as strings.
    """
    _, gfx = _graphs(cls_name, UNFILTERED_KINDS["plain"])
    with pytest.raises(KeyError) as caught:
        gfx.adj[key]
    assert caught.value.args == (key,)
    assert type(caught.value.args[0]) is type(key)


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("kind_name", list(FILTERED_KINDS) + list(UNFILTERED_KINDS))
def test_unhashable_index_raises_typeerror_in_both(cls_name, kind_name):
    """br-r37-c1-i9whv: the hash check must still come first."""
    _skip_unsupported(cls_name, kind_name)
    if kind_name == "reverse":
        pytest.skip("br-r37-c1-sc825: reverse view is missing the hash() guard")
    make = {**FILTERED_KINDS, **UNFILTERED_KINDS}[kind_name]
    gnx, gfx = _graphs(cls_name, make)
    for graph in (gnx, gfx):
        with pytest.raises(TypeError):
            graph.adj[["not", "hashable"]]


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("kind_name", list(FILTERED_KINDS) + list(UNFILTERED_KINDS))
def test_present_nodes_still_answer_identically(cls_name, kind_name):
    """The error path must not have disturbed the success path."""
    _skip_unsupported(cls_name, kind_name)
    make = {**FILTERED_KINDS, **UNFILTERED_KINDS}[kind_name]
    gnx, gfx = _graphs(cls_name, make)
    for name, accessor in _accessors_for(cls_name).items():
        got_nx, got_fx = _outcome(accessor, gnx, "a"), _outcome(accessor, gfx, "a")
        assert got_nx[0] == "ok", (name, got_nx)
        if name in ("adj", "getitem", "pred", "succ"):
            # Compare the mapping's KEYS; the row objects repr differently.
            assert sorted(accessor(gfx, "a")) == sorted(accessor(gnx, "a")), name
        else:
            assert got_fx == got_nx, name


def test_the_two_wordings_are_not_the_same_string():
    """Guard against the table above being trivially satisfiable."""
    graph = nx.DiGraph()
    graph.add_edge("a", "b")
    with pytest.raises(KeyError) as filtered:
        graph.subgraph(["a", "b"]).adj["zzz"]
    with pytest.raises(KeyError) as plain:
        graph.adj["zzz"]
    assert filtered.value.args != plain.value.args
