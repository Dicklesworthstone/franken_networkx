"""Byte-exact conformance guard for directed subgraph / edge_subgraph / reverse.

CrimsonRiver is folding the DiGraph/MultiDiGraph construction paths (subgraph,
edge_subgraph, reverse, absorb, to_undirected) to single-pass / lazy AttrMap
attr crossing. Those folds must preserve observable behaviour exactly; this locks
it vs networkx so the optimization lands without silent attr loss or aliasing:

  * subgraph(S): node set S, induced edges (both endpoints in S), node+edge attrs
    match networkx;
  * edge_subgraph(E): exactly edges E + incident nodes, attrs match networkx;
  * reverse(): every arc flipped, node/edge/graph attrs preserved, matches nx;
  * mutating the SOURCE after the operation does not change the result.

Complements test_to_undirected_conformance_guard.py + test_copy_family_*.

No mocks: real fnx vs real networkx.
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx

_TYPES = [(fnx.DiGraph, nx.DiGraph), (fnx.MultiDiGraph, nx.MultiDiGraph)]


def _build(fcls, ncls, seed):
    r = random.Random(seed)
    n = r.randint(5, 10)
    fg, ng = fcls(), ncls()
    for node in range(n):
        fg.add_node(node, tag=f"t{node}")
        ng.add_node(node, tag=f"t{node}")
    for u in range(n):
        for v in range(n):
            if u != v and r.random() < 0.3:
                w = r.randint(1, 9)
                fg.add_edge(u, v, weight=w)
                ng.add_edge(u, v, weight=w)
    fg.graph["meta"] = "m"
    ng.graph["meta"] = "m"
    return fg, ng, n, r


def _nattrs(g):
    return {n: dict(d) for n, d in g.nodes(data=True)}


def _eattrs(g):
    if g.is_multigraph():
        return sorted(((u, v), k, tuple(sorted(d.items())))
                      for u, v, k, d in g.edges(keys=True, data=True))
    return sorted(((u, v), tuple(sorted(d.items()))) for u, v, d in g.edges(data=True))


@pytest.mark.parametrize("fcls,ncls", _TYPES)
@pytest.mark.parametrize("seed", range(12))
def test_directed_subgraph_matches_networkx(fcls, ncls, seed):
    fg, ng, n, r = _build(fcls, ncls, seed)
    keep = sorted(r.sample(range(n), r.randint(2, n)))
    fs, nss = fg.subgraph(keep), ng.subgraph(keep)
    assert set(fs.nodes()) == set(nss.nodes())
    assert _nattrs(fs) == _nattrs(nss)
    assert _eattrs(fs) == _eattrs(nss)


@pytest.mark.parametrize("fcls,ncls", _TYPES)
@pytest.mark.parametrize("seed", range(12))
def test_directed_reverse_matches_networkx(fcls, ncls, seed):
    fg, ng, n, r = _build(fcls, ncls, seed)
    fr, nr = fg.reverse(), ng.reverse()
    assert _nattrs(fr) == _nattrs(nr)
    assert _eattrs(fr) == _eattrs(nr)
    assert dict(fr.graph) == dict(nr.graph)


@pytest.mark.parametrize("fcls,ncls", _TYPES)
@pytest.mark.parametrize("seed", range(12))
def test_directed_subgraph_independent_of_source(fcls, ncls, seed):
    fg, ng, n, r = _build(fcls, ncls, seed)
    keep = sorted(r.sample(range(n), r.randint(2, n)))
    fs = fg.subgraph(keep).copy()   # .copy() detaches the subgraph view
    before_n, before_e = _nattrs(fs), _eattrs(fs)
    for node in list(fg.nodes()):
        fg.nodes[node]["tag"] = "MUT"
        break
    fg.add_node("brand_new")
    assert _nattrs(fs) == before_n
    assert _eattrs(fs) == before_e
    assert "brand_new" not in set(fs.nodes())


def _view_chains(lib, g, keep, drop):
    """Views nested through a reverse view (br-r37-c1-7jhpr). A filtered view
    over a reverse view inherited the reverse view's methods, which read its
    _graph as the un-reversed graph: the subgraph reversed to the whole graph
    and its reverse listed the filtered-out nodes."""
    r = g.reverse(copy=False)
    rs = r.subgraph(keep)
    edges = list(r.edges(keys=True)) if g.is_multigraph() else list(r.edges)
    return {
        "R.sub": rs,
        "R.sub.R": rs.reverse(copy=False),
        "R.sub.R.sub": rs.reverse(copy=False).subgraph(keep[: max(2, len(keep) - 1)]),
        "R.edge_sub": r.edge_subgraph(edges[::2]),
        "R.restricted": lib.restricted_view(r, [drop], []),
    }


def _observe(view):
    return {
        "nodes": sorted(view),
        "edges": _eattrs(view),
        "rows": {u: sorted(nbrs) for u, nbrs in view.adj.items()},
        "in_degree": dict(view.in_degree(weight="weight")),
        "out_degree": dict(view.out_degree()),
        "nbunch": sorted(view.nbunch_iter(list(range(12)))),
        "reverse": _eattrs(view.reverse(copy=False)),
        "edge_data": [view.get_edge_data(u, v) is not None for u in range(12) for v in range(12)],
    }


@pytest.mark.parametrize("fcls,ncls", _TYPES)
@pytest.mark.parametrize("seed", range(12))
def test_views_nested_through_a_reverse_view_match_networkx(fcls, ncls, seed):
    fg, ng, n, r = _build(fcls, ncls, seed)
    keep = sorted(r.sample(range(n), r.randint(2, n - 1)))
    drop = next(node for node in range(n) if node not in keep)
    f_views = _view_chains(fnx, fg, keep, drop)
    n_views = _view_chains(nx, ng, keep, drop)
    for name in f_views:
        assert _observe(f_views[name]) == _observe(n_views[name]), name
        if 0 in n_views[name]:
            assert fnx.single_source_shortest_path_length(f_views[name], 0) == (
                nx.single_source_shortest_path_length(n_views[name], 0)
            ), name
            assert fnx.goldberg_radzik(f_views[name], 0) == nx.goldberg_radzik(
                n_views[name], 0
            ), name
