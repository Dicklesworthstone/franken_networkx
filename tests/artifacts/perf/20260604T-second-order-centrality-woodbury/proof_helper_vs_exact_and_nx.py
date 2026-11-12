"""Validate the EXACT helper code (as it will be pasted into __init__.py)."""
import numpy as np
import networkx as nx
import random


def _second_order_fundamental_columns(transition, ones):
    n = transition.shape[0]
    try:
        from scipy.linalg import lu_factor, lu_solve

        A = np.eye(n) - transition
        A[:, 0] += transition[:, 0]
        piv = lu_factor(A)
        a = lu_solve(piv, ones)
        bp = lu_solve(piv, transition)
        matrix = np.empty((n, n))
        matrix[:, 0] = a
        a0 = a[0]
        bp0_col = bp[:, 0]
        bp_row0 = bp[0, :]
        bp00 = bp[0, 0]
        for j in range(1, n):
            bpj = bp[:, j]
            s = np.array([[1.0 + bp[j, j], -bp[j, 0]],
                          [bp_row0[j], 1.0 - bp00]])
            rhs = np.array([a[j], a0])
            c0, c1 = np.linalg.solve(s, rhs)
            matrix[:, j] = a - (bpj * c0 - bp0_col * c1)
        if not np.all(np.isfinite(matrix)):
            return None
        return matrix
    except Exception:
        return None


def exact(transition, ones):
    n = transition.shape[0]
    identity = np.identity(n)
    M = np.empty((n, n))
    for idx in range(n):
        r = transition.copy()
        r[:, idx] = 0
        M[:, idx] = np.linalg.solve(identity - r, ones)
    return M


def build_transition(G, weight):
    nodelist = list(G.nodes())
    n = len(nodelist)
    directed = nx.DiGraph(G)
    indeg = dict(directed.in_degree(weight=weight))
    mx = max(indeg.values())
    for node, deg in indeg.items():
        if deg < mx:
            directed.add_edge(node, node, weight=mx - deg)
    T = nx.to_numpy_array(directed, nodelist=nodelist)
    T /= T.sum(axis=1)[:, np.newaxis]
    return T, nodelist


def soc(M, nl):
    n = M.shape[0]
    return {nd: float(np.sqrt(2 * np.sum(M[:, j]) - n * (n + 1))) for j, nd in enumerate(nl)}


me = ms = mnx = 0.0
nfallback = 0
for seed in range(60):
    rnd = random.Random(seed * 7 + 1)
    n = rnd.randint(2, 45)
    G = nx.connected_watts_strogatz_graph(max(4, n), 4, 0.35, seed=seed)
    for u, v in G.edges():
        G[u][v]["weight"] = rnd.uniform(0.3, 6.0)
    for weight in ("weight",):  # weight=None mixes attr semantics; test weighted
        T, nl = build_transition(G, weight)
        ones = np.ones(T.shape[0])
        Mref = exact(T, ones)
        Mfast = _second_order_fundamental_columns(T, ones)
        if Mfast is None:
            nfallback += 1
            continue
        me = max(me, float(np.max(np.abs(Mref - Mfast))))
        s_fast = soc(Mfast, nl)
        s_ref = soc(Mref, nl)
        ms = max(ms, max(abs(s_fast[k] - s_ref[k]) for k in nl))
        s_nx = nx.second_order_centrality(G, weight=weight)
        mnx = max(mnx, max(abs(s_fast[k] - s_nx[k]) for k in nl))

print(f"max |M_fast - M_exact|  = {me:.3e}")
print(f"max |soc_fast - soc_ex| = {ms:.3e}")
print(f"max |soc_fast - soc_nx| = {mnx:.3e}")
print(f"fallbacks               = {nfallback}")
print("PASS" if me < 1e-7 and ms < 1e-7 and mnx < 1e-7 else "FAIL")
