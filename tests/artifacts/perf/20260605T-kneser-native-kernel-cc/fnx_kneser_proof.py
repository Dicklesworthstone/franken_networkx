"""br-r37-c1-z2eaa parity proof: kneser_graph native kernel vs nx."""
import hashlib, time
import networkx as nx
import franken_networkx as fnx

fails, lines = [], []


def canon(g):
    return (
        [repr(n) for n in g.nodes()],
        [(repr(u), repr(v)) for u, v in g.edges()],
        {repr(n): [repr(x) for x in g.adj[n]] for n in g},
    )


def check(n, k):
    cn = cf = en = ef = None
    try:
        cn = canon(nx.kneser_graph(n, k))
    except Exception as e:
        en = (type(e).__name__, str(e))
    try:
        cf = canon(fnx.kneser_graph(n, k))
    except Exception as e:
        ef = (type(e).__name__, str(e))
    lines.append(f"{n},{k}|{cn}|{en}")
    if cn != cf or en != ef:
        fails.append((n, k))
        print(f"FAIL ({n},{k}): en={en} ef={ef}")
        if cn and cf:
            for a, b, name in zip(cn, cf, ("nodes", "edges", "adj")):
                if a != b:
                    for i, (x, y) in enumerate(zip(a, b) if isinstance(a, list) else zip(sorted(a.items()), sorted(b.items()))):
                        if x != y:
                            print(f"  {name}[{i}] nx={x} fnx={y}")
                            break
                    break


# exhaustive small matrix (covers 2k>n isolated case, k=1, k=n, petersen)
for n in range(1, 13):
    for k in range(1, n + 1):
        check(n, k)
# validation errors
check(0, 1)
check(5, 0)
check(5, 6)
check(-1, 2)
# bigger shapes (the benched gaps)
check(9, 3)
check(11, 4)
check(14, 2)
# type/membership pins
g = fnx.kneser_graph(5, 2)
kx = next(iter(g))
assert type(kx) is tuple and all(type(x) is int for x in kx)
assert (0, 1) in g and g.has_edge((0, 1), (2, 3))
assert fnx.is_isomorphic(g, fnx.petersen_graph())
# post-build mutation parity
gn, gf = nx.kneser_graph(5, 2), fnx.kneser_graph(5, 2)
for h in (gn, gf):
    h.add_edge((0, 1), (0, 2), w=1)
    h.remove_node((1, 2))
assert canon(gn) == canon(gf), "mutation diverged"
# pickle + copy
import pickle
assert canon(pickle.loads(pickle.dumps(fnx.kneser_graph(6, 2)))) == canon(nx.kneser_graph(6, 2))
assert canon(fnx.kneser_graph(6, 2).copy()) == canon(nx.kneser_graph(6, 2).copy())

sha = hashlib.sha256("\n".join(lines).encode()).hexdigest()
print(f"cases: {len(lines)}, failures: {len(fails)} {fails[:6]}")
print("GOLDEN_SHA256:", sha)

# bench
def t(f, *a):
    best = 1e9
    for _ in range(5):
        s = time.perf_counter(); f(*a); best = min(best, time.perf_counter() - s)
    return best
for (n, k) in [(9, 3), (11, 4), (14, 2)]:
    r = t(fnx.kneser_graph, n, k) / t(nx.kneser_graph, n, k)
    print(f"kneser({n},{k}): {r:.2f}x")
