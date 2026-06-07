"""Conversion-family copy-depth + order contracts vs networkx.

br-r37-c1-convcontract: copy() / to_directed() / to_undirected() share subtle,
easy-to-break contracts that the native fast-path kernels must honor exactly:

  * copy() is SHALLOW — nested attr containers are SHARED with the original
    (nx: "if an attribute is a container, that container is shared").
  * to_directed() / to_undirected() are DEEP — nested attr containers are
    INDEPENDENT copies.
  * All three preserve node + edge insertion order and edge endpoint orientation.
  * Mutating the result's graph structure never touches the original.

These are exercised across all four graph classes against networkx. This locks
the contracts while the native copy/to_directed/to_undirected kernels are being
optimized (a shallow/deep mix-up or order scramble is otherwise silent).
"""

import networkx as nx
import pytest

import franken_networkx as fnx

_CLS = {
    "Graph": (nx.Graph, fnx.Graph),
    "DiGraph": (nx.DiGraph, fnx.DiGraph),
    "MultiGraph": (nx.MultiGraph, fnx.MultiGraph),
    "MultiDiGraph": (nx.MultiDiGraph, fnx.MultiDiGraph),
}


def _populate(G):
    G.add_nodes_from(range(6))
    for u, v in [(0, 1), (1, 2), (2, 0), (3, 4), (1, 3), (4, 4)]:
        G.add_edge(u, v, weight=u + v, tags=[u, v])
    for n in (0, 2, 4):
        G.nodes[n]["meta"] = {"id": n}
    G.graph["info"] = ["g"]
    return G


def _edge_sig(G):
    if G.is_multigraph():
        return [
            (u, v, k, w, tuple(t))
            for u, v, k, w, t in (
                (u, v, k, d.get("weight"), d.get("tags", ()))
                for u, v, k, d in G.edges(keys=True, data=True)
            )
        ]
    return [
        (u, v, d.get("weight"), tuple(d.get("tags", ())))
        for u, v, d in G.edges(data=True)
    ]


def _full_sig(G):
    return (list(G.nodes()), _edge_sig(G), sorted(G.graph.items()))


@pytest.mark.parametrize("cls_name", list(_CLS))
def test_copy_is_shallow_and_ordered_like_networkx(cls_name):
    ncls, fcls = _CLS[cls_name]
    Gn, Gf = _populate(ncls()), _populate(fcls())
    Cn, Cf = Gn.copy(), Gf.copy()
    # Order + values match networkx exactly.
    assert _full_sig(Cf) == _full_sig(Cn)
    # SHALLOW: nested edge/node containers are SHARED with the original (nx contract).
    u, v = next(iter(Gf.edges()))[:2]
    tags_f = (Cf[u][v][0]["tags"] if Gf.is_multigraph() else Cf[u][v]["tags"])
    tags_n = (Cn[u][v][0]["tags"] if Gn.is_multigraph() else Cn[u][v]["tags"])
    src_f = (Gf[u][v][0]["tags"] if Gf.is_multigraph() else Gf[u][v]["tags"])
    src_n = (Gn[u][v][0]["tags"] if Gn.is_multigraph() else Gn[u][v]["tags"])
    assert (tags_f is src_f) == (tags_n is src_n), "copy shallow-share parity broke"
    # Structural independence: adding a node to the copy must not touch the original.
    Cf.add_node("ZZ")
    assert "ZZ" not in Gf


@pytest.mark.parametrize("cls_name", list(_CLS))
def test_to_directed_is_deep_and_ordered_like_networkx(cls_name):
    ncls, fcls = _CLS[cls_name]
    Gn, Gf = _populate(ncls()), _populate(fcls())
    Dn, Df = Gn.to_directed(), Gf.to_directed()
    assert Df.is_directed()
    assert _full_sig(Df) == _full_sig(Dn)
    # DEEP: mutating a nested container in the result must NOT touch the original.
    u, v = next(iter(Gf.edges()))[:2]
    (Df[u][v][0] if Gf.is_multigraph() else Df[u][v])["tags"].append("X")
    src = (Gf[u][v][0] if Gf.is_multigraph() else Gf[u][v])["tags"]
    assert "X" not in src, "to_directed must deep-copy edge attrs"


@pytest.mark.parametrize("cls_name", list(_CLS))
def test_to_undirected_is_deep_and_ordered_like_networkx(cls_name):
    ncls, fcls = _CLS[cls_name]
    Gn, Gf = _populate(ncls()), _populate(fcls())
    Un, Uf = Gn.to_undirected(), Gf.to_undirected()
    assert not Uf.is_directed()
    assert _full_sig(Uf) == _full_sig(Un)
    # DEEP: result's nested node container is independent of the original.
    Uf.nodes[0]["meta"]["id"] = 999
    assert Gf.nodes[0]["meta"]["id"] == 0, "to_undirected must deep-copy node attrs"
