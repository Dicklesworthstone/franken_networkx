"""Does the LANDED native DiGraph.predecessors preserve what the Python shim guaranteed?

br-r37-c1-predrow-8vytj named three risks for exactly this conversion:
  * br-r37-c1-ppiei - the ASSIGNED `_pred` mapping is the authority, not the node view;
  * br-r37-c1-lvlu7 - `adjacency[n]` hashes n, so an unhashable node must raise TypeError
    rather than report absence;
  * br-r37-c1-txkrn - FIVE wrong-answer manifestations from a row cache outliving a cleared
    map, which is why this wants a mutation MATRIX and not a spot check.
Compared against the live networkx in the same process.
"""
import networkx as nx
import franken_networkx as fnx

fails = []

def check(label, got, want):
    if got != want:
        fails.append(f"{label}: fnx={got!r} nx={want!r}")

def outcome(fn):
    try:
        return ("ok", sorted(map(str, fn())))
    except Exception as exc:
        return ("raise", type(exc).__name__)

# --- 1. mutation matrix: every step compared against networkx -------------------------
for cls in ("DiGraph", "MultiDiGraph"):
    f, n = getattr(fnx, cls)(), getattr(nx, cls)()
    steps = [
        ("init",        lambda g: [g.add_edge(i, (i + 1) % 6) for i in range(6)]),
        ("add_edge",    lambda g: g.add_edge(9, 3)),
        ("add_node",    lambda g: g.add_node(42)),
        ("remove_edge", lambda g: g.remove_edge(0, 1)),
        ("add_edge2",   lambda g: g.add_edge(7, 1)),
        ("remove_node", lambda g: g.remove_node(2)),
        ("readd",       lambda g: g.add_edge(2, 3)),
        ("clear",       lambda g: g.clear()),
        ("post_clear",  lambda g: g.add_edge(1, 2)),
    ]
    for name, step in steps:
        step(f); step(n)
        # read EVERY node's predecessors after EVERY mutation - a stale row cache shows up
        # as a correct answer that goes wrong only after the map behind it moved.
        for node in sorted(n.nodes(), key=str):
            check(f"{cls}/{name}/pred({node})",
                  outcome(lambda: f.predecessors(node)),
                  outcome(lambda: n.predecessors(node)))
            check(f"{cls}/{name}/succ({node})",
                  outcome(lambda: f.successors(node)),
                  outcome(lambda: n.successors(node)))

# --- 2. assigned private storage: the mapping is the authority (br-r37-c1-ppiei) ------
for cls in ("DiGraph", "MultiDiGraph"):
    f, n = getattr(fnx, cls)(), getattr(nx, cls)()
    for g in (f, n):
        g.add_edge(1, 2)
    row = {5: {}} if cls == "DiGraph" else {5: {0: {}}}
    f._pred = {2: row, 1: {}, 5: {}}
    n._pred = {2: row, 1: {}, 5: {}}
    check(f"{cls}/assigned_pred/pred(2)",
          outcome(lambda: f.predecessors(2)), outcome(lambda: n.predecessors(2)))
    # a node reachable ONLY through the assigned mapping
    check(f"{cls}/assigned_pred/pred(5)",
          outcome(lambda: f.predecessors(5)), outcome(lambda: n.predecessors(5)))

# --- 3. unhashable node must raise TypeError, not report absence (br-r37-c1-lvlu7) ----
for cls in ("DiGraph", "MultiDiGraph"):
    f, n = getattr(fnx, cls)(), getattr(nx, cls)()
    for g in (f, n):
        g.add_edge(1, 2)
    check(f"{cls}/unhashable",
          outcome(lambda: f.predecessors([1, 2])), outcome(lambda: n.predecessors([1, 2])))
    check(f"{cls}/missing",
          outcome(lambda: f.predecessors(999)), outcome(lambda: n.predecessors(999)))

print(f"{len(fails)} divergences")
for x in fails[:40]:
    print("  " + x)
