"""Deliberate-divergence lock for br-r37-c1-cow38 — custom node-key equality.

fnx canonicalises every node key to a string and compares those bytes, so it
implements ONE equivalence relation: character identity. networkx stores nodes
in a dict, so the key's own ``__eq__``/``__hash__`` define the relation. A node
key that redefines equality therefore matches in networkx and misses in fnx.

That is a DECLARED SCOPE BOUNDARY, not an open defect — see "Declared Scope
Boundary: Node-Key Equivalence" in FEATURE_PARITY.md for why closing it needs a
storage-model change whose cost is itself an open bead
(br-r37-c1-node-storage-materialization-wall-5fije).

This file therefore asserts the divergence FROM BOTH SIDES: networkx matches,
fnx does not. That is unusual and intentional. **If these tests start failing
because fnx began agreeing with networkx, the boundary has moved and
FEATURE_PARITY.md is what needs updating — do not "fix" the test.**

What is NOT a scope boundary, and is asserted as ordinary parity below: a plain
``str`` subclass that does not override anything must behave exactly like
``str`` in both libraries, and the hashability contract (br-r37-c1-lvlu7,
closed in c14dc2ecf) must hold.
"""

from __future__ import annotations

import networkx as nx
import pytest

import franken_networkx as fnx

CLASSES = ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]


class CaseFoldingStr(str):
    """A node key asserting that 'N0' and 'n0' are the same node."""

    def __hash__(self):
        return hash(str(self).lower())

    def __eq__(self, other):
        return str(self).lower() == str(other).lower()

    def __ne__(self, other):
        return not self.__eq__(other)


class PlainStr(str):
    """A subclass that redefines NOTHING — ordinary parity, not a boundary."""


def _pair(cls_name):
    made = []
    for lib in (nx, fnx):
        graph = getattr(lib, cls_name)()
        graph.add_edge("n0", "n1")
        made.append(graph)
    return made


def _answer(fn, graph):
    try:
        result = fn(graph)
    except Exception as exc:  # noqa: BLE001 - an exception is a valid answer
        return ("raised", type(exc).__name__)
    if isinstance(result, (int, float)):
        return ("number", result)
    try:
        return ("view", sorted(dict(result).items()))
    except TypeError:
        return ("value", result)


PROBES = [
    ("n in G", lambda g, key: key in g),
    ("G.has_node(n)", lambda g, key: g.has_node(key)),
    ("n in G.nodes", lambda g, key: key in g.nodes),
    ("(n,v) in G.edges", lambda g, key: (key, "n1") in g.edges),
    ("G.has_edge(n,v)", lambda g, key: g.has_edge(key, "n1")),
]


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize(("label", "probe"), PROBES, ids=[p[0] for p in PROBES])
def test_custom_equality_key_matches_in_networkx_and_misses_in_fnx(
    cls_name, label, probe
):
    """THE DECLARED DIVERGENCE. Both sides asserted on purpose."""
    gnx, gfx = _pair(cls_name)
    key = CaseFoldingStr("N0")
    assert probe(gnx, key) is True, (
        f"networkx no longer honours custom node-key equality for {label}; "
        "the premise of the scope boundary has changed"
    )
    assert probe(gfx, key) is False, (
        f"fnx now matches networkx for {label} on a custom-equality node key. "
        "That is an IMPROVEMENT, not a regression: update the 'Declared Scope "
        "Boundary: Node-Key Equivalence' section of FEATURE_PARITY.md and this "
        "file rather than reverting the behaviour."
    )


@pytest.mark.parametrize("cls_name", CLASSES)
def test_custom_equality_key_degree_divergence(cls_name):
    """degree() answers a number in networkx and an empty view in fnx."""
    gnx, gfx = _pair(cls_name)
    key = CaseFoldingStr("N0")
    assert _answer(lambda g: g.degree(key), gnx) == ("number", 1)
    assert _answer(lambda g: g.degree(key), gfx) == ("view", [])


@pytest.mark.parametrize("cls_name", CLASSES)
def test_exact_value_key_is_unaffected_by_the_boundary(cls_name):
    """The same subclass spelled with the STORED characters matches in both."""
    gnx, gfx = _pair(cls_name)
    key = CaseFoldingStr("n0")
    for label, probe in PROBES:
        assert probe(gfx, key) == probe(gnx, key) is True, label


