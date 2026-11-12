"""Conversion kernels: reciprocal/parallel/self-loop merge parity.

br-r37-c1-convkey. ``to_undirected``/``to_directed``/``copy``/``reverse`` on the
multigraph classes have to decide, per arc, which undirected edge KEY an arc
merges onto - u->v and v->u collapse to one undirected pair, and parallel arcs
must keep distinct keys. The kernel tracks that with a per-pair bucket, and this
commit changed how that bucket is KEYED (owned ``(String, String)`` node names ->
node POSITIONS) and how the attribute mirror is found (two canonical rebuilds per
arc -> a handle carried in the bucket).

Neither change is supposed to alter a single output. That is exactly why it needs
a test that can SEE a merge go wrong: a fixture of one plain edge passes under
any keying scheme.

WHAT EACH SHAPE CATCHES:

  reciprocal  a->b and b->a. These MUST merge onto one undirected pair, and
              their attrs must merge onto one dict. If the bucket key stopped
              being orientation-insensitive, this splits into two edges.
  parallel    two a->b arcs. These must NOT merge; they take distinct keys. If
              the mirror handle were keyed by pair alone rather than
              (pair, key), the second arc would overwrite the first's attrs.
  selfloop    a->a, where source and target sort equal and the "lo/hi" ordering
              is degenerate.
  mixed       all of the above at once plus an attributed isolated node, which
              is where an ordering-sensitive bug shows up as a wrong KEY rather
              than a wrong edge count.
  noattr      arcs with no attributes at all, which take the branch that skips
              the mirror entirely - the path where a missing insert is invisible
              in the edge list and only shows up in the attr dicts.

The comparison is against networkx and covers nodes, node attrs, edges, keys and
edge attrs, because a merge bug can preserve the edge set exactly while putting
the attributes on the wrong key.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]
METHODS = ["to_undirected", "to_directed", "copy", "reverse"]


def _shapes():
    return {
        "reciprocal": lambda g: (g.add_edge("a", "b", w=1), g.add_edge("b", "a", w=2)),
        "parallel": lambda g: (g.add_edge("a", "b", w=1), g.add_edge("a", "b", w=3)),
        "selfloop": lambda g: (g.add_edge("a", "a", w=5),),
        "mixed": lambda g: (
            g.add_edge("a", "b", w=1),
            g.add_edge("b", "a", w=2),
            g.add_edge("a", "b", w=9),
            g.add_edge("c", "a", w=4),
            g.add_node("z", color="k"),
        ),
        "noattr": lambda g: (g.add_edge("a", "b"), g.add_edge("b", "a")),
        "long_keys": lambda g: (
            g.add_edge("a".ljust(2000, "x"), "b".ljust(2000, "y"), w=1),
            g.add_edge("b".ljust(2000, "y"), "a".ljust(2000, "x"), w=2),
        ),
    }


def _norm(graph):
    nodes = sorted(str(n) for n in graph.nodes())
    node_attrs = sorted((str(n), tuple(sorted(d.items()))) for n, d in graph.nodes(data=True))
    if graph.is_multigraph():
        edges = sorted(
            (str(u), str(v), k, tuple(sorted(d.items())))
            for u, v, k, d in graph.edges(keys=True, data=True)
        )
    else:
        edges = sorted(
            (str(u), str(v), tuple(sorted(d.items())))
            for u, v, d in graph.edges(data=True)
        )
    return nodes, node_attrs, edges


@pytest.mark.parametrize("cls", CLASSES)
@pytest.mark.parametrize("method", METHODS)
@pytest.mark.parametrize("shape", sorted(_shapes()))
def test_conversion_matches_networkx(cls, method, shape):
    build = _shapes()[shape]
    got, want = getattr(fnx, cls)(), getattr(nx, cls)()
    build(got)
    build(want)
    if method == "reverse" and not got.is_directed():
        pytest.skip("reverse is directed-only")
    assert _norm(getattr(got, method)()) == _norm(getattr(want, method)())


@pytest.mark.parametrize("cls", CLASSES)
def test_converted_attr_dicts_are_independent_copies(cls):
    """The kernel deepcopies attrs; a merge must not alias the source's dict.

    If the mirror handle carried in the bucket were the SOURCE dict rather than
    the deepcopied one, mutating the result would write through to the original.
    """
    got, want = getattr(fnx, cls)(), getattr(nx, cls)()
    for g in (got, want):
        g.add_edge("a", "b", w=1)
        g.add_edge("b", "a", w=2)

    def mutate_and_compare(method):
        g_out, w_out = getattr(got, method)(), getattr(want, method)()
        for out in (g_out, w_out):
            for *_e, d in (
                out.edges(keys=True, data=True)
                if out.is_multigraph()
                else out.edges(data=True)
            ):
                d["injected"] = 1
        assert _norm(got) == _norm(want), (
            f"{cls}.{method}() result aliases the SOURCE graph's attr dicts"
        )

    for method in ("to_undirected", "to_directed", "copy"):
        mutate_and_compare(method)


@pytest.mark.parametrize("cls", ["MultiGraph", "MultiDiGraph"])
def test_parallel_edges_keep_distinct_keys_and_attrs(cls):
    """Requirement the bucket exists for: parallel arcs must not collapse."""
    got, want = getattr(fnx, cls)(), getattr(nx, cls)()
    for g in (got, want):
        for i in range(5):
            g.add_edge("a", "b", w=i)
        g.add_edge("b", "a", w=99)

    for method in ("to_undirected", "copy"):
        g_out, w_out = getattr(got, method)(), getattr(want, method)()
        assert g_out.number_of_edges() == w_out.number_of_edges()
        got_ws = sorted(d.get("w") for *_e, d in g_out.edges(keys=True, data=True))
        want_ws = sorted(d.get("w") for *_e, d in w_out.edges(keys=True, data=True))
        assert got_ws == want_ws, f"{cls}.{method}() lost or merged a parallel edge's attrs"
