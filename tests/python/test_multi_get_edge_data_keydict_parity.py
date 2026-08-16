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
