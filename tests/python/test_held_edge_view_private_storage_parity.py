"""A HELD `G.edges` view must ignore private storage assigned after it was built.

br-r37-c1-hvw2e-8smdi. networkx's edge views capture the adjacency MAPPING OBJECT once,
in `__init__`::

    def __init__(self, G):
        self._graph = G
        self._adjdict = G._succ if hasattr(G, "succ") else G._adj

and `__getitem__` reads only `self._adjdict[u][v]` — it never re-reads `G._succ`.
So assigning `G._adj` / `G._succ` AFTER a view exists cannot change what that view
answers. fnx's Python edge views re-ran `_has_networkx_private_storage(self._graph)`
on every subscript in order to make a held view "notice" a late override, which
inverted the contract: fnx raised `KeyError` where networkx returns the edge, in 6
cells of the 4-class x 4-attribute x 2-order matrix below.

NEGATIVE CASE a naive implementation fails: the `view_before` rows. An
implementation that consults private storage per call — the previous behaviour, and
the natural one to write — answers `KeyError` for every one of them. An
implementation that never consults private storage at all fails the `view_after`
rows instead, where the override IS in place at construction and must be honoured.
Only capture-at-construction passes both halves, which is why both orders are
asserted rather than just the one that was broken.

WHY BOTH ORDERS, NOT JUST THE FIXED ONE: `view_after` is what
`test_assigned_private_edge_view_getitem_parity.py` already covers, and it is
precisely the case in which the old and new behaviour AGREE. Testing only the
broken order would let a later "fix" that drops the construction-time check pass.

`Graph` is xfail: its `G.edges` is the native `_fnx.EdgeView` whose `__getitem__`
is a C slot doing its own per-call `private_adj_row` probe, so it still carries the
defect this module fixes in the three Python views. Removing the xfail is the gate
on the Rust half.
"""

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]
PRIVATE_ATTRS = ["_adj", "_succ", "_pred", "_node"]
ORDERS = ["view_before", "view_after"]

# The cells where fnx's native EdgeView C slot still diverges. Graph only.
NATIVE_SLOT_DEFECT = {("Graph", "_adj", "view_before")}


def _subscript(module, class_name, private_attr, order):
    """Build a one-edge graph, assign private storage, and subscript `G.edges`.

    `order` decides whether the view is created BEFORE or AFTER the assignment;
    that ordering is the entire contract under test.
    """
    graph = getattr(module, class_name)()
    key = graph.add_edge("a", "b", w=1)
    subscript = ("a", "b", key) if class_name.startswith("Multi") else ("a", "b")
    # An adjacency that HIDES the edge: "a" is present with no neighbours. If the
    # view reads this mapping the answer is KeyError; if it reads the state it
    # captured, the answer is {'w': 1}.
    override = {"a": {}, "b": {}}
    if order == "view_before":
        view = graph.edges
        setattr(graph, private_attr, override)
    else:
        setattr(graph, private_attr, override)
        view = graph.edges
    try:
        return ("ok", repr(view[subscript]))
    except Exception as exc:  # noqa: BLE001 - the exception IS the contract
        return (type(exc).__name__, repr(exc.args))


@pytest.mark.parametrize("order", ORDERS)
@pytest.mark.parametrize("private_attr", PRIVATE_ATTRS)
@pytest.mark.parametrize("class_name", CLASSES)
def test_held_edge_view_matches_networkx(class_name, private_attr, order):
    if (class_name, private_attr, order) in NATIVE_SLOT_DEFECT:
        pytest.xfail(
            "native _fnx.EdgeView C slot still re-probes private storage per "
            "call (br-r37-c1-hvw2e-8smdi, Rust half)"
        )
    expected = _subscript(nx, class_name, private_attr, order)
    actual = _subscript(fnx, class_name, private_attr, order)
    assert actual == expected, (
        f"{class_name}.edges[...] with {private_attr} assigned "
        f"{'after' if order == 'view_before' else 'before'} the view was built: "
        f"networkx gave {expected}, fnx gave {actual}. networkx captures the "
        f"adjacency mapping in __init__, so a view built BEFORE the assignment "
        f"must not see it, and one built AFTER must."
    )


@pytest.mark.parametrize("class_name", ["DiGraph", "MultiGraph", "MultiDiGraph"])
def test_held_view_subscript_costs_one_python_frame(class_name):
    """The fix is also the perf lever, so pin the frame count it bought.

    The per-call guard was a second Python call frame on every subscript, where
    networkx pays exactly one (`reportviews.__getitem__`). Counting frames rather
    than timing them is deliberate: it is load-independent, so this assertion
    means the same thing on a quiet host and a host at loadavg 40, where a timing
    assertion would be flaky. If a future change reintroduces a per-call helper
    this fails with the helper named.
    """
    import sys

    graph = getattr(fnx, class_name)()
    key = graph.add_edge("a", "b", w=1)
    subscript = ("a", "b", key) if class_name.startswith("Multi") else ("a", "b")
    view = graph.edges
    view[subscript]  # warm any accessor caches so they are not counted

    seen = []

    def record(frame, event, _arg):
        if event == "call":
            seen.append(frame.f_code.co_name)

    sys.setprofile(record)
    try:
        view[subscript]
    finally:
        sys.setprofile(None)

    assert seen == ["__getitem__"], (
        f"{class_name}.edges[u,v] should cost exactly one Python frame — the "
        f"view's own __getitem__, matching networkx — but called {seen}."
    )
