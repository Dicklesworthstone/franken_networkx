"""Conformance guard for the same-type / lift constructor-absorb folds.

cls(other_graph) — building a graph from another graph instance — is the "absorb"
path. cc folded MultiGraph(MultiGraph) and MultiGraph(Graph) to single-pass
with_mirror; CrimsonRiver folds the DiGraph/MultiDiGraph constructors ("new")
toward fully-lazy. Existing tests cover dict-of-list / numpy / from-nx inputs but
NOT fnx-graph absorb, so this locks it vs networkx:

  * same-type absorb (Graph(Graph), DiGraph(DiGraph), MultiGraph(MultiGraph),
    MultiDiGraph(MultiDiGraph)) reproduces nodes/edges/attrs/graph-attrs exactly;
  * simple->multi LIFT (MultiGraph(Graph), MultiDiGraph(DiGraph)) lifts edges to
    key 0 and matches nx;
  * the absorb result is independent of the source (mutating source after).

No mocks: real fnx vs real networkx.
"""

from __future__ import annotations

import random

import pytest
import networkx as nx
import franken_networkx as fnx

# (fnx_target, nx_target, fnx_source, nx_source)
_SAME = [
    (fnx.Graph, nx.Graph, fnx.Graph, nx.Graph),
    (fnx.DiGraph, nx.DiGraph, fnx.DiGraph, nx.DiGraph),
    (fnx.MultiGraph, nx.MultiGraph, fnx.MultiGraph, nx.MultiGraph),
    (fnx.MultiDiGraph, nx.MultiDiGraph, fnx.MultiDiGraph, nx.MultiDiGraph),
]
_LIFT = [
    (fnx.MultiGraph, nx.MultiGraph, fnx.Graph, nx.Graph),
    (fnx.MultiDiGraph, nx.MultiDiGraph, fnx.DiGraph, nx.DiGraph),
]


def _fill(fg, ng, seed):
    r = random.Random(seed)
    n = r.randint(4, 9)
    for node in range(n):
        fg.add_node(node, tag=f"t{node}")
        ng.add_node(node, tag=f"t{node}")
    directed = fg.is_directed()
    for u in range(n):
        for v in range(n):
            if (u < v or (directed and u != v)) and r.random() < 0.4:
                w = r.randint(1, 9)
                fg.add_edge(u, v, weight=w)
                ng.add_edge(u, v, weight=w)
    fg.graph["meta"] = "m"
    ng.graph["meta"] = "m"


def _nattrs(g):
    return {n: dict(d) for n, d in g.nodes(data=True)}


def _eattrs(g):
    if g.is_multigraph():
        return sorted(((u, v), tuple(sorted(d.items())))
                      for u, v, k, d in g.edges(keys=True, data=True))
    return sorted(((u, v), tuple(sorted(d.items()))) for u, v, d in g.edges(data=True))


@pytest.mark.parametrize("ft,nt,fs,ns", _SAME + _LIFT)
@pytest.mark.parametrize("seed", range(12))
def test_absorb_matches_networkx(ft, nt, fs, ns, seed):
    fsrc, nsrc = fs(), ns()
    _fill(fsrc, nsrc, seed)
    fres, nres = ft(fsrc), nt(nsrc)
    assert sorted(fres.nodes()) == sorted(nres.nodes())
    assert _nattrs(fres) == _nattrs(nres)
    assert _eattrs(fres) == _eattrs(nres)
    assert dict(fres.graph) == dict(nres.graph)


@pytest.mark.parametrize("ft,nt,fs,ns", _SAME)
@pytest.mark.parametrize("seed", range(8))
def test_absorb_independent_of_source(ft, nt, fs, ns, seed):
    fsrc, nsrc = fs(), ns()
    _fill(fsrc, nsrc, seed)
    fres = ft(fsrc)
    before_n, before_e = _nattrs(fres), _eattrs(fres)
    for node in list(fsrc.nodes()):
        fsrc.nodes[node]["tag"] = "MUT"
        break
    fsrc.add_node("brand_new")
    assert _nattrs(fres) == before_n
    assert _eattrs(fres) == before_e
    assert "brand_new" not in set(fres.nodes())
