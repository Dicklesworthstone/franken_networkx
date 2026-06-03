import hashlib, json
import networkx as nx, franken_networkx as fnx

def canon_graph(G):
    nodes = [repr(n) for n in G.nodes()]
    # edges as canonical sorted (min,max) repr pairs, then sorted set (order-independent for undirected)
    edges = sorted("|".join(sorted([repr(u), repr(v)])) for u, v in G.edges())
    node_data = sorted(f"{repr(n)}:{sorted(G.nodes[n].items())}" for n in G.nodes())
    edge_data = sorted(f"{'|'.join(sorted([repr(u),repr(v)]))}:{sorted(G[u][v].items())}" for u,v in G.edges())
    payload = {
        "n": G.number_of_nodes(), "m": G.number_of_edges(),
        "directed": G.is_directed(), "multi": G.is_multigraph(),
        "node_order": nodes, "edges": edges,
        "node_data": node_data, "edge_data": edge_data,
    }
    return json.dumps(payload, sort_keys=True)

def dg(s): return hashlib.sha256(s.encode()).hexdigest()

cases = [
    ("complete_graph", lambda M: M.complete_graph(300)),
    ("complete_small", lambda M: M.complete_graph(7)),
    ("watts_strogatz", lambda M: M.watts_strogatz_graph(50, 6, 0.0, seed=42)),  # p=0 deterministic
    ("barabasi_albert", lambda M: M.barabasi_albert_graph(200, 4, seed=42)),
    ("path", lambda M: M.path_graph(100)),
    ("star", lambda M: M.star_graph(80)),
    ("cycle", lambda M: M.cycle_graph(120)),
    ("grid2d", lambda M: M.grid_2d_graph(15, 20)),
]
results, mism = {}, 0
for name, fn in cases:
    Gnx, Gfnx = fn(nx), fn(fn and fnx)
    cnx, cfnx = canon_graph(Gnx), canon_graph(Gfnx)
    # node ORDER must match nx too
    ok = (cnx == cfnx)
    results[name] = dg(cfnx)
    if not ok:
        mism += 1
        a, b = json.loads(cnx), json.loads(cfnx)
        for k in a:
            if a[k] != b[k]:
                print(f"MISMATCH {name} field={k}", end=" ")
                if isinstance(a[k], list):
                    print(f"(nx_len={len(a[k])} fnx_len={len(b[k])})")
                else:
                    print(f"nx={a[k]} fnx={b[k]}")
                break
print(f"mismatches={mism} cases={len(results)}")
print("GEN_GOLDEN", dg("|".join(f"{k}={results[k]}" for k in sorted(results))))

# Edge-iteration-order parity (order, not just set) + mutation persistence
import networkx as _nx, franken_networkx as _fnx
Gn = _nx.complete_graph(50); Gf = _fnx.complete_graph(50)
assert list(Gn.edges()) == list(Gf.edges()), "edge iteration order diverged!"
assert list(Gn.nodes()) == list(Gf.nodes()), "node order diverged!"
T = _fnx.complete_graph(30)
u, v = list(T.edges())[10]
T[u][v]['weight'] = 2.5
assert T[u][v]['weight'] == 2.5, "edge attr mutation did not persist!"
n5 = list(T.nodes())[5]; T.nodes[n5]['x'] = 1
assert T.nodes[n5]['x'] == 1, "node attr mutation did not persist!"
print("edge-order + mutation-persistence: OK")
