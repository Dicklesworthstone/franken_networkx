"""condensation() full-contract parity vs networkx.

br-r37-c1-condscc: condensation has a subtle multi-part contract that the SCC
labeling makes easy to break: node labels must be 0..k in nx's
strongly_connected_components order, edge tuples must use those labels in nx's
G.edges() iteration order (first-occurrence deduped), each node carries a
``members`` SET of the original SCC nodes, and ``C.graph['mapping']`` maps every
original node to its SCC index. A wrong SCC numbering silently scrambles labels,
edges AND mapping together (the native _condensation_raw kernel diverged on
135/200 random graphs for exactly this reason).

This locks all four parts vs networkx across random directed graphs (incl
self-loops + the explicit ``scc=`` path), so any future native-kernel routing of
condensation stays byte-compatible.
"""

import random

import networkx as nx
import pytest

import franken_networkx as fnx


def _build(seed):
    rng = random.Random(seed)
    n = rng.randint(2, 14)
    base = nx.gnp_random_graph(n, rng.uniform(0.05, 0.45), seed=seed, directed=True)
    if rng.random() < 0.3:
        for x in list(base.nodes())[:2]:
            base.add_edge(x, x)
    Df, Dn = fnx.DiGraph(), nx.DiGraph()
    for G in (Df, Dn):
        G.add_nodes_from(base.nodes())
        G.add_edges_from(base.edges())
    return Df, Dn


def test_condensation_full_contract_matches_networkx():
    mismatches = []
    for seed in range(400):
        Df, Dn = _build(seed)
        cf, cn = fnx.condensation(Df), nx.condensation(Dn)
        nodes_ok = list(cf.nodes()) == list(cn.nodes())
        edges_ok = sorted(cf.edges()) == sorted(cn.edges())
        members_ok = all(
            cf.nodes[i]["members"] == cn.nodes[i]["members"] for i in cn.nodes()
        )
        mapping_ok = {str(k): v for k, v in cf.graph["mapping"].items()} == {
            str(k): v for k, v in cn.graph["mapping"].items()
        }
        if not (nodes_ok and edges_ok and members_ok and mapping_ok):
            mismatches.append((seed, nodes_ok, edges_ok, members_ok, mapping_ok))
    assert not mismatches, (
        f"condensation contract divergence: {len(mismatches)} of 400; "
        f"first (seed, nodes, edges, members, mapping)={mismatches[0]}"
    )


def test_condensation_edge_cases():
    # Empty graph -> empty condensation.
    assert list(fnx.condensation(fnx.DiGraph()).nodes()) == []
    # Single isolated node -> one SCC with that member, empty mapping target.
    g = fnx.DiGraph()
    g.add_node(7)
    c = fnx.condensation(g)
    assert list(c.nodes()) == [0]
    assert c.nodes[0]["members"] == {7}
    assert c.graph["mapping"] == {7: 0}
    # Explicit scc= path (caller supplies the partition).
    g2 = fnx.DiGraph()
    g2.add_edges_from([(0, 1), (1, 0), (1, 2)])
    c2 = fnx.condensation(g2, scc=[{0, 1}, {2}])
    assert sorted(c2.edges()) == [(0, 1)]
    # Undirected raises (directed-only).
    with pytest.raises(nx.NetworkXNotImplemented):
        fnx.condensation(fnx.Graph())
