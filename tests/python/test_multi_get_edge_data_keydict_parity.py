"""Unkeyed multigraph ``get_edge_data`` must build the SAME keydict as networkx.

br-r37-c1-ptiz2. The unkeyed branch loops over the parallel edges of one
endpoint pair and, for each key, called BOTH ``ensure_edge_py_attrs`` and
``py_edge_key``. Each of those re-derives ``edge_key(u, v, k)``, which does
``u.to_owned(), v.to_owned()`` — so the loop allocated four full-length node-key
strings per parallel edge, all byte-identical across iterations, purely to vary
one ``usize``. Measured against a flat networkx (95-103ns at every parallel
count), fnx grew 360ns at par=1 to 30366ns at par=128: 0.0072x at par=64, the
worst cell in the campaign.

The lever hoists the tuple out of the loop and overwrites ``.2`` per key.

THE NEGATIVE CASE, and the reason this file exists rather than a benchmark note:
a single mutable tuple reused across iterations is only correct if every consumer
reads it before the next overwrite and none of them retains it. Two consumers
read it — the attr-dict mirror and the PUBLIC KEY mirror (``edge_py_keys``) —
and the second is the dangerous one, because it is a lookup keyed by the whole
tuple. If the reused tuple were stale or mis-sequenced by even one iteration,
every parallel edge would come back under its NEIGHBOUR's public key: a silent
wrong-answer bug that value-only assertions on the attribute dicts would not
catch. ``test_custom_public_keys_survive`` and ``test_key_to_attr_pairing`` pin
exactly that pairing.

The undirected ``edge_key`` also SORTS its endpoints (``u <= v``), so the tuple
is built from the sorted pair; the directed twin does not. Both orientations are
exercised so a hoist that captured the wrong orientation once, outside the loop,
cannot pass.
"""

import pytest

import networkx as nx

import franken_networkx as fnx

CLASSES = ["MultiGraph", "MultiDiGraph"]
PARALLEL = [1, 2, 3, 8, 33]
# Straddle the 128-byte canonical stack buffer: the hoisted tuple owns heap
# Strings above it and the whole point is that they are built once.
KEY_LENGTHS = [1, 3, 130, 400]


def _pair(length):
    """Endpoints that sort BOTH ways, to exercise the undirected swap."""
    return ("m" * length, "z" * length), ("z" * length, "m" * length)


def _build(mod, class_name, u, v, par, keys=None):
    graph = getattr(mod, class_name)()
    for i in range(par):
        if keys is None:
            graph.add_edge(u, v, weight=i, tag=f"t{i}")
        else:
            graph.add_edge(u, v, key=keys[i], weight=i, tag=f"t{i}")
    return graph


@pytest.mark.parametrize("class_name", CLASSES)
@pytest.mark.parametrize("par", PARALLEL)
@pytest.mark.parametrize("length", KEY_LENGTHS)
def test_matches_networkx_exactly(class_name, par, length):
    for u, v in _pair(length):
        got = _build(fnx, class_name, u, v, par).get_edge_data(u, v)
        want = _build(nx, class_name, u, v, par).get_edge_data(u, v)
        assert list(got.keys()) == list(want.keys()), (
            f"key ORDER diverged for {class_name} par={par} len={length}"
        )
        assert {k: dict(d) for k, d in got.items()} == {
            k: dict(d) for k, d in want.items()
        }


@pytest.mark.parametrize("class_name", CLASSES)
@pytest.mark.parametrize("par", PARALLEL)
def test_key_to_attr_pairing(class_name, par):
    """Each key must map to ITS OWN attrs, not a neighbour's.

    A reused tuple that lagged or led by one iteration still produces a dict of
    the right size with the right key set and the right attr dicts — only the
    PAIRING is wrong. `weight=i` is written to match the i-th key so a shift of
    any distance shows up here.
    """
    u, v = "u" * 130, "v" * 130
    data = _build(fnx, class_name, u, v, par).get_edge_data(u, v)
    for key, attrs in data.items():
        assert attrs["weight"] == key, (
            f"key {key!r} carried weight {attrs['weight']!r} — the keydict "
            f"paired a key with ANOTHER parallel edge's attributes"
        )
        assert attrs["tag"] == f"t{key}"


