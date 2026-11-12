"""br-r37-c1-bt8m4: directed->undirected cross-class constructor parity vs nx.

Collapsing a directed source into an undirected target, nx's
from_dict_of_dicts walks adjacency cells with a `seen` reverse-pair skip:
the FIRST direction encountered wins (keeping all its parallel keys);
the reverse direction is skipped entirely — attrs never merge across
directions. fnx previously let the reverse direction overwrite
(last-wins) in MultiGraph(DiGraph), Graph(MultiDiGraph), and
MultiGraph(MultiDiGraph).
"""

import random

import networkx as nx
import pytest

import franken_networkx as fnx


def _canon(g):
    return (
        repr([(n, dict(a)) for n, a in g.nodes(data=True)]),
        repr(
            sorted(
                map(
                    repr,
                    g.edges(data=True, keys=True)
                    if g.is_multigraph()
                    else g.edges(data=True),
                )
            )
        ),
        repr(dict(g.graph)),
    )


@pytest.mark.parametrize(
    "src_cls,dst_cls,edges",
    [
        ("DiGraph", "MultiGraph", [("a", "b", {"w": 1}), ("b", "a", {"w": 2})]),
        ("DiGraph", "MultiGraph", [("b", "a", {"w": 2}), ("a", "b", {"w": 1})]),  # reverse first
        ("MultiDiGraph", "Graph", [("a", "b", {"w": 1}), ("b", "a", {"w": 2})]),
        ("MultiDiGraph", "MultiGraph", [("a", "b", {"w": 1}), ("b", "a", {"w": 2})]),
        # parallel keys in the kept direction survive; reverse still skipped
        (
            "MultiDiGraph",
            "MultiGraph",
            [("a", "b", {"w": 1}), ("a", "b", {"w": 3}), ("b", "a", {"w": 2})],
        ),
        (
            "MultiDiGraph",
            "Graph",
            [("a", "b", {"w": 1}), ("a", "b", {"w": 3}), ("b", "a", {"w": 2})],
        ),
        # parallel self-loops keep all keys
        ("MultiDiGraph", "MultiGraph", [("a", "a", {"w": 1}), ("a", "a", {"w": 2})]),
        ("DiGraph", "MultiGraph", [("a", "a", {"w": 1})]),
    ],
)
def test_collapse_shapes_match_nx(src_cls, dst_cls, edges):
    gn = getattr(nx, src_cls)()
    gf = getattr(fnx, src_cls)()
    gn.add_edges_from(edges)
    gf.add_edges_from(edges)
    assert _canon(getattr(fnx, dst_cls)(gf)) == _canon(getattr(nx, dst_cls)(gn))


def test_full_cross_class_matrix():
    classes = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]
    rnd = random.Random(20260605)
    for trial in range(3):
        edges = [
            (f"n{rnd.randrange(15)}", f"n{rnd.randrange(15)}", {"w": round(rnd.random(), 9)})
            for _ in range(30)
        ]
        for src_cls in classes:
            gn = getattr(nx, src_cls)()
            gf = getattr(fnx, src_cls)()
            gn.add_edges_from(edges)
            gf.add_edges_from(edges)
            for dst_cls in classes:
                assert _canon(getattr(fnx, dst_cls)(gf)) == _canon(
                    getattr(nx, dst_cls)(gn)
                ), f"{trial}:{src_cls}->{dst_cls}"


# br-r37-c1-bw6si / br-r37-c1-gelud. Everything below is ORDER-sensitive: node
# order, each adjacency row's order, edge order and each attribute dict's key
# order, because the store an attribute can live in sorts its keys.

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


def _exact(g):
    rows = {n: list(nbrs) for n, nbrs in g.adj.items()}
    if g.is_multigraph():
        edges = [(u, v, k, list(d.items())) for u, v, k, d in g.edges(keys=True, data=True)]
    else:
        edges = [(u, v, list(d.items())) for u, v, d in g.edges(data=True)]
    return (
        type(g).__name__,
        [(n, list(d.items())) for n, d in g.nodes(data=True)],
        rows,
        edges,
        list(g.graph.items()),
    )


def _store_only_nodes(lib, cls, edges):
    """One-key node dicts through the node batch - held only in the native store."""
    g = getattr(lib, cls)()
    g.add_nodes_from([(n, {"color": n % 3}) for n in range(12)])
    g.add_edges_from(edges)
    g.graph["name"] = "g"
    return g


RING = [(i, (i + 1) % 12) for i in range(12)] + [(0, 5), (7, 2)]
NODE_DATA_CALLS = {
    "Graph(G)": lambda m, g: m.Graph(g),
    "DiGraph(G)": lambda m, g: m.DiGraph(g),
    "MultiGraph(G)": lambda m, g: m.MultiGraph(g),
    "MultiDiGraph(G)": lambda m, g: m.MultiDiGraph(g),
    "copy": lambda m, g: g.copy(),
    "to_directed": lambda m, g: g.to_directed(),
    "to_undirected": lambda m, g: g.to_undirected(),
    "freeze copy": lambda m, g: m.freeze(g.copy()).copy(),
    "contracted_nodes": lambda m, g: m.contracted_nodes(g, 0, 1),
}


