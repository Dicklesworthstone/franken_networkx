import hashlib, json, sys, warnings
warnings.filterwarnings("ignore")
import networkx as nx
import franken_networkx as fnx

def graphs():
    cases = []
    # simple gnp + ws across seeds
    for seed in range(6):
        cases.append(("gnp80", nx.gnp_random_graph(80, 0.08, seed=seed), fnx.gnp_random_graph(80, 0.08, seed=seed)))
        cases.append(("ws120", nx.watts_strogatz_graph(120, 6, 0.2, seed=seed), fnx.watts_strogatz_graph(120, 6, 0.2, seed=seed)))
        cases.append(("ba60", nx.barabasi_albert_graph(60, 3, seed=seed), fnx.barabasi_albert_graph(60, 3, seed=seed)))
    # self-loops
    gn = nx.gnp_random_graph(40, 0.1, seed=1); gn.add_edge(0,0); gn.add_edge(5,5)
    gf = fnx.gnp_random_graph(40, 0.1, seed=1); gf.add_edge(0,0); gf.add_edge(5,5)
    cases.append(("selfloop", gn, gf))
    # tiny / empty / triangle
    cases.append(("tri", nx.Graph([(0,1),(1,2),(0,2),(2,3)]), fnx.Graph([(0,1),(1,2),(0,2),(2,3)])))
    cases.append(("empty", nx.Graph(), fnx.Graph()))
    # string-labeled
    sn = nx.Graph([("a","b"),("b","c"),("a","c"),("c","d"),("d","a")])
    sf = fnx.Graph([("a","b"),("b","c"),("a","c"),("c","d"),("d","a")])
    cases.append(("strlabels", sn, sf))
    return cases

def nbunches(g):
    nodes = list(g)
    out = [None]
    if nodes:
        out.append(nodes[0])
        out.append(nodes[: max(1, len(nodes)//3)])
    return out

def run():
    fnx_h = hashlib.sha256()
    nx_h = hashlib.sha256()
    mism = 0
    total = 0
    for name, gn, gf in graphs():
        for nb in nbunches(gn):
            total += 1
            rf = list(fnx.all_triangles(gf, nb))
            rn = list(nx.all_triangles(gn, nb))
            sf = json.dumps([list(map(str, t)) for t in rf])
            sn = json.dumps([list(map(str, t)) for t in rn])
            fnx_h.update(sf.encode()); fnx_h.update(b"|")
            nx_h.update(sn.encode()); nx_h.update(b"|")
            if rf != rn:
                mism += 1
                if mism <= 3:
                    print(f"MISMATCH {name} nb={nb}: fnx={rf[:5]} nx={rn[:5]}")
    print(f"cases={total} mismatches={mism}")
    print(f"fnx_sha={fnx_h.hexdigest()}")
    print(f"nx_sha ={nx_h.hexdigest()}")
    print(f"MATCH={fnx_h.hexdigest()==nx_h.hexdigest()}")

if __name__ == "__main__":
    run()
