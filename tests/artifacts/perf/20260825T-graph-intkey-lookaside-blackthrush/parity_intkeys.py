"""End-to-end parity for the int-key canonicalization path, against LIVE networkx.

The Rust unit test pins byte-identity between the borrowed and owned canonical
forms; this pins the thing that actually matters to a caller: that a node
reached by an int key resolves to the SAME node networkx resolves, across every
shape the new branch admits -- 0, negatives, i64 boundaries, bool (an int
subclass that must stay numerically equivalent), int subclasses, ints beyond
i64 (which still take the owned arbitrary-precision path), and the int/float
equivalence networkx gets for free from dict hashing.
"""
import sys

import networkx as nx
import franken_networkx as fnx
import franken_networkx._fnx as _fnx

print(f"loaded _fnx: {_fnx.__file__}")

failures = []


def check(name, got, want):
    if got != want:
        failures.append(f"{name}: fnx={got!r} nx={want!r}")


class MyInt(int):
    pass


BIG = 2 ** 63          # one past i64::MAX -> owned arbitrary-precision path
NEG_BIG = -(2 ** 63) - 1  # one past i64::MIN

KEYS = [
    0, 1, -1, 7, -7, 9, 10, -10, 99, -100, 12345, -12345,
    2 ** 62, -(2 ** 62), 2 ** 63 - 1, -(2 ** 63),
    BIG, NEG_BIG,
    True, False,
    MyInt(41), MyInt(-41),
]

for directed in (False, True):
    G = (nx.DiGraph if directed else nx.Graph)()
    F = (fnx.DiGraph if directed else fnx.Graph)()
    tag = "DiGraph" if directed else "Graph"

    for i in range(len(KEYS) - 1):
        u, v = KEYS[i], KEYS[i + 1]
        G.add_edge(u, v, weight=i)
        F.add_edge(u, v, weight=i)

    check(f"{tag} node count", F.number_of_nodes(), G.number_of_nodes())
    check(f"{tag} edge count", F.number_of_edges(), G.number_of_edges())
    check(f"{tag} node set", sorted(map(repr, F.nodes)), sorted(map(repr, G.nodes)))

    for k in KEYS:
        check(f"{tag} {k!r} in G", k in F, k in G)
        check(f"{tag} has_node({k!r})", F.has_node(k), G.has_node(k))
        if k in G:
            check(f"{tag} neighbors({k!r})",
                  sorted(map(repr, F.neighbors(k))), sorted(map(repr, G.neighbors(k))))
            check(f"{tag} degree({k!r})", F.degree(k), G.degree(k))

    for i in range(len(KEYS) - 1):
        u, v = KEYS[i], KEYS[i + 1]
        check(f"{tag} edges[{u!r},{v!r}]", dict(F.edges[u, v]), dict(G.edges[u, v]))
        check(f"{tag} has_edge({u!r},{v!r})", F.has_edge(u, v), G.has_edge(u, v))
        check(f"{tag} get_edge_data", F.get_edge_data(u, v), G.get_edge_data(u, v))

    # An absent int must raise the SAME way in both.
    for probe in (10 ** 30, -(10 ** 30), 777777):
        try:
            G.edges[probe, probe]
            nx_exc = None
        except Exception as exc:  # noqa: BLE001
            nx_exc = (type(exc).__name__, exc.args)
        try:
            F.edges[probe, probe]
            fx_exc = None
        except Exception as exc:  # noqa: BLE001
            fx_exc = (type(exc).__name__, exc.args)
        check(f"{tag} absent edges[{probe!r}] raises", fx_exc, nx_exc)

# int/float/bool equivalence: 1, 1.0 and True are ONE dict key in Python, so
# they must be ONE node in both libraries.
G, F = nx.Graph(), fnx.Graph()
G.add_node(1)
F.add_node(1)
for alias in (1, 1.0, True):
    check(f"alias {alias!r} in G", alias in F, alias in G)
G.add_node(1.0)
F.add_node(1.0)
check("1 and 1.0 collapse", F.number_of_nodes(), G.number_of_nodes())

# str "5" and int 5 are DISTINCT nodes and must not alias.
G, F = nx.Graph(), fnx.Graph()
G.add_edge(5, 6)
F.add_edge(5, 6)
G.add_edge("5", "6")
F.add_edge("5", "6")
check("int/str keys stay distinct (nodes)", F.number_of_nodes(), G.number_of_nodes())
check("int/str keys stay distinct (edges)", F.number_of_edges(), G.number_of_edges())
check("edges[5,6] is not edges['5','6']",
      dict(F.edges[5, 6]) == dict(F.edges["5", "6"]),
      dict(G.edges[5, 6]) == dict(G.edges["5", "6"]))

if failures:
    print(f"\n{len(failures)} PARITY FAILURES:")
    for f in failures:
        print("  " + f)
    sys.exit(1)
print("\nint-key parity vs networkx: ALL CHECKS PASS")
