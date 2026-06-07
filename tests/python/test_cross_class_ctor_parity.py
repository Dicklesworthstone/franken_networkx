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
