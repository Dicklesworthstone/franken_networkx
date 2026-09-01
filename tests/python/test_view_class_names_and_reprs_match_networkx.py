"""br-r37-c1-ih59i — every accessor view prints and names itself as networkx does.

A view's `type(v).__name__` and its `repr` are both public surface: the first is
what every name-based parity check reads, the second is what a `print()` or a log
line shows. Three defects lived there, and a sweep of 76 accessor forms across
the four classes found exactly them.

1. `MG.edges()` and `MDG.edges()` returned the PRIVATE `_LiveMultiEdgeCallView`
   where networkx reports `MultiEdgeDataView` and `OutMultiEdgeDataView`. The
   repr was already right, so only a check that reads the TYPE could see it.

2. `G.degree()` — the CALLED form — reprd as
   `DegreeView([('str:1:a', 1), ...])`. Two things wrong: it walked the
   canonical keys and printed them raw, LEAKING the internal `str:{len}:{s}`
   encoding into user-visible output, and it hardcoded quotes so an int node
   came out as `('5', 5)`. networkx prints `DegreeView({'a': 1, ...})`.

3. `DG.degree()` had no `__repr__` at all and printed
   `<franken_networkx.DiDegreeView object at 0x...>`.

THE NO-PARENS SPELLINGS WERE ALL CORRECT, which is why this survived: `G.degree`
is the Python `_GraphDegreeView` and was fine, and only `G.degree()` reaches the
native class. A sweep of one spelling per accessor would have found nothing.

KEY TYPE IS A REAL AXIS HERE and not decoration: the canonical-key leak only
shows for a `str` node (an int canonicalises to its own digits, so
`('5', 5)`'s defect is the QUOTES, not the encoding). Every case below runs
str, int and tuple keys for that reason.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]
DIRECTED = ["DiGraph", "MultiDiGraph"]
MULTI = ["MultiGraph", "MultiDiGraph"]

KEY_SETS = {
    "str": ("a", "b", "c"),
    "int": (1, 2, 3),
    "tuple": ((1, 2), (3, 4), (5, 6)),
    "mixed": ("a", 2, (3, 4)),
}


def _pair(cls_name, keys):
    graphs = []
    for lib in (nx, fnx):
        g = getattr(lib, cls_name)()
        g.add_edge(keys[0], keys[1], weight=1.0)
        g.add_edge(keys[1], keys[2], weight=2.0)
        graphs.append(g)
    return graphs


def _forms(cls_name, keys):
    table = {
        "edges": lambda g: g.edges,
        "edges()": lambda g: g.edges(),
        "edges(data=True)": lambda g: g.edges(data=True),
        "edges(data='weight')": lambda g: g.edges(data="weight"),
        "edges([n])": lambda g: g.edges([keys[0]]),
        "edges([n],data=True)": lambda g: g.edges([keys[0]], data=True),
        "nodes": lambda g: g.nodes,
        "nodes()": lambda g: g.nodes(),
        "nodes(data=True)": lambda g: g.nodes(data=True),
        "degree": lambda g: g.degree,
        "degree()": lambda g: g.degree(),
        "degree([n])": lambda g: g.degree([keys[0]]),
        "degree(weight=)": lambda g: g.degree(weight="weight"),
        "adj": lambda g: g.adj,
        "adj[n]": lambda g: g.adj[keys[0]],
    }
    if cls_name in DIRECTED:
        table.update({
            "succ": lambda g: g.succ,
            "pred": lambda g: g.pred,
            "out_edges": lambda g: g.out_edges,
            "in_edges": lambda g: g.in_edges,
            "out_edges()": lambda g: g.out_edges(),
            "in_edges()": lambda g: g.in_edges(),
            "in_degree": lambda g: g.in_degree,
            "out_degree": lambda g: g.out_degree,
            "in_degree()": lambda g: g.in_degree(),
            "out_degree()": lambda g: g.out_degree(),
        })
    if cls_name in MULTI:
        table.update({
            "edges(keys=True)": lambda g: g.edges(keys=True),
            "edges([n],keys=True)": lambda g: g.edges([keys[0]], keys=True),
        })
    return table


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("key_kind", sorted(KEY_SETS))
def test_every_view_names_itself_as_networkx_does(cls_name, key_kind):
    """THE SWEEP, on `type(v).__name__`.

    Two cells were wrong: `MG.edges()` and `MDG.edges()` reported the private
    `_LiveMultiEdgeCallView`.
    """
    keys = KEY_SETS[key_kind]
    gnx, gfx = _pair(cls_name, keys)
    fnx_forms, nx_forms = _forms(cls_name, keys), _forms(cls_name, keys)
    for label in nx_forms:
        want = type(nx_forms[label](gnx)).__name__
        got = type(fnx_forms[label](gfx)).__name__
        assert got == want, f"{cls_name} {label} ({key_kind} keys)"


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("key_kind", sorted(KEY_SETS))
def test_every_view_reprs_as_networkx_does(cls_name, key_kind):
    """THE SWEEP, on `repr(v)` — byte for byte, not just the wrapper name."""
    keys = KEY_SETS[key_kind]
    gnx, gfx = _pair(cls_name, keys)
    fnx_forms, nx_forms = _forms(cls_name, keys), _forms(cls_name, keys)
    for label in nx_forms:
        want = repr(nx_forms[label](gnx))
        got = repr(fnx_forms[label](gfx))
        assert got == want, f"{cls_name} {label} ({key_kind} keys)"


@pytest.mark.parametrize("cls_name", CLASSES)
def test_no_repr_leaks_the_canonical_key_encoding(cls_name):
    """The sharpest of the three, asserted on its own.

    `G.degree()` printed the internal `str:{len}:{s}` canonical form. That is
    not a formatting difference — it is an internal encoding reaching a user's
    terminal — so it gets a check that does not depend on networkx agreeing
    with anything.
    """
    _gnx, gfx = _pair(cls_name, KEY_SETS["str"])
    for label, form in _forms(cls_name, KEY_SETS["str"]).items():
        text = repr(form(gfx))
        assert "str:1:" not in text, f"{cls_name} {label} leaked a canonical key: {text}"
        assert "int:" not in text, f"{cls_name} {label} leaked a canonical key: {text}"


@pytest.mark.parametrize("cls_name", CLASSES)
def test_no_repr_is_the_default_object_repr(cls_name):
    """`DG.degree()` had no `__repr__` at all. Nothing here may fall back to one."""
    for key_kind, keys in KEY_SETS.items():
        _gnx, gfx = _pair(cls_name, keys)
        for label, form in _forms(cls_name, keys).items():
            text = repr(form(gfx))
            assert " object at 0x" not in text, (
                f"{cls_name} {label} ({key_kind}) has no __repr__: {text}"
            )


@pytest.mark.parametrize("cls_name", MULTI)
def test_the_renamed_call_view_still_behaves(cls_name):
    """The rename must be a rename and nothing else.

    `MG.edges()` is a live view with `__slots__`; giving it a subclass could
    have handed every result a `__dict__` or broken the liveness the class
    exists for (br-r37-c1-msf5j), so both are asserted rather than assumed.
    """
    gnx, gfx = _pair(cls_name, KEY_SETS["str"])
    for g in (gnx, gfx):
        g.add_edge("a", "b", weight=9.0)  # a parallel edge
    vnx, vfx = gnx.edges(), gfx.edges()
    assert list(vfx) == list(vnx)
    assert len(vfx) == len(vnx)
    assert (("a", "b") in vfx) == (("a", "b") in vnx)
    assert not hasattr(vfx, "__dict__"), "the subclass lost __slots__"

    for g in (gnx, gfx):
        g.add_edge("c", "d")
    assert list(vfx) == list(vnx), "the view stopped being live"
    assert len(vfx) == len(vnx)