@pytest.mark.parametrize("class_name", CLASSES)
def test_custom_public_keys_survive(class_name):
    """The `edge_py_keys` mirror is looked up BY THE WHOLE TUPLE.

    Custom (non-auto) public keys are served from that mirror, so this is the
    consumer most sensitive to a mis-sequenced reused tuple. Mixed types on
    purpose: str, int and float public keys all coexist.
    """
    u, v = "n" * 130, "q" * 130
    keys = ["alpha", 7, 2.5, "beta", 11]
    got = _build(fnx, class_name, u, v, len(keys), keys=keys).get_edge_data(u, v)
    want = _build(nx, class_name, u, v, len(keys), keys=keys).get_edge_data(u, v)

    assert list(got.keys()) == list(want.keys())
    for key in want:
        assert dict(got[key]) == dict(want[key]), (
            f"custom public key {key!r} resolved to the wrong attribute dict"
        )


@pytest.mark.parametrize("class_name", CLASSES)
def test_mixed_custom_and_auto_keys_in_one_graph(class_name):
    """The `edge_py_keys.is_empty()` guard is GLOBAL, the keys are per-edge.

    br-r37-c1-ptiz2 skips the public-key lookup entirely when no edge in the
    graph has an explicit key, because probing an empty map still costs a full
    hash of both node keys. This is the case that distinguishes "empty map" from
    "this pair has no custom key": one pair carries explicit keys, so the map is
    NON-empty, while the pair under test uses networkx's auto keys and must
    still come back with plain integers.

    A guard keyed on the wrong emptiness — or one that short-circuited when the
    map merely lacks THIS pair — would return the auto pair's keys correctly here
    and only fail once some unrelated edge in the graph was given a key, which is
    exactly the shape that survives a narrow test.
    """
    auto_u, auto_v = "auto_u" * 20, "auto_v" * 20
    named_u, named_v = "named_u" * 20, "named_v" * 20

    graphs = {}
    for name, mod in (("fnx", fnx), ("nx", nx)):
        graph = getattr(mod, class_name)()
        for i in range(6):
            graph.add_edge(auto_u, auto_v, weight=i)
        for label in ("first", "second"):
            graph.add_edge(named_u, named_v, key=label, weight=label)
        graphs[name] = graph

    auto_got = graphs["fnx"].get_edge_data(auto_u, auto_v)
    auto_want = graphs["nx"].get_edge_data(auto_u, auto_v)
    assert list(auto_got.keys()) == list(auto_want.keys()) == [0, 1, 2, 3, 4, 5]
    assert all(isinstance(k, int) for k in auto_got), (
        "auto keys came back as something other than plain ints while another "
        "edge in the same graph carried explicit keys"
    )
    assert {k: dict(d) for k, d in auto_got.items()} == {
        k: dict(d) for k, d in auto_want.items()
    }

    named_got = graphs["fnx"].get_edge_data(named_u, named_v)
    named_want = graphs["nx"].get_edge_data(named_u, named_v)
    assert list(named_got.keys()) == list(named_want.keys()) == ["first", "second"]
    assert {k: dict(d) for k, d in named_got.items()} == {
        k: dict(d) for k, d in named_want.items()
    }


@pytest.mark.parametrize("class_name", CLASSES)
@pytest.mark.parametrize("par", [1, 4, 16])
def test_returned_dicts_are_live_and_shared(class_name, par):
    """The keydict must hand back the graph's LIVE attr dicts.

    The hoist changes how the lookaside is keyed, not what it stores, so every
    inner dict must remain the same object the other accessors serve and a write
    through one must be visible everywhere.
    """
    u, v = "a" * 130, "b" * 130
    graph = _build(fnx, class_name, u, v, par)
    data = graph.get_edge_data(u, v)
    for key in list(data):
        assert data[key] is graph[u][v][key], f"key {key} returned a copy"
        assert data[key] is graph.edges[u, v, key]
        data[key]["written"] = key
        assert graph[u][v][key]["written"] == key


