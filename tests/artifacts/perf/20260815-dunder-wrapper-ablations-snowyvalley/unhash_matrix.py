"""Unhashable / custom-eq key behaviour, fnx vs live networkx (br-r37-c1-lvlu7)."""

import sys

import networkx as nx

import franken_networkx as fnx


class Unhash(str):
    __hash__ = None


class Ci(str):
    """Case-insensitive: equal and hash-equal to its lowercase form."""

    def __hash__(self):
        return hash(str(self).lower())

    def __eq__(self, other):
        return str(self).lower() == str(other).lower()

    def __ne__(self, other):
        return not self.__eq__(other)


def outcome(fn):
    try:
        return f"{fn()}"
    except BaseException as exc:  # noqa: BLE001 — the exception IS the contract
        return f"!{type(exc).__name__}"


def probes(lib, cls):
    g = getattr(lib, cls)()
    g.add_edge("n0", "n1")
    U, C = Unhash("n0"), Ci("N0")
    UV = Unhash("n1")
    return [
        ("(U,n1) in G.edges", lambda: (U, "n1") in g.edges),
        ("(n0,UV) in G.edges", lambda: ("n0", UV) in g.edges),
        ("(missing,UV) in G.edges", lambda: ("missing", UV) in g.edges),
        ("(U,missing) in G.edges", lambda: (U, "missing") in g.edges),
        ("U in G", lambda: U in g),
        ("G.has_node(U)", lambda: g.has_node(U)),
        ("U in G.nodes", lambda: U in g.nodes),
        ("G.has_edge(U,n1)", lambda: g.has_edge(U, "n1")),
        ("G.has_edge(n0,UV)", lambda: g.has_edge("n0", UV)),
        ("G.has_edge(missing,UV)", lambda: g.has_edge("missing", UV)),
        ("(C,n1) in G.edges", lambda: (C, "n1") in g.edges),
        ("C in G", lambda: C in g),
    ]


def main():
    for cls in ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"]:
        print(f"=== {cls}")
        for (label, a), (_, b) in zip(probes(nx, cls), probes(fnx, cls)):
            x, y = outcome(a), outcome(b)
            flag = "" if x == y else "   <<< DIVERGES"
            print(f"  {label:26s} nx={x:12s} fnx={y:12s}{flag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
