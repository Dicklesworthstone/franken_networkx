"""Randomised differential fuzz of the LANDED native predecessors/successors conversion.

br-r37-c1-predrow-8vytj demanded "the mutation-matrix treatment ... not a spot check",
because br-r37-c1-txkrn found FIVE wrong-answer manifestations from a row cache outliving a
cleared map: the stamp `restamp_neighbor_rows` writes on the next add_edge can LAUNDER a
stale row into looking fresh. A stale index twin is invisible until the indices move, so this
drives random mutation sequences that force index reuse (remove then re-add), interleaves
reads to WARM the twin before each mutation, and compares every node's row against live
networkx after every single step.
"""
import random
import networkx as nx
import franken_networkx as fnx

def outcome(fn):
    try:
        return ("ok", sorted(map(str, fn())))
    except Exception as exc:
        return ("raise", type(exc).__name__)

def compare(f, n, label, fails):
    for node in sorted(n.nodes(), key=str):
        for meth in ("predecessors", "successors"):
            a = outcome(lambda: getattr(f, meth)(node))
            b = outcome(lambda: getattr(n, meth)(node))
            if a != b:
                fails.append(f"{label}/{meth}({node!r}): fnx={a} nx={b}")
    # nodes networkx does not have must be refused identically
    for ghost in ("ghost", 12345):
        a = outcome(lambda: f.predecessors(ghost))
        b = outcome(lambda: n.predecessors(ghost))
        if a != b:
            fails.append(f"{label}/absent({ghost!r}): fnx={a} nx={b}")

fails = []
steps_run = 0
for cls in ("DiGraph", "MultiDiGraph"):
    for seed in range(6):
        rng = random.Random(seed)
        f, n = getattr(fnx, cls)(), getattr(nx, cls)()
        # mixed key types and a long key, per the landing commit's own test list
        pool = [0, 1, 2, 3, "a", "bb", "x" * 2000, 7, "ccc"]
        for g in (f, n):
            g.add_edges_from([(pool[0], pool[1]), (pool[1], pool[2]), (pool[2], pool[0])])
        for step in range(40):
            op = rng.choice(["add_edge", "add_edge", "remove_edge", "remove_node",
                             "add_node", "clear_edges"])
            u, v = rng.choice(pool), rng.choice(pool)
            for g in (f, n):
                try:
                    if op == "add_edge":
                        g.add_edge(u, v)
                    elif op == "add_node":
                        g.add_node(u)
                    elif op == "remove_edge":
                        if g.has_edge(u, v):
                            g.remove_edge(u, v)
                    elif op == "remove_node":
                        if u in g:
                            g.remove_node(u)
                    elif op == "clear_edges":
                        g.clear_edges()
                except Exception:
                    pass
            # WARM the index twin before the next mutation - a stale row only shows
            # after the map behind it has moved, so reading first is the whole point.
            for node in list(n.nodes())[:4]:
                outcome(lambda: f.predecessors(node))
            steps_run += 1
            compare(f, n, f"{cls}/seed{seed}/step{step}/{op}", fails)

print(f"{steps_run} mutation steps, {len(fails)} divergences")
for x in fails[:25]:
    print("  " + x)
