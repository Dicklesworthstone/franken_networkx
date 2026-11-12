# br-r37-c1-modmat — modularity redundant-setup fold

Status: **SHIP.** 1.71x, ULP-identical. A pivot off the generator batch family into the redundant-
materialization family. My change clippy-clean (crate has pre-existing peer lint debt, untouched).

## The target

`modularity(graph, communities, resolution, weight_attr)` (fnx-algorithms) had a triple redundancy in its
setup:

1. `graph.nodes_ordered()` was called **3 times** (m2 pass, node_to_idx, and the `k` pass), each rebuilding
   a `Vec<&str>`.
2. The `m2` total-weight computation and the `k` (per-node weighted degree) vector are the **same per-node
   neighbour-weight sum**, computed **twice** — a full extra pass over every node's neighbours
   (`O(Σ deg) = O(2|E|)` `edge_weight_or_default` lookups).

## The lever

Materialize `nodes = graph.nodes_ordered()` once, compute `k` once, and derive `m2 = k.iter().sum()`.

## ULP-identical argument

The original `m2` is `nodes.iter().map(|nd| neighbour_sum(nd)).sum::<f64>()` — a left-fold over the per-node
sums in `nodes_ordered` order. `k[i]` is exactly `neighbour_sum(nodes[i])` (the identical expression), and
`k.iter().sum()` is the **same left-fold, same order, same values** → bit-identical `m2`. `nodes_ordered()`
is deterministic, so the single materialization equals each prior call, and `node_to_idx` built from it is
identical. The `m2 == 0.0` early return and the community double-loop are unchanged. Verified: A/B parity
`assert_eq!(old.to_bits(), new.to_bits())` (exact `f64` bits) passed before timing; the 5 modularity suite
tests pass, including `modularity_perfect_partition` which asserts the numeric Q value.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib modularity_mat_ab -- --ignored --nocapture`

Dense circulant (1000 nodes, degree 30, ~15000 edges) partitioned into 250 communities of 4 — a
setup-dominated workload so the removed m2 pass shows. 61 rounds. Ratio = orig/fold, **>1 = fold faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `FOLD_vs_orig` | **1.7126x** | 61/61 | [1.3370, 2.2199] |
| `NULL_fold_vs_fold` | 1.0081x | 35/61 | [0.8332, 1.2660] |

Decidable: candidate p5 (1.34) clears the NULL p95 (1.27); all 61 rounds won (vs null 35/61). Modest but
decisive — the win is the setup fraction (halved neighbour iteration + 2 dropped `nodes_ordered` rebuilds),
which is Amdahl-limited by the community double-loop; on a setup-dominated partition (many small communities)
it clears the null.

## Clippy note

My change is clippy-clean (0 findings in production ~23920-23942 / test ~70187-70362, grep-verified). The
crate has 12 pre-existing clippy `-D warnings` errors in peer/committed code — left untouched per
shared-checkout discipline.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `modularity`.
- Test-only: `modularity_mat_ab` A/B.

## Vein status

First win in the **redundant-materialization** family since the generator batch seam wound down. The pattern:
a fn that computes the same per-node/per-edge reduction twice (here `m2` vs `sum(k)`) + calls
`nodes_ordered()`/`edges_ordered()` multiple times. Next: sweep other centrality/community fns for the same
double-reduction + repeated-materialization shape (`edge_weight_or_default`-heavy setups).
