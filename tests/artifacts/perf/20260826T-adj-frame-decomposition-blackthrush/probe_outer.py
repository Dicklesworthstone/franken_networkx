"""What is inside the 169 ns outer AdjacencyView.__getitem__ frame?

On a warm row the Python outer view does, per subscript:

    owner = self._fnx_owner            # plain attribute load
    seq = owner.nodes_seq              # PyO3 GETTER -> a round trip into Rust
    ... cache token compare ...
    view = cache[1].get(node)          # dict lookup
    return view

`owner.nodes_seq` is the only PyO3 crossing on that path, so it is the piece
worth sizing before anyone tries to remove the frame. Remove exactly one thing
at a time and time each in the SAME invocation with dual A/A nulls:

    A  owner.nodes_seq                 the PyO3 getter alone
    B  G.adj[u]                        the whole outer frame (warm row cache)
    C  G.adj[u][v]                     outer frame + row subscript
    D  G._fnx_edge_attr_dict_fast(u,v) the native accessor alone

Both arms of every pair are FrankenNetworkX: this is a decomposition, not a
vs-incumbent claim.
"""
import json
import os
import sys

sys.path.insert(0, "/data/projects/franken_networkx/scripts")
import perf_harness as ph

CALLS = 512


def build(cls_name, n=2000, m=8000, seed=7):
    import random
    import franken_networkx as fnx

    rng = random.Random(seed)
    seen, stream = set(), []
    while len(stream) < m:
        u, v = rng.randrange(n), rng.randrange(n)
        if u == v or (min(u, v), max(u, v)) in seen:
            continue
        seen.add((min(u, v), max(u, v)))
        stream.append((u, v))
    g = getattr(fnx, cls_name)()
    g.add_nodes_from(range(n))
    g.add_edges_from([(u, v, {"weight": 1}) for u, v in stream])
    return g, stream[:CALLS]


def main():
    import franken_networkx._fnx as _fnx
    exp = os.environ.get("FNX_EXPECT_SO")
    if exp and os.path.realpath(_fnx.__file__) != os.path.realpath(exp):
        raise RuntimeError(f"wrong extension loaded: {_fnx.__file__}")
    ph.provenance_header("probe=outer-frame-decomposition")

    out = {}
    for cls_name in ("Graph", "DiGraph"):
        g, pairs = build(cls_name)
        adj = g.adj
        fast = g._fnx_edge_attr_dict_fast
        nodes = [u for u, _ in pairs]
        for u, v in pairs:                      # warm the row-view cache
            adj[u][v]; fast(u, v)

        def seq_only(*, o=g, ns=nodes):
            return [o.nodes_seq for _ in ns]

        def row_only(*, d=adj, ns=nodes):
            return [d[u] is not None for u in ns]

        def full(*, d=adj, e=pairs):
            return [d[u][v] is not None for u, v in e]

        def native(*, f=fast, e=pairs):
            return [f(u, v) is not None for u, v in e]

        per = {}
        for name, fn in (("nodes_seq getter", seq_only), ("adj[u] (outer frame)", row_only),
                         ("adj[u][v] (full)", full), ("native accessor", native)):
            lab = f"{cls_name}: {name}"
            null = ph.paired(f"[A/A] {lab}", fn, fn)
            # time against itself once more to get a clean median; the A/A pair
            # IS the measurement here since both arms are the same callable.
            per[name] = {"ns": null.p50_a * 1e9 / CALLS, "null": null.ratio_p50,
                         "cv": null.cv_a}
            print(f"  {cls_name:8s} {name:24s} {per[name]['ns']:7.1f} ns/call   "
                  f"A/A={null.ratio_p50:.4f} cv={null.cv_a:.2f}%", flush=True)
        out[cls_name] = per

    print("\nOUTER FRAME BREAKDOWN (ns/call):", flush=True)
    for cls_name, per in out.items():
        seq = per["nodes_seq getter"]["ns"]
        row = per["adj[u] (outer frame)"]["ns"]
        full_ = per["adj[u][v] (full)"]["ns"]
        nat = per["native accessor"]["ns"]
        print(f"  {cls_name}:", flush=True)
        print(f"    nodes_seq PyO3 getter      {seq:7.1f}", flush=True)
        print(f"    adj[u] outer frame total   {row:7.1f}   -> getter is {100*seq/row:4.1f}% of it", flush=True)
        print(f"    adj[u][v] full             {full_:7.1f}", flush=True)
        print(f"    native accessor alone      {nat:7.1f}", flush=True)
        print(f"    row subscript = full-outer {full_-row:7.1f}", flush=True)
    print("probe_outer_json=" + json.dumps(out, sort_keys=True, separators=(",", ":")), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