@pytest.mark.parametrize("cls_name", CLASSES)
def test_plain_str_subclass_is_full_parity_not_a_boundary(cls_name):
    """A subclass that overrides nothing is ordinary parity in both directions."""
    gnx, gfx = _pair(cls_name)
    for label, probe in PROBES:
        assert probe(gfx, PlainStr("n0")) == probe(gnx, PlainStr("n0")) is True, label
        assert probe(gfx, PlainStr("zz")) == probe(gnx, PlainStr("zz")) is False, label


@pytest.mark.parametrize("cls_name", CLASSES)
def test_hashability_contract_is_in_scope_and_still_holds(cls_name):
    """br-r37-c1-lvlu7: unhashable keys must behave exactly as in networkx."""

    class Unhashable(str):
        __hash__ = None

    gnx, gfx = _pair(cls_name)
    key = Unhashable("n0")
    for label, probe in PROBES:
        assert _answer(lambda g: probe(g, key), gfx) == _answer(
            lambda g: probe(g, key), gnx
        ), label


@pytest.mark.parametrize("cls_name", CLASSES)
def test_custom_equality_key_cannot_corrupt_the_graph_through_add(cls_name):
    """Adding under the alias must not silently merge or duplicate differently
    from a plain unequal key: whatever fnx does, it stays self-consistent."""
    gnx, gfx = _pair(cls_name)
    for graph in (gnx, gfx):
        graph.add_node(CaseFoldingStr("N0"))
    # networkx treats it as the SAME node; fnx as a NEW one. Assert each
    # library's own count so a silent change in either is caught.
    assert gnx.number_of_nodes() == 2
    assert gfx.number_of_nodes() == 3
    for graph in (gnx, gfx):
        assert all(n in graph for n in graph.nodes)


class CustomNode:
    """Non-primitive custom object with value-based __eq__ and __hash__."""

    def __init__(self, ident: int, label: str = ""):
        self.ident = ident
        self.label = label

    def __hash__(self):
        return hash(("CustomNode", self.ident))

    def __eq__(self, other):
        return isinstance(other, CustomNode) and self.ident == other.ident


class CollidingCustomNode:
    """Custom object with constant hash to force hash collisions."""

    def __init__(self, ident: int):
        self.ident = ident

    def __hash__(self):
        return 424242

    def __eq__(self, other):
        return isinstance(other, CollidingCustomNode) and self.ident == other.ident


@pytest.mark.parametrize("cls_name", CLASSES)
def test_non_primitive_custom_object_equality_and_collision_parity(cls_name):
    """br-r37-c1-epic-storage-architecture-yr2oc.5: non-primitive custom objects
    with value-based __eq__/__hash__ (and hash collisions) match NetworkX both
    directly and inside tuple node/edge keys."""
    gnx = getattr(nx, cls_name)()
    gfx = getattr(fnx, cls_name)()

    a1 = CustomNode(1, "first")
    a2 = CustomNode(1, "second")
    b1 = CollidingCustomNode(10)
    b2 = CollidingCustomNode(10)
    b_other = CollidingCustomNode(20)

    for g in (gnx, gfx):
        g.add_edge(a1, b1)
        g.add_edge((a1, 1), (b1, 2))

    assert (a2 in gfx) == (a2 in gnx) is True
    assert (b2 in gfx) == (b2 in gnx) is True
    assert (b_other in gfx) == (b_other in gnx) is False
    assert gfx.has_edge(a2, b2) == gnx.has_edge(a2, b2) is True
    assert gfx.has_edge(a2, b_other) == gnx.has_edge(a2, b_other) is False
    assert ((a2, 1) in gfx) == ((a2, 1) in gnx) is True
    assert gfx.has_edge((a2, 1), (b2, 2)) == gnx.has_edge((a2, 1), (b2, 2)) is True


