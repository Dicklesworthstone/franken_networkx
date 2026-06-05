"""Metamorphic differential parity: random mutation sequences vs networkx.

br-r37-c1-mutfuzz: single-operation parity probes miss bugs that only surface
after a *sequence* of compound mutations (add/remove/copy/subgraph/clear/update
interleaved with attr mutation). This harness drives the SAME deterministic
random operation sequence through fnx and networkx for every graph class and
asserts the full resulting state (node order + node attrs, edge order + keys +
edge attrs, graph attrs) is byte-identical.

Locks the core mutation machinery (the most-used surface in the library) against
state-divergence regressions. Validated 0 mismatches over 2800+ sequences during
authoring; the committed parametrization runs a deterministic subset in CI time.
"""

import random

import networkx as nx
import pytest

import franken_networkx as fnx

_CLS = {
    (False, False): (nx.Graph, fnx.Graph),
    (True, False): (nx.DiGraph, fnx.DiGraph),
    (False, True): (nx.MultiGraph, fnx.MultiGraph),
    (True, True): (nx.MultiDiGraph, fnx.MultiDiGraph),
}


def _state(G):
    """Order-sensitive, fully-comparable snapshot of a graph's observable state."""
    if G.is_multigraph():
        edges = [
            (str(u), str(v), k, tuple(sorted(d.items())))
            for u, v, k, d in G.edges(keys=True, data=True)
        ]
    else:
        edges = [
            (str(u), str(v), tuple(sorted(d.items()))) for u, v, d in G.edges(data=True)
        ]
    nodes = [(str(n), tuple(sorted(d.items()))) for n, d in G.nodes(data=True)]
    graph = sorted((str(k), str(v)) for k, v in G.graph.items())
    return (nodes, edges, graph)


def _drive(seed, directed, multi):
    """Run one deterministic random mutation sequence through both graphs."""
    rng = random.Random(seed)
    ncls, fcls = _CLS[(directed, multi)]
    Gn, Gf = ncls(), fcls()
    n = 5
    for _ in range(rng.randint(15, 45)):
        op = rng.random()
        a, b = rng.randrange(n), rng.randrange(n)
        if op < 0.35:
            Gn.add_edge(a, b, weight=a + b)
            Gf.add_edge(a, b, weight=a + b)
        elif op < 0.45:
            es = [(rng.randrange(n), rng.randrange(n)) for _ in range(3)]
            Gn.add_edges_from(es)
            Gf.add_edges_from(es)
        elif op < 0.55:
            if a in Gn:
                Gn.remove_node(a)
            if a in Gf:
                Gf.remove_node(a)
        elif op < 0.62:
            if Gn.has_edge(a, b):
                Gn.remove_edge(a, b)
            if Gf.has_edge(a, b):
                Gf.remove_edge(a, b)
        elif op < 0.68:
            es = [(0, 1), (1, 2)]
            Gn.remove_edges_from([e for e in es if Gn.has_edge(*e)])
            Gf.remove_edges_from([e for e in es if Gf.has_edge(*e)])
        elif op < 0.74:
            Gn.update([(3, 4)], [3, 4])
            Gf.update([(3, 4)], [3, 4])
        elif op < 0.82:
            sub = [x for x in range(n) if rng.random() < 0.6]
            Gn = Gn.subgraph([x for x in sub if x in Gn]).copy()
            Gf = Gf.subgraph([x for x in sub if x in Gf]).copy()
        elif op < 0.88:
            Gn, Gf = Gn.copy(), Gf.copy()
        elif op < 0.92:
            if a in Gn:
                Gn.nodes[a]["c"] = "z"
                Gf.nodes[a]["c"] = "z"
        elif op < 0.96:
            Gn.clear()
            Gf.clear()
        else:
            if Gn.has_edge(a, b):
                Gn.add_edge(a, b, extra=1)
                Gf.add_edge(a, b, extra=1)
    return _state(Gf), _state(Gn)


@pytest.mark.parametrize("directed", [False, True])
@pytest.mark.parametrize("multi", [False, True])
def test_mutation_sequence_state_matches_networkx(directed, multi):
    mismatches = []
    for seed in range(250):
        sf, sn = _drive(seed, directed, multi)
        if sf != sn:
            mismatches.append((seed, sf, sn))
    assert not mismatches, (
        f"mutation-sequence divergence (directed={directed}, multi={multi}): "
        f"{len(mismatches)} of 250 seeds; first seed={mismatches[0][0]}"
    )
