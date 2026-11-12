# br-r37-c1-modwmap — modularity community double-loop → integer indices + weight map

Status: **SHIP.** 1.98x, ULP-identical. Opens a fresh sub-family (the `has_edge`/`node_to_idx`-in-nested-loop
pattern). My change clippy-clean (crate has pre-existing peer lint debt, untouched).

## The target

`modularity`'s community double-loop is `O(Σ|comm|²)` — for each ordered pair `(u, v)` in each community it
did `node_to_idx.get(u)` + `node_to_idx.get(v)` (String hashes) + `graph.has_edge(u, v)` (String) +
`edge_weight_or_default` (String, on an edge). For a few large communities the double-loop dominates the whole
function.

## The lever (two parts — the first alone is not enough)

1. Precompute the edge weights into an **index-keyed** `HashMap<(usize,usize), f64>` (`w_map`) once (O(|E|)),
   so `a_uv` is an O(1) integer lookup instead of `has_edge` + `edge_weight_or_default`.
2. **Resolve each community's nodes to indices once** (`comm_idx`), so the double-loop iterates `(ui, vi)`
   directly — dropping the per-pair `node_to_idx.get` String hash.

**Key finding:** part 1 alone was *marginal* (1.06x, candidate p5 below null) — `has_edge` is already an
internal hash, so replacing it with another hash saved little. The dominant cost was the per-pair
`node_to_idx.get`; adding part 2 lifted it to 1.98x.

## Byte-identical (ULP) argument

`comm_idx` keeps the community's in-graph nodes in the same order, so the `(ui, vi)` pairs — and hence the `q`
summation order — are identical to the per-name loop. `a_uv` is identical: `w_map[canon(ui,vi)]` holds exactly
`edge_weight_or_default` for each undirected (symmetric-weight) edge, so edge → weight and non-edge → 0.0,
matching the old `if has_edge { edge_weight } else { 0.0 }`. No float reassociation. Verified: A/B parity
`assert_eq!(old.to_bits(), new.to_bits())` (exact f64 bits) passed before timing; the 5 modularity suite tests
pass, including `modularity_perfect_partition` (asserts the numeric Q value).

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib modularity_wmap_ab -- --ignored --nocapture`

Circulant (2000 nodes, degree 20) partitioned into 4 communities of 500 (double-loop = 4·500² = 1M pairs).
61 rounds. Ratio = has_edge/wmap, **>1 = wmap faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `WMAP_vs_hasedge` | **1.9794x** | 60/61 | [1.4957, 2.3381] |
| `NULL_wmap_vs_wmap` | 0.9990x | 30/61 | [0.7713, 1.3048] |

Decidable: candidate p5 (1.50) clears the NULL p95 (1.30); 60/61 rounds won. (An initial w_map-only version
measured 1.06x with p5 below null — recorded in the log — motivating the `comm_idx` addition.)

## Clippy note

My change is clippy-clean (0 findings in production ~23960-23995 / test ~71895-72047, grep-verified). The
crate has 12 pre-existing clippy `-D warnings` errors in peer/committed code — left untouched per
shared-checkout discipline.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `modularity` (double-loop; pairs with the earlier
  `br-r37-c1-modmat` setup fold).
- Test-only: `modularity_wmap_ab` A/B.

## Vein status

New sub-family: a nested `for u in set { for v in set }` loop doing per-pair `node_to_idx.get` + `has_edge`.
The fix is to **hoist the set→index resolution out of the inner loop** and read adjacency/weight from an
index-keyed map. Lesson: `has_edge`→map is marginal (both hash); the win is dropping the per-pair
`node_to_idx.get`. Next: sweep other `for u in group/comm/set { for v … node_to_idx.get + has_edge }`
double-loops (e.g. group centralities, other community quality measures).