@pytest.mark.parametrize("cls_name", CLASSES)
def test_remove_node_cleans_up_neighbor_aliases_and_preserves_other_edges(cls_name):
    """br-r37-c1-epic-storage-architecture-yr2oc.5: neighbor-scoped O(deg(u))
    remove_node cleanup removes incident alias entries while keeping non-incident
    adjacency key aliases intact."""
    gnx = getattr(nx, cls_name)()
    gfx = getattr(fnx, cls_name)()
    for g in (gnx, gfx):
        g.add_edge(0, 1.0)
        g.add_edge(1, 2.0)
        g.add_edge(2, 3.0)
        g.remove_node(1)
    assert list(gfx.nodes) == list(gnx.nodes)
    assert list(gfx.edges) == list(gnx.edges)
    assert dict(gfx[2]) == dict(gnx[2])


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize("nested", [False, True], ids=["node", "tuple-node"])
def test_equal_node_in_another_graph_survives_first_representative_collection(
    cls_name, nested
):
    """Collecting one graph cannot invalidate an equal node in another graph."""
    import gc
    import weakref

    for lib in (nx, fnx):
        original = CustomNode(810001, "first graph")
        survivor = CustomNode(810001, "second graph")
        original_ref = weakref.ref(original)
        first = getattr(lib, cls_name)()
        second = getattr(lib, cls_name)()
        first.add_edge((original, "node") if nested else original, "target")
        key = (survivor, "node") if nested else survivor
        second.add_edge(key, "target", weight=7)
        del first, original
        gc.collect()
        assert original_ref() is None

        alias = CustomNode(810001, "lookup")
        alias_key = (alias, "node") if nested else alias
        assert key in second
        assert alias_key in second
        assert second.has_edge(alias_key, "target")
        assert list(second.neighbors(alias_key)) == ["target"]
        assert lib.shortest_path(second, alias_key, "target") == [alias_key, "target"]
        second.add_node(alias_key, retained=True)
        assert second.number_of_nodes() == 2
        assert second.nodes[key]["retained"] is True
        second.remove_node(alias_key)
        assert list(second) == ["target"]


@pytest.mark.parametrize("cls_name", ["MultiGraph", "MultiDiGraph"])
def test_equal_multiedge_key_survives_first_representative_collection(cls_name):
    import gc
    import weakref

    for lib in (nx, fnx):
        original = CustomNode(810002, "first graph")
        survivor = CustomNode(810002, "second graph")
        original_ref = weakref.ref(original)
        first = getattr(lib, cls_name)()
        second = getattr(lib, cls_name)()
        first.add_edge("a", "b", key=original)
        second.add_edge("a", "b", key=survivor, weight=9)
        del first, original
        gc.collect()
        assert original_ref() is None

        alias = CustomNode(810002, "lookup")
        assert second.has_edge("a", "b", key=alias)
        assert second.get_edge_data("a", "b", key=alias) == {"weight": 9}
        second.remove_edge("a", "b", key=alias)
        assert second.number_of_edges() == 0


