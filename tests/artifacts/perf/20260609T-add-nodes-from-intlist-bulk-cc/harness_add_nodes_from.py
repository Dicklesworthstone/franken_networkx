import time, sys, hashlib, json
import networkx as nx
import franken_networkx as fnx

def nodes_repr(g):
    # display order + attrs, as strings for cross-impl compare
    return [(repr(n), sorted(g.nodes[n].items())) for n in g.nodes()]

def scenario(mod, build):
    g = mod.Graph()
    build(g)
    return g

SCN = {
    "plain_list": lambda g: g.add_nodes_from(list(range(50))),
    "with_dups": lambda g: g.add_nodes_from([3,1,4,1,5,9,2,6,5,3,5]),
    "preexisting": lambda g: (g.add_nodes_from([1,2,3]), g.add_nodes_from([2,3,4,5]))[-1],
    "tuple_input": lambda g: g.add_nodes_from((7,8,9)),
    "bool_mix": lambda g: g.add_nodes_from([True, 1, 0, False, 2, 3]),
    "negatives": lambda g: g.add_nodes_from([-3,-1,0,1,3,-3]),
    "attr_tuples": lambda g: g.add_nodes_from([(10,{"w":1}), (11,{"w":2}), 12]),
    "nonint_fallback": lambda g: g.add_nodes_from(["a", 1, (0,1), 2.5]),
    "grid_tuples": lambda g: g.add_nodes_from([(0,0),(0,1),(1,0)]),
    "bigint_overflow": lambda g: g.add_nodes_from([1, 2, 10**30, 3]),
    "empty": lambda g: g.add_nodes_from([]),
    "with_global_attr": lambda g: g.add_nodes_from([20,21,22], color="red"),
    "generator": lambda g: g.add_nodes_from(x for x in range(5)),
    "set_input": lambda g: g.add_nodes_from({100,101,102}),
}

def run(mod):
    out = {}
    for name, build in SCN.items():
        try:
            g = scenario(mod, build)
            out[name] = nodes_repr(g)
        except Exception as e:
            out[name] = f"EXC:{type(e).__name__}:{e}"
    return out

if __name__ == "__main__":
    fnx_res = run(fnx)
    nx_res = run(nx)
    mism = [k for k in SCN if fnx_res[k] != nx_res[k]]
    print("MISMATCHES:", mism)
    for k in mism:
        print(f"  {k}:\n    fnx={fnx_res[k]}\n    nx ={nx_res[k]}")
    sha = hashlib.sha256(json.dumps(fnx_res, sort_keys=True).encode()).hexdigest()
    print("fnx corpus sha256:", sha)
    print("PARITY_OK" if not mism else "PARITY_FAIL")
    # bench
    big = list(range(50000))
    def measure(fn,runs=7,warm=2):
        for _ in range(warm): fn()
        ts=[]
        for _ in range(runs):
            s=time.perf_counter(); fn(); ts.append((time.perf_counter()-s)*1000)
        ts.sort(); return ts[len(ts)//2]
    tf = measure(lambda:(lambda g:g.add_nodes_from(big))(fnx.Graph()))
    tn = measure(lambda:(lambda g:g.add_nodes_from(big))(nx.Graph()))
    print(f"BENCH add_nodes_from(list(range(50000))): fnx {tf:.2f}ms  nx {tn:.2f}ms  ratio {tf/tn:.2f}")
