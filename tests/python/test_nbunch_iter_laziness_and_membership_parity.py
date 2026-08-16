"""br-r37-c1-oaamq — nbunch_iter must be lazy, and its container choice is the cost.

``nbunch_iter`` was the worst row in a 43-row ranked sweep: 0.453x-0.515x against
networkx on all four classes. A native bulk path (br-cc-nbunchbulk) filtered the
whole nbunch in one call to avoid a per-node ``n in self.adj`` crossing. Against
that baseline it WAS an improvement — but ``self.adj`` was never the cheapest
container, and the comparison had not been made against the others. Measured at
N=4000 filtering 2000 nodes, identical work in every row:

    networkx list(nbunch_iter)      88.3 us
    native _nbunch_present         167.0 us   <- what was there
    py `n in self.adj`             433.6 us   <- what it replaced
    py `n in self.nodes`            93.3 us
    py `n in self`                  78.5 us

Decomposed further, the generator skeleton alone is 37.4us (networkx pays it
too), and the explicit per-node ``hash(n)`` was 71.4us — more than networkx
spends on the entire operation. That hash exists only because
``Graph.__contains__`` answers False for an unhashable node instead of raising.
``NodeView.__contains__`` raises, so moving to ``self.nodes`` retires the hash.

THE PARITY HALF MATTERS MORE THAN THE RATIO. networkx's nbunch_iter returns a
lazy GENERATOR over the live graph. The bulk path was eager, so a node added
between the call and the iteration was invisible:

    it = G.nbunch_iter(['a','b','later']); G.add_node('later'); list(it)
    networkx -> ['a','b','later']       fnx -> ['a','b']

on all four classes, and the returned type was ``list_iterator`` where nx's is
``generator``. Both are locked below, because a faster wrong answer is worse
than the slow right one.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


def _pair(cls_name):
    gnx, gfx = getattr(nx, cls_name)(), getattr(fnx, cls_name)()
    for graph in (gnx, gfx):
        graph.add_edge("a", "b")
        graph.add_edge("b", "c")
        graph.add_node("iso")
    return gnx, gfx


@pytest.mark.parametrize("cls_name", CLASSES)
def test_nbunch_iter_is_lazy_over_the_live_graph(cls_name):
    """The contract the eager bulk path broke."""
    results = []
    for lib in (nx, fnx):
        graph = getattr(lib, cls_name)()
        graph.add_edge("a", "b")
        iterator = graph.nbunch_iter(["a", "b", "later"])
        graph.add_node("later")
        results.append(list(iterator))
    assert results[1] == results[0], cls_name
    assert "later" in results[0], "fixture no longer proves laziness"


@pytest.mark.parametrize("cls_name", CLASSES)
def test_a_node_removed_before_iteration_is_also_seen_live(cls_name):
    """Laziness cuts both ways; a removal must register too."""
    results = []
    for lib in (nx, fnx):
        gnx = getattr(lib, cls_name)()
        gnx.add_edge("a", "b")
        gnx.add_node("doomed")
        iterator = gnx.nbunch_iter(["a", "b", "doomed"])
        gnx.remove_node("doomed")
        results.append(list(iterator))
    assert results[1] == results[0], cls_name
    assert "doomed" not in results[0]


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize(
    "kind", ["sequence", "single", "none", "generator", "set", "tuple"]
)
def test_returned_type_matches_networkx(cls_name, kind):
    """nx returns a generator for a sequence and dict_keyiterator for None.

    The runtime type is parity surface — code does ``isinstance`` and pickling
    on these — and the eager path returned ``list_iterator`` for the sequence
    case.
    """
    types = []
    for lib in (nx, fnx):
        gnx, gfx = _pair(cls_name)
        graph = gnx if lib is nx else gfx
        arg = {
            "sequence": ["a", "b"],
            "single": "a",
            "none": None,
            "generator": (n for n in ["a", "b"]),
            "set": {"a", "b"},
            "tuple": ("a", "b"),
        }[kind]
        types.append(type(graph.nbunch_iter(arg)).__name__)
    assert types[1] == types[0], (cls_name, kind, types)


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize(
    "arg",
    [
        ["a", "b"],
        ["a", "zz"],
        [],
        ["a", "a", "a"],
        {"a", "b"},
        ("a", "iso"),
        "a",
        None,
    ],
    ids=["pair", "missing", "empty", "repeats", "set", "tuple", "single", "none"],
)
def test_membership_result_matches_networkx(cls_name, arg):
    gnx, gfx = _pair(cls_name)
    assert list(gfx.nbunch_iter(arg)) == list(gnx.nbunch_iter(arg)), (cls_name, arg)


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize(
    "arg,ids", [(["a", ["x"]], "unhashable-elem"), (3.7, "non-iterable")]
)
def test_error_contract_matches_networkx(cls_name, arg, ids):
    """The explicit hash() was retired; the exception must still be nx's.

    nx relies on plain-dict membership raising TypeError and rewrites it into a
    NetworkXError inside the generator. ``self.nodes`` raises the same way;
    ``Graph.__contains__`` would NOT, which is exactly why it was not chosen
    despite being marginally cheaper.
    """
    results = []
    for lib in (nx, fnx):
        graph = getattr(lib, cls_name)()
        graph.add_edge("a", "b")
        try:
            results.append(("ok", list(graph.nbunch_iter(arg))))
        except Exception as exc:  # noqa: BLE001
            results.append((type(exc).__name__, exc.args))
    assert results[1] == results[0], (cls_name, ids, results)
    assert results[0][0] == "NetworkXError"


@pytest.mark.parametrize("cls_name", CLASSES)
def test_errors_surface_only_when_the_generator_is_consumed(cls_name):
    """A lazy generator does not raise at call time; nx's does not either."""
    for lib in (nx, fnx):
        graph = getattr(lib, cls_name)()
        graph.add_edge("a", "b")
        iterator = graph.nbunch_iter(["a", ["unhashable"]])  # no raise here
        with pytest.raises(nx.NetworkXError):
            list(iterator)


@pytest.mark.parametrize("cls_name", CLASSES)
def test_views_still_filter_by_their_own_membership(cls_name):
    """The old bulk path had to exclude proxy views; the container must not.

    A subgraph's node membership is the VIEW's, not the parent's. Reading the
    parent would silently admit nodes the view hides.
    """
    gnx, gfx = _pair(cls_name)
    for graph_nx, graph_fx in (
        (gnx.subgraph(["a", "b"]), gfx.subgraph(["a", "b"])),
        (gnx.copy(), gfx.copy()),
    ):
        assert list(graph_fx.nbunch_iter(["a", "b", "c", "iso"])) == list(
            graph_nx.nbunch_iter(["a", "b", "c", "iso"])
        )
    if gnx.is_directed():
        assert list(gfx.reverse(copy=False).nbunch_iter(["a", "c", "zz"])) == list(
            gnx.reverse(copy=False).nbunch_iter(["a", "c", "zz"])
        )


def test_a_large_nbunch_matches_networkx_exactly():
    """The shape the ratio was measured on, asserted for content as well."""
    order = 4000
    gnx, gfx = nx.Graph(), fnx.Graph()
    for i in range(order):
        gnx.add_edge(f"n{i}", f"n{(i * 7 + 3) % order}")
        gfx.add_edge(f"n{i}", f"n{(i * 7 + 3) % order}")
    half = [f"n{i}" for i in range(order // 2)] + ["absent"]
    assert list(gfx.nbunch_iter(half)) == list(gnx.nbunch_iter(half))