@pytest.mark.parametrize("class_name", CLASSES)
@pytest.mark.parametrize(
    "tamper",
    [
        pytest.param(lambda keydict: keydict.__setitem__(9999, {"phantom": True}), id="insert"),
        pytest.param(lambda keydict: keydict.__delitem__(3), id="delete"),
    ],
)
def test_tampering_with_the_returned_keydict_self_heals(class_name, tamper):
    """br-r37-c1-f3i50: the cache is now handed out LIVE, and heals on tamper.

    This test previously required a COPY on every read. That was the safe way to
    stop a caller's mutation corrupting the cache, but it cost O(parallel edges)
    per read and diverged from networkx, which returns `self._adj[u][v]` itself
    so repeated reads are the same object.

    The copy is gone. What protects the cache now is an entry-count guard: a
    caller that inserts or deletes changes the count, the next read sees the
    mismatch and REBUILDS from the graph rather than copying the tampered dict.
    So a phantom key survives exactly until the next read, and the mapping,
    `G.edges` and `number_of_edges` never disagree with each other.

    The undirected class has the live path; the directed one is another pane's
    work in progress (its `edge_keydict_by_index`), so only self-consistency is
    asserted for both and identity is asserted where it is implemented.
    """
    u, v = "u" * 130, "v" * 130
    graph = _build(fnx, class_name, u, v, 8)

    first = graph.get_edge_data(u, v)
    tamper(first)

    second = graph.get_edge_data(u, v)
    assert 9999 not in second, (
        "the phantom key survived a second read — the count guard did not "
        "rebuild, so the cache stayed corrupted"
    )
    assert list(second.keys()) == list(range(8))
    assert (u, v, 9999) not in graph.edges(keys=True)
    assert graph.number_of_edges() == 8


def test_undirected_repeated_reads_return_the_same_object():
    """br-r37-c1-f3i50: identity parity with networkx, on the class that has it.

    networkx returns its own keydict, so `g.get_edge_data(u,v) is
    g.get_edge_data(u,v)`. Dropping the per-read copy makes that true for
    MultiGraph. Asserted against live networkx so it cannot drift.
    """
    u, v = "u" * 130, "v" * 130
    reference = _build(nx, "MultiGraph", u, v, 4)
    assert reference.get_edge_data(u, v) is reference.get_edge_data(u, v)

    graph = _build(fnx, "MultiGraph", u, v, 4)
    assert graph.get_edge_data(u, v) is graph.get_edge_data(u, v)


@pytest.mark.parametrize("class_name", CLASSES)
@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(lambda g, u, v: g.add_edge(u, v, weight="new"), id="add_parallel"),
        pytest.param(lambda g, u, v: g.remove_edge(u, v), id="remove_one"),
        pytest.param(lambda g, u, v: g.add_edge(u, "fresh"), id="add_other_edge"),
        pytest.param(lambda g, u, v: g.add_node("lonely"), id="add_node"),
        pytest.param(lambda g, u, v: g.remove_node("bulk0"), id="remove_other_node"),
        pytest.param(lambda g, u, v: g.clear(), id="clear"),
    ],
)
def test_every_mutation_invalidates_the_cached_keydict(class_name, mutate):
    """A warm keydict must not survive ANY structural change.

    The cache is stamped with `(nodes_seq, edges_seq)`, so this asserts the
    stamps actually advance for each mutation shape rather than trusting that
    they do. `add_other_edge` and `remove_other_node` touch a DIFFERENT pair on
    purpose: the generation is global, so an unrelated mutation must drop this
    pair's entry too, and a cache that only invalidated on same-pair edits would
    pass every same-pair test and fail these.
    """
    u, v = "u" * 130, "v" * 130
    graph = _build(fnx, class_name, u, v, 4)
    graph.add_node("bulk0")

    warm = graph.get_edge_data(u, v)
    assert list(warm.keys()) == [0, 1, 2, 3]

    mutate(graph, u, v)

    after = graph.get_edge_data(u, v)
    # Built through the SAME helper as the fnx graph — an inline reconstruction
    # here silently dropped the `tag` attribute and made all five mutation cases
    # fail on a difference the lever had nothing to do with.
    reference = _build(nx, class_name, u, v, 4)
    reference.add_node("bulk0")
    mutate(reference, u, v)
    expected = reference.get_edge_data(u, v)

    if expected is None:
        assert after is None
    else:
        assert list(after.keys()) == list(expected.keys())
        assert {k: dict(d) for k, d in after.items()} == {
            k: dict(d) for k, d in expected.items()
        }


