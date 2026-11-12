"""Reference-semantics probe: does a returned object BEHAVE like networkx's?

WHY THIS EXISTS, stated plainly: the ad-hoc check this replaces tested two
dimensions — "does inner attribute mutation propagate" and "does new-key
insertion propagate" — on ONE accessor, and reported the result as though it were
the surface. A systematic enumeration of the same accessor found EIGHT
divergences (br-r37-c1-f3i50). Seven of those were invisible to the old check,
and one of them (read-liveness) invalidates the fix the old check's conclusion
implied. A probe that samples 2 of 10 dimensions does not under-report by 20
percent; it reports a defect as healthy.

THE DESIGN CONSEQUENCE: value parity is the weakest evidence available and it is
what almost every existing test asserts. Two mappings can compare equal, carry
equal values, expose the same type, and still differ in identity, liveness and
mutability — the three properties that decide whether real caller code works.
So this probe sweeps a MATRIX of (accessor x dimension) and reports every cell
where fnx and networkx disagree, rather than confirming the cells someone
happened to think of.

DIMENSIONS, and what each one catches that the others do not:

  type            a wrapper swapped for a raw dict, or vice versa
  identity_calls  two calls return the same object (nx caches; a snapshot cannot)
  identity_raw    the returned object IS the graph's own storage
  read_liveness   a LATER graph mutation is visible through a HELD reference.
                  THE decisive one: no snapshot can satisfy it at any cost, so a
                  divergence here rules out every write-proxy style fix.
  write_reaches   a write on the object reaches the graph
  inner_mutation  mutating a nested value reaches the graph (the dimension the
                  old check tested, and the one most likely to pass anyway)
  write_raises    if writes are rejected, the same exception type in both
  len_iter        len / iter / contains agree
  missing_key     the same exception TYPE AND ARGS on a missing key

Every cell builds its own graph, because probing mutation on a shared fixture
lets one cell's writes silently decide the next cell's answer.

USAGE:  python scripts/reference_semantics_probe.py [--classes Graph,MultiGraph]
Exit status is 0 always; this reports, it does not gate.
"""

from __future__ import annotations

import argparse
import sys

import networkx as nx

import franken_networkx as fnx

SENTINEL = "__probe_sentinel__"


# --- accessors ------------------------------------------------------------
# Each entry: name -> (applies(cls_name), build(lib, cls_name) -> (graph, obj))


def _seed(lib, cls_name):
    graph = getattr(lib, cls_name)()
    graph.add_edge("a", "b", w=1.0)
    graph.add_edge("b", "c", w=2.0)
    if graph.is_multigraph():
        graph.add_edge("a", "b", w=3.0)
    graph.add_node("iso", tag=1)
    graph.graph["gname"] = "fixture"
    return graph


def _multi(cls_name):
    return cls_name.startswith("Multi")


def _directed(cls_name):
    return "Di" in cls_name


ACCESSORS = {
    "get_edge_data(u,v)": (lambda c: True, lambda g: g.get_edge_data("a", "b")),
    "get_edge_data(u,v,k)": (_multi, lambda g: g.get_edge_data("a", "b", 0)),
    "G[u]": (lambda c: True, lambda g: g["a"]),
    "G[u][v]": (lambda c: True, lambda g: g["a"]["b"]),
    "G.adj[u]": (lambda c: True, lambda g: g.adj["a"]),
    "G.adj[u][v]": (lambda c: True, lambda g: g.adj["a"]["b"]),
    "G.succ[u]": (_directed, lambda g: g.succ["a"]),
    "G.pred[u]": (_directed, lambda g: g.pred["b"]),
    "G.nodes[n]": (lambda c: True, lambda g: g.nodes["a"]),
    "G.edges[u,v]": (lambda c: not _multi(c), lambda g: g.edges["a", "b"]),
    "G.edges[u,v,k]": (_multi, lambda g: g.edges["a", "b", 0]),
    "G.graph": (lambda c: True, lambda g: g.graph),
    "G.nodes": (lambda c: True, lambda g: g.nodes),
    "G.adj": (lambda c: True, lambda g: g.adj),
}

# Raw storage each accessor should BE, where networkx exposes one.
RAW = {
    "get_edge_data(u,v)": lambda g: g._adj["a"]["b"],
    "G.nodes[n]": lambda g: g._node["a"],
    "G.graph": lambda g: g.graph,
    "G.adj[u]": lambda g: g._adj["a"],
}


# --- dimensions -----------------------------------------------------------


def dim_type(lib, cls_name, get):
    return type(get(_seed(lib, cls_name))).__name__


def dim_identity_calls(lib, cls_name, get):
    graph = _seed(lib, cls_name)
    return get(graph) is get(graph)


def dim_identity_raw(lib, cls_name, get, raw):
    graph = _seed(lib, cls_name)
    try:
        return get(graph) is raw(graph)
    except Exception as exc:  # noqa: BLE001
        return f"{type(exc).__name__}"


def dim_read_liveness(lib, cls_name, get):
    """A LATER mutation seen through a HELD reference.

    The dimension that decides whether a snapshot can ever be correct.
    """
    graph = _seed(lib, cls_name)
    held = get(graph)
    graph.add_edge("a", "zz", w=9.0)
    graph.add_node("newnode")
    try:
        return ("zz" in held) or ("newnode" in held) or ("zz" in repr(held))
    except Exception as exc:  # noqa: BLE001
        return f"{type(exc).__name__}"


