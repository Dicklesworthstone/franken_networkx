"""Proof: grounded reduced-Laplacian sparse solve == pinv single-pair resistance."""
import numpy as np, networkx as nx, random
import scipy.sparse as sp
import scipy.sparse.linalg as spla


def pinv_rd(L, i, j):
    P = np.linalg.pinv(L, hermitian=True)
    return float(P[i, i] + P[j, j] - P[i, j] - P[j, i])


def grounded_rd(Ls, n, i, j):
    if i == j:
        return 0.0
    Lr = Ls[1:, :][:, 1:].tocsc()        # ground node 0
    v = np.zeros(n); v[i] = 1.0; v[j] = -1.0
    vr = v[1:]
    y = spla.spsolve(Lr, vr)
    return float(vr @ y)


maxerr = 0.0
for seed in range(60):
    rnd = random.Random(seed)
    n = rnd.randint(3, 40)
    G = nx.connected_watts_strogatz_graph(max(4, n), 4, 0.35, seed=seed)
    weighted = seed % 2 == 0
    if weighted:
        for u, v in G.edges():
            G[u][v]["weight"] = rnd.uniform(0.5, 5.0)
    wk = "weight" if weighted else None
    nodelist = list(G.nodes())
    L = nx.laplacian_matrix(G, nodelist=nodelist, weight=wk)
    Ld = L.toarray().astype(float)
    Ls = sp.csc_matrix(L, dtype=float)
    N = len(nodelist)
    for _ in range(6):
        i = rnd.randrange(N); j = rnd.randrange(N)
        a = pinv_rd(Ld, i, j)
        b = grounded_rd(Ls, N, i, j)
        maxerr = max(maxerr, abs(a - b))

print(f"max |grounded - pinv| = {maxerr:.3e}  {'PASS' if maxerr < 1e-6 else 'FAIL'}")