@pytest.mark.parametrize("class_name", CLASSES)
def test_cached_keydict_reflects_inner_attr_mutation(class_name):
    """Copying the mapping must NOT copy the attribute dicts.

    The values are the graph's live attr dicts, so a write through `G[u][v][k]`
    has to be visible in a keydict served from the cache. A deep copy — or a
    cache that snapshotted values — would break this while passing every
    key-set assertion.
    """
    u, v = "u" * 130, "v" * 130
    graph = _build(fnx, class_name, u, v, 4)
    graph.get_edge_data(u, v)  # warm the cache

    graph[u][v][2]["weight"] = "rewritten"
    assert graph.get_edge_data(u, v)[2]["weight"] == "rewritten"
    assert graph.get_edge_data(u, v)[2] is graph[u][v][2]


@pytest.mark.parametrize("class_name", CLASSES)
def test_absent_pair_returns_default(class_name):
    graph = _build(fnx, class_name, "x" * 130, "y" * 130, 3)
    assert graph.get_edge_data("x" * 130, "nope") is None
    assert graph.get_edge_data("nope", "x" * 130, default={}) == {}


@pytest.mark.parametrize("class_name", CLASSES)
def test_repeated_calls_agree(class_name):
    """Warm and cold calls must agree — the miss path clones the tuple, the hit
    path does not, so the two branches are separately exercised here."""
    u, v = "r" * 200, "s" * 200
    graph = _build(fnx, class_name, u, v, 12)
    first = {k: dict(d) for k, d in graph.get_edge_data(u, v).items()}
    second = {k: dict(d) for k, d in graph.get_edge_data(u, v).items()}
    assert first == second


def test_directed_orientation_is_not_sorted():
    """MultiDiGraph must NOT sort endpoints — u->v and v->u are distinct.

    The undirected `edge_key` sorts; the directed one does not. Hoisting the
    tuple out of the loop must preserve that difference.
    """
    u, v = "z" * 130, "a" * 130  # deliberately reverse-sorted
    graph = fnx.MultiDiGraph()
    graph.add_edge(u, v, weight="forward")
    graph.add_edge(v, u, weight="backward")
    assert graph.get_edge_data(u, v)[0]["weight"] == "forward"
    assert graph.get_edge_data(v, u)[0]["weight"] == "backward"


def test_directed_keydict_cache_does_not_confuse_orientations():
    """br-r37-c1-ptiz2: the DIRECTED cache must not sort its endpoints.

    `PyMultiGraph::edge_key` sorts (u, v) because the graph is undirected;
    `PyMultiDiGraph::edge_key` must not, because u->v and v->u are different
    edges. The directed keydict cache is keyed the same way, so a mirror that
    copied the undirected sorting would serve u->v's mapping for a v->u lookup —
    and only when the endpoints happen to sort the wrong way round, which a test
    using alphabetically ordered names would never reach.

    The names here are deliberately reverse-sorted, and BOTH directions are
    warmed before either is re-read, so a shared cache entry shows up as one
    direction returning the other's keys.
    """
    u, v = "z" * 130, "a" * 130  # u > v, so a sorting cache would swap them
    graph = fnx.MultiDiGraph()
    for i in range(4):
        graph.add_edge(u, v, weight=f"fwd{i}")
    for i in range(2):
        graph.add_edge(v, u, weight=f"rev{i}")

    forward = graph.get_edge_data(u, v)
    backward = graph.get_edge_data(v, u)
    # Re-read after both are warm — a shared entry surfaces on the second pass.
    forward_again = graph.get_edge_data(u, v)
    backward_again = graph.get_edge_data(v, u)

    assert list(forward) == list(forward_again) == [0, 1, 2, 3]
    assert list(backward) == list(backward_again) == [0, 1]
    assert [d["weight"] for d in forward_again.values()] == [
        "fwd0",
        "fwd1",
        "fwd2",
        "fwd3",
    ]
    assert [d["weight"] for d in backward_again.values()] == ["rev0", "rev1"]

    reference = nx.MultiDiGraph()
    for i in range(4):
        reference.add_edge(u, v, weight=f"fwd{i}")
    for i in range(2):
        reference.add_edge(v, u, weight=f"rev{i}")
    for a, b in ((u, v), (v, u)):
        assert {k: dict(d) for k, d in graph.get_edge_data(a, b).items()} == {
            k: dict(d) for k, d in reference.get_edge_data(a, b).items()
        }


