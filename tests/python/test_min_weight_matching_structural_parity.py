"""min_weight_matching goes through a STRUCTURAL nx copy, not a faithful conversion.

br-r37-c1-fs3bl. This function delegates to networkx and must keep doing so: nx's per-pair
tuple DIRECTION comes from the insertion order of the blossom algorithm's internal ``mate``
dict - ``matching_dict_to_set`` keeps whichever orientation it encounters first - and no
native kernel reproduces that. The Rust binding picked the same pairs but flipped
orientations (``(d, e)`` against ``(e, d)``), which is what got it reverted.

What did NOT need to be faithful is the CONVERSION. A matching depends only on structure
and the weight attribute, so copying every node and edge attribute across was pure
overhead: 68,318,179 Ir/call against networkx's own 58,893,510 (0.862x). A structural copy
carrying nodes in order and edges in order with just the weight brings it to 63,032,838
(0.934x, 1.08x self).

IT IS STILL A LOSS and this file does not pretend otherwise. The residue is networkx's
blossom implementation, which fnx runs either way; closing the row would mean reproducing
nx's mate-assignment order natively, which is the thing this bead already rejected once.

EDGE INSERTION ORDER IS LOAD-BEARING, which is why the structural copy preserves it: nx's
min_weight_matching builds an inverted graph with ``add_weighted_edges_from`` over
``G.edges(...)``, so the order edges arrive decides the blossom traversal and therefore
which orientation each pair ends up with. These cases compare EXACT tuples, not just the
pairing, because comparing unordered pairs would pass even if orientation regressed.
"""

import random

import networkx as nx
import pytest

import franken_networkx as fnx


def _outcome(fn):
    try:
        return ("ok", {tuple(map(str, e)) for e in fn()})
    except Exception as exc:  # noqa: BLE001 - the exception IS the observation
        return ("raise", type(exc).__name__, tuple(str(a) for a in exc.args))


def _build(module, n, seed, permute, attributed, int_weights):
    rng = random.Random(seed)
    graph = module.Graph()
    labels = list(range(n))
    if permute:
        rng.shuffle(labels)
    graph.add_nodes_from(labels)
    for i in range(n):
        for _ in range(rng.choice([0, 1, 3])):
            j = rng.randrange(n)
            if i != j:
                weight = rng.randint(1, 9) if int_weights else float(rng.randint(1, 9))
                graph.add_edge(labels[i], labels[j], weight=weight)
    if attributed:
        for node in graph.nodes():
            graph.nodes[node]["c"] = "x"
    return graph


@pytest.mark.parametrize("int_weights", [False, True])
@pytest.mark.parametrize("attributed", [False, True])
@pytest.mark.parametrize("permute", [False, True])
@pytest.mark.parametrize("seed", range(8))
def test_min_weight_matching_matches_networkx(seed, permute, attributed, int_weights):
    n = random.Random(seed).randint(0, 26)
    fg = _build(fnx, n, seed, permute, attributed, int_weights)
    ng = _build(nx, n, seed, permute, attributed, int_weights)
    assert _outcome(lambda: fnx.min_weight_matching(fg)) == _outcome(
        lambda: nx.min_weight_matching(ng)
    )


def test_unweighted_default_matches_networkx():
    """No weight attribute at all: nx defaults each edge to 1."""
    fg = fnx.Graph([(0, 1), (1, 2), (2, 3), (3, 0)])
    ng = nx.Graph([(0, 1), (1, 2), (2, 3), (3, 0)])
    assert _outcome(lambda: fnx.min_weight_matching(fg)) == _outcome(
        lambda: nx.min_weight_matching(ng)
    )


def test_empty_and_edgeless_match_networkx():
    for build in (lambda m: m.Graph(), lambda m: m.Graph([(0, 1)]).__class__()):
        assert _outcome(lambda: fnx.min_weight_matching(build(fnx))) == _outcome(
            lambda: nx.min_weight_matching(build(nx))
        )
    fg, ng = fnx.Graph(), nx.Graph()
    fg.add_nodes_from(range(4))
    ng.add_nodes_from(range(4))
    assert _outcome(lambda: fnx.min_weight_matching(fg)) == _outcome(
        lambda: nx.min_weight_matching(ng)
    )


def test_directed_and_multigraph_still_rejected():
    """br-r37-c1-gt95l: nx raises NetworkXNotImplemented for both; fnx must too."""
    for cls in ("DiGraph", "MultiGraph"):
        fg = getattr(fnx, cls)()
        ng = getattr(nx, cls)()
        fg.add_edge(0, 1)
        ng.add_edge(0, 1)
        assert _outcome(lambda: fnx.min_weight_matching(fg)) == _outcome(
            lambda: nx.min_weight_matching(ng)
        )