@pytest.mark.parametrize("cls_name", CLASSES)
def test_live_custom_nodes_survive_global_interner_pressure(cls_name):
    """A graph larger than the old cache limit must retain all of its nodes."""
    import os
    import subprocess
    import sys
    import textwrap

    code = textwrap.dedent(
        """
        import sys
        import networkx as nx
        import franken_networkx as fnx

        class Node:
            def __init__(self, value):
                self.value = value
            def __hash__(self):
                return 900000 + self.value
            def __eq__(self, other):
                return isinstance(other, Node) and self.value == other.value

        nodes = [Node(i) for i in range(65600)]
        for lib in (nx, fnx):
            graph = getattr(lib, sys.argv[1])()
            graph.add_nodes_from(nodes)
            assert graph.number_of_nodes() == len(nodes)
            missing = sum(node not in graph for node in nodes)
            assert missing == 0, (lib.__name__, missing)
            graph.add_edge(nodes[0], nodes[-1], weight=3)
            assert graph.number_of_nodes() == len(nodes)
            assert graph.has_edge(Node(0), Node(len(nodes) - 1))
            assert lib.shortest_path(graph, Node(0), Node(len(nodes) - 1)) == [
                nodes[0], nodes[-1]
            ]
        """
    )
    env = dict(os.environ, OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1")
    completed = subprocess.run(
        [sys.executable, "-c", code, cls_name],
        capture_output=True,
        text=True,
        timeout=45,
        env=env,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def _custom_key_reentry_probe(lib, cls_name, case, weak_nodes):
    import gc
    import weakref

    primary = getattr(lib, cls_name)()
    secondary = getattr(lib, cls_name)()
    callbacks = []
    bucket = 19700317

    class Payload:
        pass

    class NodeBase:
        __slots__ = ("value", "bucket", "callback", "finalize", "payload")

        def __init__(self, value, node_bucket=bucket):
            self.value = value
            self.bucket = node_bucket
            self.callback = None
            self.finalize = None
            self.payload = None

        def __hash__(self):
            return self.bucket

        def __eq__(self, other):
            if not isinstance(other, NodeBase):
                return False
            if self.callback is not None:
                self.callback(other)
            return self.value == other.value

        def __del__(self):
            if self.finalize is not None:
                self.finalize()

    class WeakNode(NodeBase):
        __slots__ = ("__weakref__",)

    class StrongNode(NodeBase):
        __slots__ = ()

    Node = WeakNode if weak_nodes else StrongNode
    anchor = Node(2 if case == "weakref_callback" else 1)
    primary.add_node(anchor)

    if case == "weakref_callback":
        # A global equality comparison can release a representative held by
        # another graph. Its weakref callback must reuse the published base.
        holder = getattr(lib, cls_name)()
        holder.add_node(anchor)
        primary.clear()

        def insert_from_weakref(_):
            callbacks.append("weakref")
            secondary.add_node(Node(2))

        def release_anchor(other):
            if other.value == 2:
                holder.clear()

        reference = weakref.ref(anchor, insert_from_weakref)
        anchor.callback = release_anchor
        del anchor
        incoming = Node(2)
        primary.add_node(incoming)
        assert reference() is None
        assert callbacks == ["weakref"]
        assert incoming in primary
        assert incoming in secondary
        assert primary.number_of_nodes() == secondary.number_of_nodes() == 1
        assert holder.number_of_nodes() == 0
        return

    if case == "weakref_node":
        # The same weakref object can be a Weak registry reference and a
        # distinct Strong graph key. Pruning one must preserve the other.
        reference = weakref.ref(anchor)
        primary.add_node(reference)
        assert primary.number_of_nodes() == 2
        assert reference in primary
        assert anchor in primary
        primary.remove_node(anchor)
        del anchor
        gc.collect()
        assert reference() is None
        assert reference in primary
        assert primary.number_of_nodes() == 1
        primary.remove_node(reference)
        assert primary.number_of_nodes() == 0
        return

    if case == "finalizer":
        def insert_from_finalizer():
            callbacks.append("finalizer")
            secondary.add_node(Node(2))

        anchor.finalize = insert_from_finalizer
        anchor.payload = Payload()
        anchor_payload = weakref.ref(anchor.payload)
        del anchor
        primary.clear()
        gc.collect()
    else:
        def insert_from_equality(other):
            if other.value != 2:
                return
            callbacks.append("equality")
            assert len(callbacks) <= 16, "unbounded equality retry"
            if case in ("equal_alias", "same_object"):
                anchor.callback = None
                secondary.add_node(other if case == "same_object" else Node(2))
            else:
                other_bucket = bucket if case == "same_hash_unrelated" else bucket + len(callbacks)
                secondary.add_node(Node(100 + len(callbacks), other_bucket))

        anchor.callback = insert_from_equality

    incoming = Node(2)
    incoming.payload = Payload()
    incoming_payload = weakref.ref(incoming.payload)
    primary.add_node(incoming)
    assert callbacks
    if case != "finalizer":
        anchor.callback = None
    assert incoming in primary, (lib.__name__, case, "stored node is unreachable")
    assert Node(2) in primary, (lib.__name__, case, "equal lookup misses")
    assert primary.number_of_nodes() == (1 if case == "finalizer" else 2)
    if case in ("equal_alias", "same_object", "finalizer"):
        assert incoming in secondary
        assert secondary.number_of_nodes() == 1
    if case == "finalizer":
        assert anchor_payload() is None
        assert callbacks == ["finalizer"]

    primary.clear()
    secondary.clear()
    del incoming
    gc.collect()
    primary.add_node(Node(3))
    gc.collect()
    assert incoming_payload() is None, (lib.__name__, case, "dead alias was retained")


@pytest.mark.parametrize("cls_name", CLASSES)
@pytest.mark.parametrize(
    "case,weak_nodes",
    [
        (case, weak)
        for case in (
            "equal_alias", "same_object", "same_hash_unrelated", "other_hash_unrelated"
        )
        for weak in (False, True)
    ] + [("finalizer", False), ("weakref_node", True), ("weakref_callback", True)],
)
def test_custom_key_reentry_preserves_identity_and_lifetime(cls_name, case, weak_nodes):
    import subprocess
    import sys

    code = (
        "import runpy, sys\n"
        "scope = runpy.run_path(sys.argv[1])\n"
        # NetworkX has no global registry or cross-graph equality callback.
        "names = ('fnx',) if sys.argv[3]=='weakref_callback' else ('nx', 'fnx')\n"
        "for name in names:\n"
        " scope['_custom_key_reentry_probe'](scope[name], *sys.argv[2:4], sys.argv[4]=='True')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code, __file__, cls_name, case, str(weak_nodes)],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
