"""G.edges[spec] behaviour, fnx vs live networkx (br-r37-c1-ef8rt)."""
import networkx as nx, franken_networkx as fnx

class Unhash(str):
    __hash__ = None

def outcome(fn):
    try:
        v = fn()
        return f"dict{sorted(v.items())}" if isinstance(v, dict) else f"{v}"
    except BaseException as e:
        return f"!{type(e).__name__}: {e}"

def probes(g):
    U = Unhash("n0")
    return {
        "present tuple": lambda: g.edges["n0", "n1"],
        "reversed tuple": lambda: g.edges["n1", "n0"],
        "absent u": lambda: g.edges["zz", "n1"],
        "absent v": lambda: g.edges["n0", "zz"],
        "3-tuple": lambda: g.edges["n0", "n1", 0],
        "1-tuple": lambda: g.edges[("n0",)],
        "list": lambda: g.edges[["n0", "n1"]],
        "2-char str": lambda: g.edges["ab"],
        "int": lambda: g.edges[5],
        "none": lambda: g.edges[None],
        "slice": lambda: g.edges[0:2],
        "unhash u": lambda: g.edges[U, "n1"],
        "absent u + unhash v": lambda: g.edges["zz", Unhash("n1")],
        "generator": lambda: g.edges[(c for c in ("n0", "n1"))],
    }

for cls in ["Graph"]:
    a = getattr(nx, cls)(); a.add_edge("n0", "n1", weight=3); a.add_edge("a", "b")
    b = getattr(fnx, cls)(); b.add_edge("n0", "n1", weight=3); b.add_edge("a", "b")
    print(f"=== {cls}")
    pa, pb = probes(a), probes(b)
    for label in pa:
        x, y = outcome(pa[label]), outcome(pb[label])
        print(f"  {label:22s} nx={x[:46]:48s} fnx={y[:46]:48s}{'' if x==y else ' <<< DIVERGES'}")
