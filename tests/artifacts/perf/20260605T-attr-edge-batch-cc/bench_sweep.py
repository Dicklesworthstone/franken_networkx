import time, os, random, tempfile
import networkx as nx
import franken_networkx as fnx

random.seed(42)

def build(mod, n=1500):
    g = mod.Graph()
    g.add_nodes_from(range(n))
    rnd = random.Random(42)
    for u in range(n):
        for v in range(u + 1, min(u + 8, n)):
            if rnd.random() < 0.5:
                g.add_edge(u, v, weight=rnd.random())
    return g

gn, gf = build(nx), build(fnx)
TMP = tempfile.mkdtemp(prefix="sweep2", dir="/data/tmp")

def timeit(fn):
    t = time.perf_counter(); fn(); return time.perf_counter() - t

def bench(label, fn_nx, fn_fnx, reps=9):
    bn = bf = 9e9
    fn_nx(); fn_fnx()
    for _ in range(reps):
        bn = min(bn, timeit(fn_nx)); bf = min(bf, timeit(fn_fnx))
    flag = " <<<" if bf/bn > 1.5 else ""
    print(f"{label:32s} nx={bn*1000:9.3f}ms fnx={bf*1000:9.3f}ms ratio={bf/bn:6.2f}x{flag}")

# readwrite residuals
nx.write_edgelist(gn, f"{TMP}/r.el")
bench("read_edgelist(data=True)", lambda: nx.read_edgelist(f"{TMP}/r.el"), lambda: fnx.read_edgelist(f"{TMP}/r.el"))
nx.write_edgelist(gn, f"{TMP}/rnd.el", data=False)
bench("read_edgelist(no data file)", lambda: nx.read_edgelist(f"{TMP}/rnd.el"), lambda: fnx.read_edgelist(f"{TMP}/rnd.el"))
bench("write_gml", lambda: nx.write_gml(gn, f"{TMP}/n.gml"), lambda: fnx.write_gml(gf, f"{TMP}/f.gml"))
bench("write_adjlist", lambda: nx.write_adjlist(gn, f"{TMP}/n.adj"), lambda: fnx.write_adjlist(gf, f"{TMP}/f.adj"))
nx.write_weighted_edgelist(gn, f"{TMP}/w.el")
bench("read_weighted_edgelist", lambda: nx.read_weighted_edgelist(f"{TMP}/w.el"), lambda: fnx.read_weighted_edgelist(f"{TMP}/w.el"))

# conversion
dol = nx.to_dict_of_lists(gn)
bench("from_dict_of_lists", lambda: nx.from_dict_of_lists(dol), lambda: fnx.from_dict_of_lists(dol))
dod = nx.to_dict_of_dicts(gn)
bench("from_dict_of_dicts", lambda: nx.from_dict_of_dicts(dod), lambda: fnx.from_dict_of_dicts(dod))
el = list(gn.edges())
bench("from_edgelist", lambda: nx.from_edgelist(el), lambda: fnx.from_edgelist(el))

# construction substrate
edges = list(gn.edges(data=True))
def cons_nx():
    g = nx.Graph(); g.add_edges_from(edges); return g
def cons_fnx():
    g = fnx.Graph(); g.add_edges_from(edges); return g
bench("add_edges_from(data)", cons_nx, cons_fnx)
edges_nd = list(gn.edges())
def cons2_nx():
    g = nx.Graph(); g.add_edges_from(edges_nd); return g
def cons2_fnx():
    g = fnx.Graph(); g.add_edges_from(edges_nd); return g
bench("add_edges_from(nodata)", cons2_nx, cons2_fnx)
bench("add_nodes_from(100k)", lambda: nx.Graph().add_nodes_from(range(100000)), lambda: fnx.Graph().add_nodes_from(range(100000)))

# generators
bench("gnp_random_graph(800,.02)", lambda: nx.gnp_random_graph(800, .02, seed=7), lambda: fnx.gnp_random_graph(800, .02, seed=7))
bench("barabasi_albert(2000,3)", lambda: nx.barabasi_albert_graph(2000, 3, seed=7), lambda: fnx.barabasi_albert_graph(2000, 3, seed=7))
bench("watts_strogatz(2000,6,.1)", lambda: nx.watts_strogatz_graph(2000, 6, .1, seed=7), lambda: fnx.watts_strogatz_graph(2000, 6, .1, seed=7))
bench("complete_graph(500)", lambda: nx.complete_graph(500), lambda: fnx.complete_graph(500))
bench("grid_2d_graph(60x60)", lambda: nx.grid_2d_graph(60, 60), lambda: fnx.grid_2d_graph(60, 60))

# operators
g2n, g2f = build(nx, 800), build(fnx, 800)
bench("compose", lambda: nx.compose(gn, g2n), lambda: fnx.compose(gf, g2f))
bench("union(relabeled)", lambda: nx.disjoint_union(gn, g2n), lambda: fnx.disjoint_union(gf, g2f))
bench("subgraph+copy 30%", lambda: gn.subgraph(range(0, 1500, 3)).copy(), lambda: gf.subgraph(range(0, 1500, 3)).copy())
bench("reverse_view->DiGraph", lambda: nx.DiGraph(gn), lambda: fnx.DiGraph(gf))
print("TMP:", TMP)
