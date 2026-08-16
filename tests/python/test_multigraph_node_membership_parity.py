"""Lock for br-r37-c1-alll4 — multigraph `n in G.nodes()`.

The multigraph node views now answer membership the way their `has_node` twin
already did: an EXACT `str` goes through the present-key memo, everything else
is hash-checked and probed with a borrowed canonical.

Both halves of that gate are behavioural, not cosmetic:

* the memo is a Python set keyed by the caller's object, so a `str` SUBCLASS
  that overrides `__hash__`/`__eq__` must NOT reach it — it would resolve to
  whatever entry it claims to equal, and only once that entry had been probed,
  making the answer depend on cache state,
* the memo is invalidated by ``nodes_seq``, so a node removed and re-added must
  not answer from a stale entry.

Both are asserted here, alongside plain membership against live networkx.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


class _Unhashable(str):
    __hash__ = None


class _PlainSubclass(str):
    pass


class _CaseFolding(str):
    def __hash__(self):
        return hash(str(self).lower())

    def __eq__(self, other):
        return str(self).lower() == str(other).lower()


def _pair(cls_name):
    made = []
    for lib in (nx, fnx):
        graph = getattr(lib, cls_name)()
        graph.add_nodes_from(["a", "b", "c"])
        graph.add_edge("a", "b")
        made.append(graph)
    return made


def _outcome(fn, graph):
    try:
        return ("value", fn(graph))
    except Exception as exc:  # noqa: BLE001
        return ("raised", type(exc).__name__)


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize(
    "key",
    ["a", "zz", "", 5, (1, 2), _PlainSubclass("a"), _PlainSubclass("zz")],
    ids=["present", "absent", "empty", "int", "tuple", "sub-present", "sub-absent"],
)
def test_node_membership_matches_networkx(cls_name, key):
    gnx, gfx = _pair(cls_name)
    assert _outcome(lambda g: key in g.nodes, gfx) == _outcome(
        lambda g: key in g.nodes, gnx
    )


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("bad", [_Unhashable("a"), ["a"], {"a": 1}], ids=["str", "list", "dict"])
def test_unhashable_key_matches_networkx(cls_name, bad):
    """nx's `n in self._nodes` hashes, so unhashable keys raise TypeError."""
    gnx, gfx = _pair(cls_name)
    assert _outcome(lambda g: bad in g.nodes, gfx) == _outcome(
        lambda g: bad in g.nodes, gnx
    )


@pytest.mark.parametrize("cls_name", CLASSES)
def test_memo_is_invalidated_by_remove_and_readd(cls_name):
    """A stale memo entry would report a removed node as present."""
    gnx, gfx = _pair(cls_name)
    for graph in (gnx, gfx):
        assert "a" in graph.nodes  # populate the memo
        graph.remove_node("a")
    assert ("a" in gfx.nodes) == ("a" in gnx.nodes) is False
    for graph in (gnx, gfx):
        graph.add_node("a")
    assert ("a" in gfx.nodes) == ("a" in gnx.nodes) is True


@pytest.mark.parametrize("cls_name", CLASSES)
def test_overriding_str_subclass_does_not_reach_the_memo(cls_name):
    """The exact-`str` gate: a lying subclass must not resolve via the set.

    Probing the equal exact key FIRST populates the memo; a subclass that hashes
    and compares equal to it would then hit that entry if the gate were widened
    to `isinstance`. The answer must not depend on what was probed before.
    """
    gnx, gfx = _pair(cls_name)
    cold = _CaseFolding("A") in gfx.nodes
    assert "a" in gfx.nodes  # populate the memo with the exact key
    warm = _CaseFolding("A") in gfx.nodes
    assert cold == warm, "membership answer changed with memo state"
    # fnx canonicalises by characters, so 'A' is simply not a node. networkx
    # honours the subclass's equality and finds 'a' — a declared scope boundary
    # (br-r37-c1-cow38), asserted here only as fnx self-consistency.
    assert warm is False
    assert (_CaseFolding("a") in gfx.nodes) == (_CaseFolding("a") in gnx.nodes) is True


@pytest.mark.parametrize("cls_name", CLASSES)
def test_membership_spellings_agree_with_each_other(cls_name):
    """`n in G`, `G.has_node(n)` and `n in G.nodes()` are one question."""
    gnx, gfx = _pair(cls_name)
    for key in ("a", "zz", 5):
        answers = {key in gfx, gfx.has_node(key), key in gfx.nodes}
        assert len(answers) == 1, (key, answers)
        assert answers == {key in gnx}
