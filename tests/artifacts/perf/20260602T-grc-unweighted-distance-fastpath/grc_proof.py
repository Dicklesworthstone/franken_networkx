#!/usr/bin/env python3
"""Isomorphism + golden-output proof for global_reaching_centrality fast path.

Compares fnx (post-change) against nx bit-exactly across a broad sweep, plus
corner cases, and emits a sha256 over all fnx outputs as a golden digest.
"""
import hashlib, json
import franken_networkx as fnx
import networkx as nx


def mk(G):
    fg = fnx.DiGraph() if G.is_directed() else fnx.Graph()
    fg.add_nodes_from(G.nodes()); fg.add_edges_from(G.edges())
    return fg


outputs = []
bit = diff = tot = 0

# Undirected BA sweep
for seed in range(40):
    for n, m in [(20, 2), (50, 3), (100, 3), (200, 4), (400, 3), (700, 4), (1200, 3)]:
        G = nx.barabasi_albert_graph(n, m, seed=seed)
        fg = mk(G)
        a = nx.global_reaching_centrality(G)
        b = fnx.global_reaching_centrality(fg)
        outputs.append(repr(b)); tot += 1
        if a == b: bit += 1
        else:
            diff += 1
            if diff <= 8: print(f"U DIFF n={n} m={m} seed={seed} d={a-b:.3e}")

# Directed GNP sweep
for seed in range(40):
    for n in [20, 50, 100, 200]:
        G = nx.gnp_random_graph(n, 0.08, seed=seed, directed=True)
        if G.size() == 0:
            continue
        fg = mk(G)
        try:
            a = nx.global_reaching_centrality(G)
        except Exception:
            continue
        b = fnx.global_reaching_centrality(fg)
        outputs.append(repr(b)); tot += 1
        if a == b: bit += 1
        else:
            diff += 1
            if diff <= 8: print(f"D DIFF n={n} seed={seed} d={a-b:.3e}")

# Weighted path must remain unchanged (uses original code path)
for seed in range(15):
    G = nx.barabasi_albert_graph(80, 3, seed=seed)
    for u, v in G.edges():
        G[u][v]["weight"] = 1.0 + ((u * 7 + v * 13) % 9)
    fg = mk(G)
    for u, v in G.edges():
        fg[u][v]["weight"] = G[u][v]["weight"]
    a = nx.global_reaching_centrality(G, weight="weight")
    b = fnx.global_reaching_centrality(fg, weight="weight")
    outputs.append(repr(b)); tot += 1
    if a == b: bit += 1
    else:
        diff += 1
        if diff <= 8: print(f"W DIFF seed={seed} d={a-b:.3e}")

# Disconnected + multigraph + trees + complete + cycle
extra = []
G = nx.Graph(); G.add_edges_from([(0, 1), (1, 2), (3, 4)]); extra.append((G, {}))
G = nx.MultiGraph(); G.add_edges_from([(0, 1), (0, 1), (1, 2), (2, 3)]); extra.append((G, {}))
extra.append((nx.path_graph(50), {}))
extra.append((nx.complete_graph(30), {}))
extra.append((nx.cycle_graph(40), {}))
extra.append((nx.balanced_tree(3, 4), {}))
extra.append((nx.karate_club_graph(), {}))
for G, kw in extra:
    fg = mk(G)
    a = nx.global_reaching_centrality(G, **kw)
    b = fnx.global_reaching_centrality(fg, **kw)
    outputs.append(repr(b)); tot += 1
    if a == b: bit += 1
    else:
        diff += 1
        print(f"X DIFF {G} d={a-b:.3e}")

# Error parity corner cases
def check_raises(make):
    Gn = make(nx); Gf = make(fnx)
    en = ef = None
    try: nx.global_reaching_centrality(Gn)
    except Exception as e: en = type(e).__name__
    try: fnx.global_reaching_centrality(Gf)
    except Exception as e: ef = type(e).__name__
    return en, ef

cases = {
    "selfloop1": lambda m: _se(m, [(0, 0)]),
    "noedge": lambda m: _sn(m, [0, 1, 2]),
}
def _se(m, edges):
    G = m.Graph(); G.add_edges_from(edges); return G
def _sn(m, nodes):
    G = m.Graph(); G.add_nodes_from(nodes); return G
for name, make in cases.items():
    en, ef = check_raises(make)
    ok = en == ef
    print(f"err {name}: nx={en} fnx={ef} {'OK' if ok else 'MISMATCH'}")
    tot += 1; bit += ok; diff += (not ok)

digest = hashlib.sha256("\n".join(outputs).encode()).hexdigest()
print(f"\ntotal={tot} bit_exact={bit} diff={diff}")
print(f"GOLDEN_SHA256={digest}")
print("RESULT:", "PASS" if diff == 0 else "FAIL")
