"""br-r37-c1-dnv8g parity proof: grid_2d_graph native kernel vs nx."""
import hashlib
import networkx as nx
import franken_networkx as fnx

fails, lines = [], []


def canon(g):
    return (
        [(repr(n), dict(d)) for n, d in g.nodes(data=True)],
        [(repr(u), repr(v), dict(d)) for u, v, d in g.edges(data=True)],
        {repr(n): [repr(x) for x in g.adj[n]] for n in g},
        repr(dict(g.graph)),
    )


def check(tag, *args, **kw):
    cn = cf = en = ef = None
    try:
        cn = canon(nx.grid_2d_graph(*args, **kw))
    except Exception as e:
        en = (type(e).__name__, str(e))
    try:
        cf = canon(fnx.grid_2d_graph(*args, **kw))
    except Exception as e:
        ef = (type(e).__name__, str(e))
    lines.append(f"{tag}|{cn}|{en}")
    if cn != cf or en != ef:
        fails.append(tag)
        print(f"FAIL {tag}: en={en} ef={ef}")
        if cn and cf:
            for a, b, name in zip(cn, cf, ("nodes", "edges", "adj", "graph")):
                if a != b:
                    print(f"  {name} nx :", str(a)[:160])
                    print(f"  {name} fnx:", str(b)[:160])
                    break


# native-path shapes
for m, n in [(0, 0), (0, 5), (1, 1), (1, 6), (6, 1), (2, 2), (3, 4), (4, 3), (10, 10), (1, 2), (2, 1)]:
    check(f"plain-{m}x{n}", m, n)
# fallback shapes (must stay identical too)
check("periodic-true", 4, 5, periodic=True)
check("periodic-tuple", 4, 5, periodic=(True, False))
check("periodic-tuple2", 4, 5, periodic=(False, True))
check("periodic-list", 4, 5, periodic=[True, False])
check("create-digraph", 3, 3, create_using=None)
cn = canon(nx.grid_2d_graph(3, 4, create_using=nx.DiGraph))
cf = canon(fnx.grid_2d_graph(3, 4, create_using=fnx.DiGraph))
lines.append(f"digraph|{cn}")
if cn != cf:
    fails.append("create-digraph-cls")
    print("FAIL digraph", str(cn)[:120], str(cf)[:120])
# iterable rows/cols (non-int m)
check("iterable-rows", ["a", "b", "c"], 3)
check("bool-m", True, 3)  # bool must NOT take the int fast path blindly

# type checks: node keys are exact tuples of ints
g = fnx.grid_2d_graph(3, 3)
k = list(g)[0]
assert type(k) is tuple and all(type(x) is int for x in k), k
# mutation after native build
g.add_edge((0, 0), (2, 2), weight=5)
gn = nx.grid_2d_graph(3, 3)
gn.add_edge((0, 0), (2, 2), weight=5)
assert canon(g) == canon(gn), "post-build mutation diverged"
g.remove_node((1, 1))
gn.remove_node((1, 1))
assert canon(g) == canon(gn), "node removal diverged"
# copy + native algo sanity on the native-built graph
assert canon(g.copy()) == canon(gn.copy())
import networkx.algorithms.shortest_paths as _
assert fnx.shortest_path_length(fnx.grid_2d_graph(8, 8), (0, 0), (7, 7)) == \
       nx.shortest_path_length(nx.grid_2d_graph(8, 8), (0, 0), (7, 7))
assert fnx.number_of_selfloops(fnx.grid_2d_graph(5, 5)) == 0
# pickle round-trip: nodes/edges exact vs nx; adjacency row order after
# pickle is a PRE-EXISTING __setstate__ divergence (filed separately) —
# prove the native-built graph pickles IDENTICALLY to the Python-built
# fallback (build via create_using=fnx.Graph subclass-free fallback shape:
# use periodic-list falsy to force the fallback path).
import pickle
g_native = pickle.loads(pickle.dumps(fnx.grid_2d_graph(4, 4)))
# create_using=fnx.Graph forces the Python fallback path (gate requires None)
g_fallback = pickle.loads(pickle.dumps(fnx.grid_2d_graph(4, 4, create_using=fnx.Graph)))
assert canon(g_native)[:2] == canon(nx.grid_2d_graph(4, 4))[:2]
assert canon(g_native) == canon(g_fallback), "native pickle != fallback pickle"

sha = hashlib.sha256("\n".join(lines).encode()).hexdigest()
print(f"cases: {len(lines)}, failures: {len(fails)} {fails[:5]}")
print("GOLDEN_SHA256:", sha)
