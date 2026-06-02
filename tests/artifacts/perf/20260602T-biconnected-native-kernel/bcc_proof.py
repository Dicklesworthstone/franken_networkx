#!/usr/bin/env python3
"""Proof: native biconnected_components matches nx + golden sha256 (br-r37-c1-bccdisc)."""
import hashlib, random
import franken_networkx as fnx
import networkx as nx


def to_fnx(G):
    fg = fnx.Graph()
    fg.add_nodes_from(G.nodes())
    fg.add_edges_from(G.edges())
    return fg


def build(seed):
    r = random.Random(seed)
    typ = seed % 6
    if typ == 0:
        return nx.gnp_random_graph(r.randint(5, 45), r.uniform(0.04, 0.25), seed=seed)
    if typ == 1:
        return nx.barabasi_albert_graph(r.randint(6, 60), r.randint(1, 4), seed=seed)
    if typ == 2:
        return nx.random_labeled_tree(r.randint(3, 45), seed=seed)
    if typ == 3:
        G = nx.Graph(); base = 0
        for _ in range(r.randint(2, 10)):
            a, b, c = base, base + 1, base + 2
            G.add_edges_from([(a, b), (b, c), (c, a)]); base = c
        return G
    if typ == 4:
        return nx.connected_watts_strogatz_graph(r.randint(8, 45), 4, 0.3, seed=seed)
    return nx.lollipop_graph(r.randint(3, 8), r.randint(1, 6))


# bowtie regression: the exact graph the old native kernel got wrong
bowtie = nx.Graph(); bowtie.add_edges_from([(0, 1), (1, 2), (2, 0), (2, 3), (3, 4), (4, 2)])
fb = to_fnx(bowtie)
assert sorted(sorted(c) for c in fnx.biconnected_components(fb)) == [[0, 1, 2], [2, 3, 4]], "bowtie split"

outs = []
tot = bit = 0
for seed in range(500):
    G = build(seed)
    fg = to_fnx(G)
    Gn = nx.Graph(); Gn.add_nodes_from(fg.nodes()); Gn.add_edges_from(fg.edges())
    a = [sorted(c) for c in nx.biconnected_components(Gn)]
    b = [sorted(c) for c in fnx.biconnected_components(fg)]
    tot += 1; bit += (a == b)
    if a != b and tot - bit <= 5:
        print(f"FAIL seed={seed}: nx={a[:3]} fnx={b[:3]}")
    outs.append(str(b))

digest = hashlib.sha256("\n".join(outs).encode()).hexdigest()
print(f"parity tot={tot} match={bit}")
print(f"GOLDEN_SHA256={digest}")
print("RESULT:", "PASS" if bit == tot else "FAIL")
