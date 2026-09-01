"""br-r37-c1-eccks — a wrong-arity edge subscript reports the length it got.

networkx gets this text from a real tuple unpack, so CPython supplies it:

    G.edges[('a', 'b', 'c')]   too many values to unpack (expected 2, got 3)

fnx spells the message out in Rust (`unpack_two_endpoints` in views.rs and
`weighted_edge_triplet` in lib.rs), and it was frozen at the older countless
form — CPython 3.14 added the `, got N`.

THE COUNT IS NOT UNCONDITIONAL, and that is the part a hard-coded fix gets
wrong. Measured against a live `a, b = x`, CPython reports the length for an
exact tuple, list or dict and OMITS it for `str`, `bytes`, `bytearray`, `range`,
`set`, `frozenset`, `deque`, a `collections.abc.Sequence`, an object with both
`__len__` and `__iter__`, and any plain iterator or generator. Emitting it
everywhere would trade one divergence for nine, so the product mirrors the rule
and this file pins it AGAINST A LIVE UNPACK rather than against a table written
here — a future CPython change then fails a test instead of silently re-opening
the divergence.

The "not enough values" side is a DIFFERENT rule: CPython reports the count
there for every shape, including a bare iterator. That side was already right
and is carried below so a fix to one cannot break the other.
"""

from __future__ import annotations

import collections
import collections.abc

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]
DIRECTED = ["DiGraph", "MultiDiGraph"]


class _Sequence(collections.abc.Sequence):
    def __init__(self, n):
        self._n = n

    def __len__(self):
        return self._n

    def __getitem__(self, index):
        if index >= self._n:
            raise IndexError(index)
        return index


class _LenAndIter:
    def __init__(self, n):
        self._n = n

    def __len__(self):
        return self._n

    def __iter__(self):
        return iter(range(self._n))


# Every shape whose unpack behaviour differs, so the rule is discovered rather
# than assumed. The expected text is never written down — it is taken from a
# live unpack in the test below.
SHAPES = {
    "tuple": lambda n: tuple(range(n)),
    "list": lambda n: list(range(n)),
    "dict": lambda n: {i: 0 for i in range(n)},
    "set": lambda n: set(range(n)),
    "frozenset": lambda n: frozenset(range(n)),
    "str": lambda n: "abcdefg"[:n],
    "bytes": lambda n: b"abcdefg"[:n],
    "bytearray": lambda n: bytearray(b"abcdefg"[:n]),
    "range": lambda n: range(n),
    "deque": lambda n: collections.deque(range(n)),
    "Sequence": _Sequence,
    "len+iter": _LenAndIter,
    "iterator": lambda n: iter(range(n)),
    "generator": lambda n: (i for i in range(n)),
}


def _live_unpack_two(value):
    """What CPython says for `a, b = value` right now, on this interpreter."""
    try:
        _a, _b = value
    except Exception as exc:  # noqa: BLE001
        return (type(exc).__name__, str(exc))
    return ("ok", None)


def _pair(cls_name):
    graphs = []
    for lib in (nx, fnx):
        g = getattr(lib, cls_name)()
        g.add_edge("a", "b", weight=1.0)
        graphs.append(g)
    return graphs


def _outcome(fn):
    try:
        return ("ok", repr(fn()))
    except Exception as exc:  # noqa: BLE001
        return ("exc", type(exc).__name__, str(exc))


def _spellings(g, cls_name):
    table = {
        "edges[3-tuple]": lambda: g.edges[("a", "b", "c")],
        "edges[4-tuple]": lambda: g.edges[("a", "b", "c", "d")],
        "edges[5-tuple]": lambda: g.edges[("a", "b", "c", "d", "e")],
        "edges[1-tuple]": lambda: g.edges[("a",)],
        "edges[()]": lambda: g.edges[()],
        "edges[3-list]": lambda: g.edges[["a", "b", "c"]],
        "edges[3-iterator]": lambda: g.edges[iter(("a", "b", "c"))],
        "edges[3-set]": lambda: g.edges[{"a", "b", "c"}],
    }
    if cls_name in DIRECTED:
        table["out_edges[3-tuple]"] = lambda: g.out_edges[("a", "b", "c")]
        table["in_edges[3-tuple]"] = lambda: g.in_edges[("a", "b", "c")]
    return table


@pytest.mark.parametrize("cls_name", CLASSES)
def test_wrong_arity_subscripts_match_networkx(cls_name):
    """THE SWEEP. Two of these were red at HEAD, both on Graph."""
    gnx, gfx = _pair(cls_name)
    snx, sfx = _spellings(gnx, cls_name), _spellings(gfx, cls_name)
    for label in snx:
        assert _outcome(sfx[label]) == _outcome(snx[label]), (cls_name, label)


@pytest.mark.parametrize("shape", sorted(SHAPES))
def test_the_count_rule_is_cpythons_not_ours(shape):
    """The rule, taken from a LIVE unpack rather than from a table.

    If CPython ever starts (or stops) reporting the count for one of these
    shapes, this fails and names the shape — which is the whole reason the
    product mirrors the rule instead of appending `, got N` everywhere.
    """
    make = SHAPES[shape]
    live = _live_unpack_two(make(3))
    assert live[0] == "ValueError", (shape, live)
    counted = ", got 3)" in live[1]
    assert counted is (shape in {"tuple", "list", "dict"}), (
        f"CPython changed which shapes carry the unpack count: {shape} now says "
        f"{live[1]!r}. Update fnx's `too_many_values_to_unpack` to match."
    )


@pytest.mark.parametrize("cls_name", ["Graph", "DiGraph"])
@pytest.mark.parametrize("shape", sorted(SHAPES))
def test_the_edge_view_reproduces_that_rule(cls_name, shape):
    """The product's message IS CPython's, shape by shape.

    Graph and DiGraph only: their subscript expects TWO values, so a 3-item
    argument is the over-length case. The multigraph classes expect three and
    would simply look up edge (0, 1, 2) — a KeyError, not an unpack failure —
    which is why they are swept separately against networkx above rather than
    against a two-value unpack here.
    """
    live = _live_unpack_two(SHAPES[shape](3))
    _gnx, gfx = _pair(cls_name)
    with pytest.raises(ValueError) as exc:
        gfx.edges[SHAPES[shape](3)]
    assert str(exc.value) == live[1], (cls_name, shape)


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("shape", sorted(SHAPES))
def test_not_enough_values_always_carries_its_count(cls_name, shape):
    """The other rule: CPython counts on this side for EVERY shape.

    Carried so a change to the `too many` branch cannot quietly take the count
    off the `not enough` one — they are two different rules in one function.
    The oracle here is NETWORKX rather than a hand-rolled unpack, because the
    expected arity differs by class (two for Graph and DiGraph, three for the
    multigraph pair) and networkx knows which.
    """
    assert ", got 1)" in _live_unpack_two(SHAPES[shape](1))[1], shape
    gnx, gfx = _pair(cls_name)
    assert _outcome(lambda: gfx.edges[SHAPES[shape](1)]) == _outcome(
        lambda: gnx.edges[SHAPES[shape](1)]
    ), (cls_name, shape)
