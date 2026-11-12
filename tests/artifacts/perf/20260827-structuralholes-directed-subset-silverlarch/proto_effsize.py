"""Prototype + sweep for routing directed effective_size(nodes=...) natively.

br-r37-c1-qbj9u. networkx serves effective_size TWO different ways and they disagree on
directed graphs: nodes=None takes a scipy MATRIX path, nodes=<iterable> takes the
redundancy LOOP. Measured, they differ on 50/60 random digraphs (31 of those are nan
mismatches) and agree on 0/60 undirected. So fnx must match whichever path the CALL
selects - it cannot use one kernel for both.

fnx today: nodes=None -> _structural_holes_effective_size_matrix (mirrors nx's matrix
path, already 1.24x); nodes=<iterable> -> full delegation to networkx, which runs nx's own
loop at ~207 ms/call where the matrix path costs 1.6 ms marginal.

The native effective_size_directed_rust kernel matches nx's LOOP exactly once the
successors-only nan rule is applied on top - 0 mismatches in 1494 node values. The
undirected native path already applies that same rule in Python, so this needs no Rust
change.

This prototype is the candidate routing, swept against networkx before any source edit.
"""

import random

import networkx as nx

import franken_networkx as fnx
from franken_networkx._fnx import effective_size_directed_rust as _rust_eff_size_directed


def candidate_effective_size(G, nodes=None, weight=None):
    """What the patched wrapper would do. Only the new branch is exercised here."""
    has_selfloops = fnx.number_of_selfloops(G) > 0
    if (
        weight is None
        and G.is_directed()
        and not G.is_multigraph()
        and not has_selfloops
        and nodes is not None
    ):
        requested = list(nodes)
        for node in requested:
            if node not in G:
                raise KeyError(node)
        raw = _rust_eff_size_directed(G)
        keyed = {}
        for node in requested:
            # nx: all(u == v for u in G[v]) -- G[v] is SUCCESSORS on a DiGraph, so a node
            # with predecessors but no successors is nan. Same post-pass the undirected
            # native path already applies.
            if all(neighbor == node for neighbor in G[node]):
                keyed[node] = float("nan")
            else:
                keyed[node] = raw[node]
        return keyed
    return fnx.effective_size(G, nodes=nodes, weight=weight)


def same(a, b):
    if set(a) != set(b):
        return False
    for k in a:
        av, bv = a[k], b[k]
        an = isinstance(av, float) and av != av
        bn = isinstance(bv, float) and bv != bv
        if an != bn:
            return False
        if not an and abs(av - bv) > 1e-9:
            return False
    return True


def run():
    bad = []
    checked = 0
    for seed in range(300):
        r = random.Random(seed)
        n = r.randint(3, 12)
        fg, ng = fnx.DiGraph(), nx.DiGraph()
        fg.add_nodes_from(range(n))
        ng.add_nodes_from(range(n))
        for u in range(n):
            for v in range(n):
                if u != v and r.random() < r.choice([0.15, 0.3, 0.6]):
                    fg.add_edge(u, v)
                    ng.add_edge(u, v)
        subsets = [
            list(range(n)),
            [0],
            [],
            sorted(r.sample(range(n), k=max(1, n // 2))),
            list(reversed(range(n))),
        ]
        if seed % 3 == 0:
            # string node keys: the kernel returns the caller's key type, so this
            # exercises the lookup as well as the formula
            fg = fnx.DiGraph((f"n{u}", f"n{v}") for u, v in ng.edges())
            fg.add_nodes_from(f"n{i}" for i in range(n))
            ng = nx.DiGraph((f"n{u}", f"n{v}") for u, v in ng.edges())
            ng.add_nodes_from(f"n{i}" for i in range(n))
            subsets = [[f"n{i}" for i in s_] for s_ in subsets]
        for sub in subsets:
            checked += 1
            got = candidate_effective_size(fg, nodes=sub)
            exp = nx.effective_size(ng, nodes=sub)
            if not same(got, exp):
                bad.append((seed, sub, got, exp))
    # A node absent from G must raise the same way networkx does.
    fg = fnx.DiGraph([(0, 1), (1, 2)])
    ng = nx.DiGraph([(0, 1), (1, 2)])
    for graph, fn in ((fg, candidate_effective_size), (ng, nx.effective_size)):
        try:
            fn(graph, nodes=[0, 99])
            raise AssertionError("expected a raise for a missing node")
        except KeyError:
            pass
    print(f"candidate vs networkx: {len(bad)} divergences over {checked} (graph, subset) cases")
    for row in bad[:3]:
        print("  seed", row[0], "subset", row[1][:6], "got", list(row[2].items())[:3],
              "exp", list(row[3].items())[:3])
    print("missing-node KeyError parity: OK")


if __name__ == "__main__":
    run()
