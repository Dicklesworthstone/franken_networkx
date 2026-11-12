import franken_networkx as fnx
import networkx as nx
import random, time, hashlib

random.seed(12345)

def build(kind, n, p_or_m):
    if kind == "gnp":
        return nx.gnp_random_graph(n, p_or_m, seed=random.randint(0, 1<<30))
    if kind == "path":
        return nx.path_graph(n)
    if kind == "ba":
        return nx.barabasi_albert_graph(n, p_or_m, seed=random.randint(0,1<<30))
    if kind == "complete":
        return nx.complete_graph(n)
    if kind == "disc":  # two disconnected components
        g = nx.disjoint_union(nx.gnp_random_graph(n//2, 0.1), nx.gnp_random_graph(n//2, 0.1))
        return g

cases = []
for kind, n, p in [("gnp",200,0.02),("gnp",300,0.5),("path",500,0),("ba",400,3),
                   ("complete",100,0),("disc",300,0),("gnp",150,0.05),("gnp",500,0.9)]:
    cases.append((kind,n,p))

mismatches = 0
results = []
for kind,n,p in cases:
    G = build(kind,n,p)
    Gf = fnx.Graph(G)
    nodes = list(G.nodes())
    # sample many source/target pairs
    for _ in range(200):
        s = random.choice(nodes); t = random.choice(nodes)
        rx = nx.has_path(G, s, t)
        rf = fnx.has_path(Gf, s, t)
        results.append((kind,s,t,int(rf)))
        if rx != rf:
            mismatches += 1
            if mismatches <= 5:
                print(f"MISMATCH {kind} {s}->{t}: nx={rx} fnx={rf}")

print("total comparisons:", len(results), "mismatches:", mismatches)
sha = hashlib.sha256(repr(sorted(results)).encode()).hexdigest()
print("golden sha256:", sha)
