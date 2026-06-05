#!/usr/bin/env python3
"""Differential parity: fnx Multi(Di)Graph.remove_node vs networkx.

Random MultiGraph / MultiDiGraph (with parallel edges, self-loops, edge attrs);
remove a random sequence of nodes from both fnx and nx; assert byte-exact
agreement on node order, edge order (u,v,key), edge attrs. Emit a golden
sha256 over the post-removal edge listings.
"""
import hashlib
import json
import random
import sys

import networkx as nx
import franken_networkx as fnx


def build_pair(seed, directed, n, m):
    rng = random.Random(seed)
    F = fnx.MultiDiGraph() if directed else fnx.MultiGraph()
    G = nx.MultiDiGraph() if directed else nx.MultiGraph()
    for i in range(n):
        F.add_node(str(i))
        G.add_node(str(i))
    for _ in range(m):
        u = str(rng.randrange(n))
        v = str(rng.randrange(n))
        if rng.random() < 0.15:  # bias for self-loops
            v = u
        attrs = {}
        if rng.random() < 0.5:
            attrs["w"] = rng.randint(1, 100)
        if rng.random() < 0.3:
            attrs["t"] = rng.choice(["x", "y", "z"])
        F.add_edge(u, v, **attrs)
        G.add_edge(u, v, **attrs)
    return F, G


def edges_listing(g, directed):
    # nodes in iteration order
    nodes = list(g.nodes())
    out = [("NODES", nodes)]
    el = []
    for u, v, k, d in g.edges(keys=True, data=True):
        el.append([u, v, k, {kk: d[kk] for kk in sorted(d)}])
    out.append(("EDGES", el))
    return out


def canon(listing):
    return json.dumps(listing, sort_keys=False, separators=(",", ":"))


def main():
    sha = hashlib.sha256()
    total = 0
    mismatches = 0
    for case in range(60):
        directed = case % 2 == 1
        n = 8 + case % 12
        m = n * 3
        F, G = build_pair(1000 + case, directed, n, m)
        rng = random.Random(50000 + case)
        victims = [str(rng.randrange(n)) for _ in range(rng.randint(1, n // 2 + 1))]
        for node in victims:
            F.remove_node(node) if node in F else None
            G.remove_node(node) if node in G else None
        fl = edges_listing(F, directed)
        gl = edges_listing(G, directed)
        if fl != gl:
            mismatches += 1
            if mismatches <= 3:
                print(f"MISMATCH case={case} directed={directed}")
                print("  fnx:", canon(fl)[:400])
                print("  nx :", canon(gl)[:400])
        # golden over nx (== fnx) listing
        sha.update(canon(gl).encode())
        total += 1
        # also sanity: counts
        assert F.number_of_nodes() == G.number_of_nodes(), case
        assert F.number_of_edges() == G.number_of_edges(), case
    print(f"cases={total} mismatches={mismatches}")
    print(f"golden_sha256={sha.hexdigest()}")
    sys.exit(1 if mismatches else 0)


if __name__ == "__main__":
    main()
