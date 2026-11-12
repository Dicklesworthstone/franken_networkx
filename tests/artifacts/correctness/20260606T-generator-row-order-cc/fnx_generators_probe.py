"""Classic-generator parity: nodes/edges/rows/attrs/graph-name vs nx."""
import networkx as nx
import franken_networkx as fnx


def rr(g):
    out = {
        "nodes": [(repr(n), dict(g.nodes[n])) for n in g],
        "adj": {repr(n): [repr(x) for x in g[n]] for n in g},
        "graph": dict(g.graph),
        "directed": g.is_directed(),
        "multi": g.is_multigraph(),
    }
    if g.is_directed():
        out["pred"] = {repr(n): [repr(x) for x in g.pred[n]] for n in g}
    return repr(out)


CASES = [
    ("barbell(5,3)", lambda m: m.barbell_graph(5, 3)),
    ("lollipop(5,3)", lambda m: m.lollipop_graph(5, 3)),
    ("circular_ladder(6)", lambda m: m.circular_ladder_graph(6)),
    ("ladder(6)", lambda m: m.ladder_graph(6)),
    ("wheel(7)", lambda m: m.wheel_graph(7)),
    ("star(8)", lambda m: m.star_graph(8)),
    ("turan(8,3)", lambda m: m.turan_graph(8, 3)),
    ("complete_multipartite(2,3,2)", lambda m: m.complete_multipartite_graph(2, 3, 2)),
    ("caveman(3,4)", lambda m: m.caveman_graph(3, 4)),
    ("connected_caveman(3,4)", lambda m: m.connected_caveman_graph(3, 4)),
    ("dorogovtsev(2)", lambda m: m.dorogovtsev_goltsev_mendes_graph(2)),
    ("full_rary_tree(3,13)", lambda m: m.full_rary_tree(3, 13)),
    ("binomial_tree(4)", lambda m: m.binomial_tree(4)),
    ("balanced_tree(2,3)", lambda m: m.balanced_tree(2, 3)),
    ("path(0)", lambda m: m.path_graph(0)),
    ("null", lambda m: m.null_graph()),
    ("trivial", lambda m: m.trivial_graph()),
    ("tadpole(4,3)", lambda m: m.tadpole_graph(4, 3)),
    ("complete(5,DiGraph)", lambda m: m.complete_graph(5, create_using=m.DiGraph)),
    ("cycle(5,DiGraph)", lambda m: m.cycle_graph(5, create_using=m.DiGraph)),
    ("path iterable nodes", lambda m: m.path_graph(['a', 'b', 'c'])),
    ("star iterable", lambda m: m.star_graph(['c', 1, 2])),
    ("hypercube(3)", lambda m: m.hypercube_graph(3)),
    ("triangular_lattice(2,3)", lambda m: m.triangular_lattice_graph(2, 3)),
    ("hexagonal_lattice(2,2)", lambda m: m.hexagonal_lattice_graph(2, 2)),
    ("sudoku(2)", lambda m: m.sudoku_graph(2)),
    ("chvatal", lambda m: m.chvatal_graph()),
    ("petersen", lambda m: m.petersen_graph()),
    ("mycielski(4)", lambda m: m.mycielski_graph(4)),
]
for name, fn in CASES:
    try:
        a = rr(fn(fnx))
    except Exception as e:
        a = ("ERR", type(e).__name__, str(e)[:60])
    try:
        b = rr(fn(nx))
    except Exception as e:
        b = ("ERR", type(e).__name__, str(e)[:60])
    if a != b:
        print(f"DIVERGES {name}:")
        if isinstance(a, tuple) or isinstance(b, tuple):
            print(f"  fx={str(a)[:110]}\n  nx={str(b)[:110]}")
        else:
            # find first difference
            for i in range(0, min(len(a), len(b))):
                if a[i] != b[i]:
                    print(f"  first diff @{i}: fx=...{a[max(0,i-30):i+70]}...")
                    print(f"               nx=...{b[max(0,i-30):i+70]}...")
                    break
print("generators done")
