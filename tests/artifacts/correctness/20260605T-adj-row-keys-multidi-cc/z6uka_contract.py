"""Pinned nx contract probes: MultiDiGraph mixed-display row/cell objects."""
import networkx as nx
import franken_networkx as fnx

def edges_repr(g, **kw):
    return [tuple(repr(x) for x in t) for t in g.edges(**kw)]

def rows(g):
    out = {}
    for n in g:
        out[repr(n)] = [repr(x) for x in g.succ[n]] + ["|"] + [repr(x) for x in g.pred[n]]
    return out

checks = []
def chk(name, fn):
    gn, gf = nx.MultiDiGraph(), fnx.MultiDiGraph()
    fn(gn); fn(gf)
    ok = edges_repr(gn, keys=True) == edges_repr(gf, keys=True) and rows(gn) == rows(gf) \
         and [repr(n) for n in gn] == [repr(n) for n in gf]
    checks.append((name, ok))
    if not ok:
        print(f"FAIL {name}")
        print("  nx edges:", edges_repr(gn, keys=True)); print("  fnx edges:", edges_repr(gf, keys=True))
        print("  nx rows:", rows(gn)); print("  fnx rows:", rows(gf))

# base: succ gets v-obj, pred gets u-obj
chk("base", lambda g: (g.add_node(28), g.add_node(7.0), g.add_edge(7, 28.0)))
# parallel keys reuse the FIRST cell object (even other type)
chk("parallel-reuse", lambda g: (g.add_node(28), g.add_edge(7, 28.0), g.add_edge(7.0, 28)))
# self-loop: succ row keeps v-obj, pred row keeps u-obj (asymmetric)
chk("selfloop-asym", lambda g: (g.add_node(12.0), g.add_edge(12.0, 12)))
# removal of ONE key keeps the cell
def one_key(g):
    g.add_node(28); g.add_edge(7, 28.0); g.add_edge(7, 28); g.remove_edge(7, 28)
chk("remove-one-key-keeps-cell", one_key)
# removal of LAST key drops the cell; re-add = fresh objects
def last_key(g):
    g.add_node(28); g.add_edge(7, 28.0); g.remove_edge(7, 28); g.add_edge(7, 28)
chk("remove-last-key-fresh", last_key)
# remove_node purges
def rm_node(g):
    g.add_node(28); g.add_edge(7, 28.0); g.add_edge(28.0, 9); g.remove_node(28); g.add_node(28); g.add_edge(7, 28)
chk("remove-node-purge", rm_node)

def cmp_g(name, gn, gf):
    ok = edges_repr(gn, keys=True) == edges_repr(gf, keys=True) and rows(gn) == rows(gf) \
         and [repr(n) for n in gn] == [repr(n) for n in gf]
    checks.append((name, ok))
    if not ok:
        print(f"FAIL {name}")
        print("  nx edges:", edges_repr(gn, keys=True)); print("  fnx edges:", edges_repr(gf, keys=True))
        print("  nx rows:", rows(gn)); print("  fnx rows:", rows(gf))

def build(mod):
    g = mod.MultiDiGraph()
    g.add_node(28); g.add_node(5.0)
    g.add_edge(7, 28.0); g.add_edge(5, 7); g.add_edge(28.0, 5); g.add_edge(3, 3.0); g.add_edge(7, 28.0)
    return g

gn, gf = build(nx), build(fnx)
cmp_g("copy", gn.copy(), gf.copy())
cmp_g("copy-of-copy", gn.copy().copy(), gf.copy().copy())
cmp_g("reverse", gn.reverse(), gf.reverse())
cmp_g("reverse-reverse", gn.reverse().reverse(), gf.reverse().reverse())
cmp_g("subgraph-copy", gn.subgraph([7, 28, 5]).copy(), gf.subgraph([7, 28, 5]).copy())
import copy as _c
cmp_g("copy.copy", _c.copy(gn), _c.copy(gf))
cmp_g("deepcopy", _c.deepcopy(gn), _c.deepcopy(gf))

print("passed:", sum(1 for _, ok in checks if ok), "/", len(checks))
