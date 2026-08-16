"""`G.degree(nbunch)` must match networkx for every argument shape.

br-r37-c1-ey6ob. The exact-`str` lookup in `_WeightAwareDegreeView.__call__` is
now hoisted ABOVE the sequence test. That reordering is safe only because the
sequence branch is guarded by `not isinstance(nbunch, (str, bytes))`, so an exact
`str` could never take it — but "could never" is exactly the kind of claim that
needs a test, because the branch order is now load-bearing.

The two cases that would catch a bad hoist:

* a `str` SUBCLASS must still fall through to the unchanged path. `type(x) is
  str` is False for it, and that matters: the native lookup resolves a key by its
  CHARACTERS and never calls `__hash__`, so an UNHASHABLE `str` subclass routed
  into the fast path would come back with a NUMBER where networkx returns an
  empty view.
* an ABSENT plain `str` is NOT an error in networkx. `G.degree("nope")` runs
  `nbunch_iter`, which iterates the string's CHARACTERS, so it yields an empty
  view rather than raising. Code like `if G.degree(n):` depends on that.

Everything here is asserted against live networkx rather than against a recorded
expectation, so it stays correct if the incumbent's contract shifts.
"""

import pytest

import networkx as nx

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


class HashableStr(str):
    """A `str` subclass that is still hashable — must behave like its value."""


class UnhashableStr(str):
    """A `str` subclass that cannot be hashed.

    networkx's membership test rejects it, so `G.degree` yields an empty view.
    Routing it into the character-based native lookup would return a number.
    """

    __hash__ = None


def _pair(class_name):
    fnx_graph = getattr(fnx, class_name)()
    nx_graph = getattr(nx, class_name)()
    for graph in (fnx_graph, nx_graph):
        graph.add_edge("n1", "n2")
        graph.add_edge("n1", "n3")
        graph.add_edge("n2", "n3")
        graph.add_node("solo")
    return fnx_graph, nx_graph


def _outcome(graph, argument):
    try:
        result = graph.degree(argument)
        if isinstance(result, int):
            return ("int", result)
        return ("view", sorted(result))
    except Exception as exc:  # noqa: BLE001 - the exception is the contract
        return (type(exc).__name__, str(exc))


ARGUMENTS = {
    "present_str": "n1",
    "absent_str": "zzzz",
    "empty_str": "",
    "single_char_present": "n",
    "list": ["n1", "n2", "zz"],
    "tuple": ("n1", "n3"),
    "set": {"n2"},
    "frozenset": frozenset({"n3"}),
    "bytes": b"n1",
    "int": 99,
    "float": 1.5,
    "hashable_str_subclass": HashableStr("n1"),
    "unhashable_str_subclass": UnhashableStr("n1"),
}


@pytest.mark.parametrize("class_name", CLASSES)
@pytest.mark.parametrize("argument_name", sorted(ARGUMENTS))
def test_degree_call_matches_networkx_for_every_argument_shape(
    class_name, argument_name
):
    argument = ARGUMENTS[argument_name]
    fnx_graph, nx_graph = _pair(class_name)
    assert _outcome(fnx_graph, argument) == _outcome(nx_graph, argument), (
        f"{class_name}.degree({argument!r}) diverged. The exact-str fast path is "
        f"hoisted above the sequence test, so branch ORDER is load-bearing here."
    )


@pytest.mark.parametrize("class_name", CLASSES)
def test_absent_plain_string_yields_an_empty_view_not_an_error(class_name):
    """networkx iterates an absent string's CHARACTERS rather than raising."""
    fnx_graph, nx_graph = _pair(class_name)
    assert _outcome(fnx_graph, "nope") == _outcome(nx_graph, "nope")
    # Defensive code depends on this being falsey rather than an exception.
    assert not list(fnx_graph.degree("nope"))


@pytest.mark.parametrize("class_name", CLASSES)
def test_unhashable_str_subclass_does_not_reach_the_character_lookup(class_name):
    """The reason the fast path is gated on `type(x) is str`, not isinstance."""
    fnx_graph, nx_graph = _pair(class_name)
    expected = _outcome(nx_graph, UnhashableStr("n1"))
    actual = _outcome(fnx_graph, UnhashableStr("n1"))
    assert actual == expected
    assert actual[0] != "int", (
        "an unhashable str subclass returned a degree NUMBER; it reached the "
        "character-based native lookup, which never calls __hash__"
    )


@pytest.mark.parametrize("class_name", CLASSES)
def test_generator_nbunch_still_works(class_name):
    """A generator has __iter__ but is not a list/tuple/set — the hasattr arm."""
    fnx_graph, nx_graph = _pair(class_name)
    assert sorted(fnx_graph.degree(n for n in ["n1", "n2"])) == sorted(
        nx_graph.degree(n for n in ["n1", "n2"])
    )


@pytest.mark.parametrize("class_name", CLASSES)
@pytest.mark.parametrize("weight", [None, "weight"])
def test_weighted_and_unweighted_agree_for_each_shape(class_name, weight):
    """The hoist sits inside the `weight is None` arm; the weighted arm must not move."""
    fnx_graph, nx_graph = _pair(class_name)
    for graph in (fnx_graph, nx_graph):
        for u, v in list(graph.edges())[:2]:
            if graph.is_multigraph():
                graph[u][v][0]["weight"] = 3
            else:
                graph[u][v]["weight"] = 3
    for argument in ("n1", "zzzz", ["n1", "n2"]):
        try:
            expected = nx_graph.degree(argument, weight)
            expected = expected if isinstance(expected, (int, float)) else sorted(expected)
            expected_error = None
        except Exception as exc:  # noqa: BLE001
            expected, expected_error = None, type(exc).__name__
        try:
            actual = fnx_graph.degree(argument, weight)
            actual = actual if isinstance(actual, (int, float)) else sorted(actual)
            actual_error = None
        except Exception as exc:  # noqa: BLE001
            actual, actual_error = None, type(exc).__name__
        assert (actual, actual_error) == (expected, expected_error), (
            f"{class_name}.degree({argument!r}, weight={weight!r}) diverged"
        )