@pytest.mark.parametrize("call", list(NODE_DATA_CALLS))
@pytest.mark.parametrize("cls", CLASSES)
def test_store_only_node_attrs_survive_copies(cls, call):
    """br-r37-c1-bw6si: a node dict left in the store by the node batch came back
    {} from DiGraph(G), MultiGraph(G), G.to_directed() and the MultiGraph copy /
    to_directed / to_undirected kernels, which read only the Python mirror."""
    actual = NODE_DATA_CALLS[call](fnx, _store_only_nodes(fnx, cls, RING))
    expected = NODE_DATA_CALLS[call](nx, _store_only_nodes(nx, cls, RING))
    assert [(n, dict(d)) for n, d in actual.nodes(data=True)] == [
        (n, dict(d)) for n, d in expected.nodes(data=True)
    ]


ATTR_SHAPE_LABELS = [
    f"{label} / {built}"
    for label in (
        "reciprocal adds key",
        "reciprocal overwrites",
        "unsorted keys",
        "one key",
        "shared list",
        "self loop",
        "no attrs",
    )
    for built in ("batch", "per edge")
]


def _attr_shapes(lib, cls):
    shapes = {}
    for label, edges in {
        # a reciprocal pair whose second direction ADDS a key sorting before the
        # first's: networkx's merged dict keeps the first's keys first
        "reciprocal adds key": [(0, 1, {"w": 1}), (1, 0, {"a": 2}), (1, 2, {"w": 3})],
        "reciprocal overwrites": [(0, 1, {"w": 1, "a": 1}), (1, 0, {"w": 9}), (2, 0, {})],
        "unsorted keys": [(0, 1, {"weight": 2, "kind": "x"}), (1, 2, {"kind": "y", "weight": 1})],
        "one key": [(i, (i + 1) % 9, {"weight": i}) for i in range(9)] + [(3, 7, {"weight": 1.5})],
        "shared list": [(0, 1, {"tags": ["a"]}), (1, 0, {"n": 1}), (1, 2, {"tags": ["b"], "w": 2})],
        "self loop": [(0, 0, {"w": 1}), (0, 1, {"w": 2}), (1, 0, {"w": 3})],
        "no attrs": [(0, 1), (1, 0), (1, 2), (3, 3)],
    }.items():
        for built in ("batch", "per edge"):
            g = getattr(lib, cls)()
            g.add_node("iso", role="x")
            if built == "batch":
                g.add_edges_from(edges)
            else:
                for e in edges:
                    g.add_edge(*e[:2], **(e[2] if len(e) > 2 else {}))
            shapes[f"{label} / {built}"] = g
    return shapes


@pytest.mark.parametrize("label", ATTR_SHAPE_LABELS)
@pytest.mark.parametrize(
    "src_cls,dst_cls",
    [("DiGraph", "Graph"), ("Graph", "DiGraph"), ("DiGraph", "DiGraph"), ("Graph", "Graph")],
)
def test_cross_class_constructor_is_exact(src_cls, dst_cls, label):
    """br-r37-c1-gelud: Graph(DiGraph) and DiGraph(Graph) build natively, a dict
    only where the sorted store cannot rebuild it; order, merges, shared
    containers and independence must all be networkx's."""
    fsrc, nsrc = _attr_shapes(fnx, src_cls)[label], _attr_shapes(nx, src_cls)[label]
    f = getattr(fnx, dst_cls)(fsrc)
    n = getattr(nx, dst_cls)(nsrc)
    assert _exact(f) == _exact(n)
    # shallow, as networkx: a container value is the source's object ...
    for (u, v, fd), (_, _, nd) in zip(f.edges(data=True), n.edges(data=True)):
        if "tags" in nd and nsrc.has_edge(u, v) and "tags" in nsrc[u][v]:
            assert (fd["tags"] is fsrc[u][v]["tags"]) == (nd["tags"] is nsrc[u][v]["tags"])
    # ... but every dict is new: a write through the copy leaves the source
    # alone, and DiGraph(Graph)'s two directions are separate dicts
    for u, v, fd in list(f.edges(data=True)):
        fd["probe"] = 1
    for u, v, nd in list(n.edges(data=True)):
        nd["probe"] = 1
    assert _exact(fsrc) == _exact(nsrc)
    assert _exact(f) == _exact(n)


@pytest.mark.parametrize("src_cls,dst_cls,kernel", [
    ("DiGraph", "Graph", "graph_absorb_digraph"),
    ("Graph", "DiGraph", "digraph_absorb_graph_bidirected"),
])
def test_cross_class_constructor_takes_the_native_absorb(src_cls, dst_cls, kernel, monkeypatch):
    taken = []
    native = getattr(fnx._fnx, kernel)

    def counting(*args):
        answered = native(*args)
        taken.append(answered)
        return answered

    monkeypatch.setattr(fnx._fnx, kernel, counting)
    src = _attr_shapes(fnx, src_cls)["unsorted keys / batch"]
    getattr(fnx, dst_cls)(src)
    assert taken == [True]