# --- br-r37-c1-f3i50: the identity-int fast path -------------------------


def test_int_keys_match_networkx_and_are_live():
    """Int node keys take the index fast path and keep the live contract."""
    graph, reference = fnx.MultiGraph(), nx.MultiGraph()
    for g in (graph, reference):
        for i in range(8):
            g.add_edge(1, 2, weight=i)
    got, want = graph.get_edge_data(1, 2), reference.get_edge_data(1, 2)
    assert list(got.keys()) == list(want.keys())
    assert {k: dict(d) for k, d in got.items()} == {k: dict(d) for k, d in want.items()}
    # identity parity, the property the live return exists for
    assert graph.get_edge_data(1, 2) is graph.get_edge_data(1, 2)


def test_int_fast_path_degrades_after_node_removal_rather_than_lying():
    """THE safety case for the int arm.

    The fast path trusts an int only when the node with that NAME sits at that
    exact POSITION (`node_index_matches_int`). Removing a node compacts
    positions, so no surviving name equals its position any more and the arm
    stops firing — the slow path answers instead.

    A version that resolved the int to a position WITHOUT that check, or that
    used the slot space, would keep firing and return a different node's edges.
    So this asserts the answers stay correct across a removal that shifts every
    position, against live networkx.
    """
    graph, reference = fnx.MultiGraph(), nx.MultiGraph()
    for g in (graph, reference):
        for name in (0, 1, 2, 3):
            g.add_node(name)
        g.add_edge(2, 3, weight="two-three")
        g.add_edge(1, 2, weight="one-two")

    assert graph.get_edge_data(2, 3)[0]["weight"] == "two-three"
    graph.remove_node(0)
    reference.remove_node(0)

    for a, b in ((2, 3), (1, 2)):
        assert {k: dict(d) for k, d in graph.get_edge_data(a, b).items()} == {
            k: dict(d) for k, d in reference.get_edge_data(a, b).items()
        }, f"edge {a}-{b} diverged after the removal shifted every position"
    assert graph.get_edge_data(1, 3) is None
    assert graph.number_of_edges() == reference.number_of_edges()


def test_bool_keys_are_not_treated_as_int_positions():
    """`True`/`False` are `int` subclasses and would alias positions 1 and 0.

    The gate uses `is_exact_instance_of`, which excludes `bool`. If it ever
    relaxed to `isinstance`, `G.get_edge_data(True, False)` would answer with
    the edges of nodes 1 and 0.
    """
    graph, reference = fnx.MultiGraph(), nx.MultiGraph()
    for g in (graph, reference):
        g.add_edge(0, 1, weight="ints")
    assert graph.get_edge_data(True, False) == reference.get_edge_data(True, False)
    assert graph.get_edge_data(0, 1)[0]["weight"] == "ints"


def test_non_identity_ints_take_the_slow_path_correctly():
    """An int that does NOT sit at its own position must still answer right."""
    graph, reference = fnx.MultiGraph(), nx.MultiGraph()
    for g in (graph, reference):
        g.add_node("filler")
        g.add_edge(7, 9, weight="seven-nine")
    assert {k: dict(d) for k, d in graph.get_edge_data(7, 9).items()} == {
        k: dict(d) for k, d in reference.get_edge_data(7, 9).items()
    }
    assert graph.get_edge_data(0, 1) is None
