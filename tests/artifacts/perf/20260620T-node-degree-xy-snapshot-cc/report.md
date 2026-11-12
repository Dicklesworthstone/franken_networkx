# node_degree_xy — whole-graph adjacency snapshot fast path → beats nx 3.4–4.4x

Bead: br-r37-c1-wqhqr
Agent: cc (CopperCliff)
Date: 2026-06-20

## Problem

Gauntlet head-to-head (2026-06-19): public `fnx.node_degree_xy` was
contract-correct but badly slower than NetworkX:

| shape (default args)              | fnx     | nx      | ratio  |
|-----------------------------------|---------|---------|--------|
| undirected hub-spoke h512/s32     | 531 ms  | 60 ms   | 0.113x |
| directed fan l512/f32 (x=out,y=in)| 218 ms  | 50 ms   | 0.231x |

nx's algorithm is a pure-Python dict walk; fnx paid the substrate tax twice:

1. **O(E) degree recomputation** — nx recomputes each neighbour's y-degree via
   a FRESH `DegreeView` per source node (`ydeg(neighbors)`), one per-node
   round-trip on the fnx substrate.
2. **O(V) per-node `G.edges(u)`** — a fresh `EdgeView` PyO3 allocation per
   source node.

The raw u-major PyO3 kernel was previously rejected/reverted because it emitted
the wrong NetworkX contract (set-source order, double-orientation, x/y
direction). This fix keeps the exact nx contract.

## Fix (two levers, both order-preserving)

`node_degree_xy` (pure Python, no rebuild):

1. **Bulk y-degree map.** `dy = dict(ydeg(weight=weight))` once. `dy[v]` is
   identical to `ydeg(v)` for every node, so the inner per-node `DegreeView` is
   replaced by a dict lookup — byte-exact in value AND order.
2. **Whole-graph adjacency snapshot.** For the default `nodes=None`,
   `type(G) in (Graph, DiGraph)` case, snapshot the entire adjacency with ONE
   native `_native_adjacency_keys()` call (verified to yield neighbours in exact
   `G.edges(u)` order, self-loops included; directed = successors = out-edges),
   then iterate it as a pure-Python dict. Emission order is identical to nx:
   source order via `set(G)`, neighbour order via the snapshot. Degrees come
   from the bulk `dict(xdeg)`/`dy` maps (reused for undirected — one pass).

Multigraphs (no native keys snapshot — different type) and the `nodes`-subset
case keep the per-node path, which still benefits from lever 1.

## Proof

- `bench_and_parity.py` (this dir): **192 byte-exact parity checks, 0 fails** —
  str/int keys, directed both orientations (out/in, in/out), weighted, self-
  loops, empty/isolated, `nodes` subset, MultiGraph/MultiDiGraph exact order,
  60-seed simple-graph fuzz (both orientations) + 30-seed multigraph fuzz.
- Golden sha256 over all results:
  `9123af2d819efaf20f980cf86ecff6305d03beb0bfc62d7e22afd01c787a2e5e`.
- Downstream consumers (`degree_assortativity_coefficient`,
  `degree_pearson_correlation_coefficient`, weighted + unweighted, directed +
  undirected): 100 checks, 0 fails (worst abs diff ~1e-15).

## Timing (min-of-9, warm; run.log in this dir)

| shape                       | before | after  | nx      | after vs nx | self-speedup |
|-----------------------------|--------|--------|---------|-------------|--------------|
| undir hub512/s32            | 531 ms | 14 ms  | 62 ms   | **4.43x**   | ~38x         |
| dir fan512/f32 (out,in)     | 218 ms | 16 ms  | 55 ms   | **3.43x**   | ~13x         |

(Intermediate: lever 1 alone moved 0.113x→0.164x / 0.231x→0.390x; the
adjacency snapshot is what crosses parity.)

## Note

Pure-Python change scoped to `node_degree_xy`. No Rust/kernel change. The
`_native_adjacency_keys` snapshot order was verified to match `G.edges(u)`
exactly (including self-loops, directed successors) before routing to it.