def dim_write_reaches(lib, cls_name, get):
    graph = _seed(lib, cls_name)
    obj = get(graph)
    try:
        obj[SENTINEL] = {"w": 0.0}
    except Exception as exc:  # noqa: BLE001
        return f"raises {type(exc).__name__}"
    probes = (
        graph.graph,
        getattr(graph, "_node", {}),
        getattr(graph, "_adj", {}),
    )
    return any(SENTINEL in p for p in probes) or SENTINEL in repr(graph.graph)


def dim_inner_mutation(lib, cls_name, get):
    """The one dimension the superseded ad-hoc check tested."""
    graph = _seed(lib, cls_name)
    obj = get(graph)
    try:
        for value in obj.values():
            if hasattr(value, "__setitem__"):
                value["probe_w"] = 42
                break
        else:
            return "no-nested-value"
    except Exception as exc:  # noqa: BLE001
        return f"raises {type(exc).__name__}"
    return "probe_w" in repr(graph.adj) or "probe_w" in repr(graph.nodes(data=True))


def dim_write_raises(lib, cls_name, get):
    graph = _seed(lib, cls_name)
    obj = get(graph)
    try:
        obj[SENTINEL] = {"w": 0.0}
    except Exception as exc:  # noqa: BLE001
        return type(exc).__name__
    return "no-raise"


def dim_len_iter(lib, cls_name, get):
    graph = _seed(lib, cls_name)
    obj = get(graph)
    try:
        return (len(obj), tuple(sorted(map(str, iter(obj)))))
    except Exception as exc:  # noqa: BLE001
        return f"raises {type(exc).__name__}"


def dim_missing_key(lib, cls_name, get):
    graph = _seed(lib, cls_name)
    obj = get(graph)
    try:
        obj["__absent__"]
    except Exception as exc:  # noqa: BLE001
        return (type(exc).__name__, repr(exc.args))
    return "no-raise"


def dim_private_write(lib, cls_name, get):
    """Item-assignment into the PRIVATE storage the accessor sits over.

    ADDED AFTER THE PROBE MISSED IT. The first version of this file swept eight
    dimensions and reported 21 divergences, none of which was the one that
    mattered most: networkx's `G._adj` is a raw `dict` and its own algorithms
    mutate it in place, while fnx exposes an `AdjacencyView`, so
    `G._adj[u][v] = {...}` raises in all four classes. A probe that only
    exercises the PUBLIC surface cannot see a private-API contract, and that is
    precisely the surface library code reaches for.
    """
    graph = _seed(lib, cls_name)
    try:
        graph._adj["a"]["probe_target"] = {} if not _multi(cls_name) else {0: {}}
    except Exception as exc:  # noqa: BLE001
        return f"raises {type(exc).__name__}"
    return "probe_target" in graph["a"]


# Graph-level dimensions do NOT vary by accessor, so they are swept once per
# class. Sweeping them per accessor inflated one real finding into 46 identical
# rows and buried the accessor-specific divergences under it.
GRAPH_DIMENSIONS = [
    ("private_write_adj", dim_private_write),
]

DIMENSIONS = [
    ("type", dim_type),
    ("identity_calls", dim_identity_calls),
    ("read_liveness", dim_read_liveness),
    ("write_reaches", dim_write_reaches),
    ("inner_mutation", dim_inner_mutation),
    ("write_raises", dim_write_raises),
    ("len_iter", dim_len_iter),
    ("missing_key", dim_missing_key),
]


def probe(cls_names):
    rows = []
    for cls_name in cls_names:
        for dim_name, fn in GRAPH_DIMENSIONS:
            out = {}
            for lib, tag in ((nx, "nx"), (fnx, "fnx")):
                try:
                    out[tag] = fn(lib, cls_name, None)
                except Exception as exc:  # noqa: BLE001
                    out[tag] = f"PROBE-ERROR {type(exc).__name__}: {exc}"
            rows.append((cls_name, "(graph-level)", dim_name, out["nx"], out["fnx"]))
        for acc_name, (applies, get) in ACCESSORS.items():
            if not applies(cls_name):
                continue
            for dim_name, fn in DIMENSIONS:
                out = {}
                for lib, tag in ((nx, "nx"), (fnx, "fnx")):
                    try:
                        out[tag] = fn(lib, cls_name, get)
                    except Exception as exc:  # noqa: BLE001
                        out[tag] = f"PROBE-ERROR {type(exc).__name__}: {exc}"
                rows.append((cls_name, acc_name, dim_name, out["nx"], out["fnx"]))
            if acc_name in RAW:
                out = {}
                for lib, tag in ((nx, "nx"), (fnx, "fnx")):
                    try:
                        out[tag] = dim_identity_raw(lib, cls_name, get, RAW[acc_name])
                    except Exception as exc:  # noqa: BLE001
                        out[tag] = f"PROBE-ERROR {type(exc).__name__}: {exc}"
                rows.append((cls_name, acc_name, "identity_raw", out["nx"], out["fnx"]))
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--classes",
        default="Graph,DiGraph,MultiGraph,MultiDiGraph",
        help="comma-separated graph classes to probe",
    )
    parser.add_argument("--all", action="store_true", help="print agreeing cells too")
    args = parser.parse_args(argv)
    rows = probe([c.strip() for c in args.classes.split(",") if c.strip()])
    diverging = [r for r in rows if r[3] != r[4]]
    print(f"{len(rows)} cells probed, {len(diverging)} diverge\n")
    print(f"{'class':<13} {'accessor':<22} {'dimension':<16} {'nx':<28} {'fnx'}")
    for cls_name, acc, dim, want, got in (rows if args.all else diverging):
        print(f"{cls_name:<13} {acc:<22} {dim:<16} {str(want)[:27]:<28} {str(got)[:40]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
