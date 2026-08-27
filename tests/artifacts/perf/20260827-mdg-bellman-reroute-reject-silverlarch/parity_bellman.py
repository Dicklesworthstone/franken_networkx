"""Does the raw native kernel match nx on a MultiDiGraph, everywhere the public
wrapper does? (br-r37-c1-mg7hw)

The public wrapper reaches the simple kernel via a per-call collapse that costs 75.3% of
the operation. Routing straight to _raw_bellman_ford_path_length is 1.24x cheaper, but the
collapse is not purely an optimization: its comment records that it replaced two O(|E|)
Python gate scans and "keeps negatives (valid for Bellman-Ford) and delegates only
NaN/inf/nonnumeric". So the reroute is a PARITY change first, and this is the matrix that
decides it.

Compares exception ARGS, not just types - a type-only sweep reports false green.
Three arms: networkx (the incumbent and the reference), fnx's public wrapper (which must
already match nx), and the raw kernel applied directly to the multigraph (the candidate).
"""

import math
import sys
import traceback

import networkx as nx

import franken_networkx as fnx

RAW = fnx._raw_bellman_ford_path_length


def build(mod, edges, nodes=()):
    g = mod.MultiDiGraph()
    for n in nodes:
        g.add_node(n)
    for e in edges:
        if len(e) == 3:
            u, v, w = e
            g.add_edge(u, v, weight=w)
        else:
            g.add_edge(*e)
    return g


def outcome(fn, mod, edges, src, dst, nodes=()):
    try:
        g = build(mod, edges, nodes)
        return ("ok", fn(g, src, dst, weight="weight"))
    except Exception as exc:  # noqa: BLE001 - the exception IS the observation
        return ("raise", type(exc).__name__, tuple(str(a) for a in exc.args))


def norm(r):
    # NaN != NaN, so compare its repr; otherwise leave values alone (int vs float matters).
    if r[0] == "ok" and isinstance(r[1], float) and math.isnan(r[1]):
        return ("ok", "nan")
    if r[0] == "ok":
        return ("ok", repr(r[1]))
    return r


CASES = [
    ("plain float", [("a", "b", 1.0), ("b", "c", 2.0)], "a", "c", ()),
    ("plain int", [("a", "b", 1), ("b", "c", 2)], "a", "c", ()),
    ("parallel min wins", [("a", "b", 5.0), ("a", "b", 2.0), ("b", "c", 1.0)], "a", "c", ()),
    ("parallel int/float mix", [("a", "b", 5), ("a", "b", 2.0), ("b", "c", 1)], "a", "c", ()),
    ("negative weight", [("a", "b", -1.0), ("b", "c", 2.0)], "a", "c", ()),
    ("negative cycle", [("a", "b", 1.0), ("b", "a", -5.0), ("b", "c", 1.0)], "a", "c", ()),
    ("nan weight", [("a", "b", float("nan")), ("b", "c", 1.0)], "a", "c", ()),
    ("inf weight", [("a", "b", float("inf")), ("b", "c", 1.0)], "a", "c", ()),
    ("neg inf weight", [("a", "b", float("-inf")), ("b", "c", 1.0)], "a", "c", ()),
    ("non-numeric weight", [("a", "b", "heavy"), ("b", "c", 1.0)], "a", "c", ()),
    ("missing weight attr", [("a", "b"), ("b", "c")], "a", "c", ()),
    ("source == target", [("a", "b", 1.0)], "a", "a", ()),
    ("unreachable target", [("a", "b", 1.0)], "a", "z", ("z",)),
    ("missing source", [("a", "b", 1.0)], "zz", "b", ()),
    ("missing target", [("a", "b", 1.0)], "a", "zz", ()),
    ("self loop", [("a", "a", 1.0), ("a", "b", 2.0)], "a", "b", ()),
    ("zero weight", [("a", "b", 0.0), ("b", "c", 0.0)], "a", "c", ()),
    ("bool weight", [("a", "b", True), ("b", "c", 1)], "a", "c", ()),
]

print(f"{'case':<24} {'networkx':<34} {'fnx public':<10} {'raw kernel':<10}")
pub_bad, raw_bad = [], []
for name, edges, src, dst, nodes in CASES:
    ref = norm(outcome(nx.bellman_ford_path_length, nx, edges, src, dst, nodes))
    pub = norm(outcome(fnx.bellman_ford_path_length, fnx, edges, src, dst, nodes))
    raw = norm(outcome(RAW, fnx, edges, src, dst, nodes))
    if pub != ref:
        pub_bad.append((name, ref, pub))
    if raw != ref:
        raw_bad.append((name, ref, raw))
    shown = str(ref[1] if ref[0] == "ok" else f"{ref[1]}{ref[2]}")[:33]
    print(f"{name:<24} {shown:<34} {'MATCH' if pub == ref else 'DIVERGE':<10} "
          f"{'MATCH' if raw == ref else 'DIVERGE':<10}")

print(f"\npublic wrapper divergences from networkx: {len(pub_bad)}")
for n, r, g in pub_bad:
    print(f"  {n}: nx={r} fnx={g}")
print(f"raw kernel divergences from networkx: {len(raw_bad)}")
for n, r, g in raw_bad:
    print(f"  {n}: nx={r} raw={g}")
print("\nVERDICT:", "raw kernel is a drop-in on these rows"
      if not raw_bad and not pub_bad else
      "raw kernel is NOT a drop-in - the collapse is carrying behaviour")
