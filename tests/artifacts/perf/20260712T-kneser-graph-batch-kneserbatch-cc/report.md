# br-r37-c1-kneserbatch — kneser_graph disjoint-subset edge batch-insert

Status: **SHIP.** 12.35x, byte-identical — the biggest result-builder batch win to date. My change
clippy-clean (crate has pre-existing peer lint debt, untouched).

## The target

`kneser_graph(n, k)` (fnx-algorithms) = the Kneser graph KG(n,k): nodes are the k-subsets of {0..n-1},
edges connect **disjoint** subsets. The edge loop iterates all `i<j` subset pairs, tests disjointness, and
adds `(names[i], names[j])` via a per-edge `add_edge`.

## The lever

Collect the disjoint-subset edges (same `i<j` order) into one `Vec<(&str, &str)>` and insert with one
`Graph::extend_edges_unrecorded`. The subset `&str`s borrow the local `names` vector, so no cloning is added.

## Byte-identical argument

The disjointness test `subsets[i].iter().all(|x| !subsets[j].contains(x))` reads only the input `subsets`
(never `g`); each `(i,j)` with `i<j` names a distinct node pair, so every collected edge is unique with no
self-loop. `extend_edges_unrecorded` resolves indices, dedups on `(s_idx, t_idx)`, and pushes adjacency
exactly as `add_edge`, in the identical order; all nodes are pre-added so every endpoint resolves. Verified:
A/B parity `assert_eq!(edges_ordered_borrowed + nodes_ordered)` on KG(22,2) (231 nodes, 21945 edges) passed
before timing; suite test `test_kneser_graph_petersen` (KG(5,2) = Petersen, 10 nodes/15 edges) passes.

## Why this clears the null so decisively (12.35x)

The O(subsets²) disjoint-check loop is identical in both arms, and each check is O(k)=O(2) — negligible.
The per-edge `add_edge`'s **policy record** on ~21945 edges is thus nearly the entire differentiable cost,
dropped to one. The policy record dwarfs the tiny disjoint check, so the ratio is even larger than the
dup-heavy `moral_graph` (9.80x).

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib kneser_graph_batch_ab -- --ignored --nocapture`

KG(22,2): 231 nodes, 21945 edges. 61 rounds. Ratio = base/cand, **>1 = batch faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BATCH_vs_string` | **12.3531x** | 61/61 | [9.8242, 17.7710] |
| `NULL_batch_vs_batch` | 0.9918x | 28/61 | [0.7891, 1.1430] |

Decisive: candidate p5 (9.82) ~8.6x above the NULL p95 (1.14); all 61 rounds won.

## Clippy note

My change is clippy-clean (0 findings in production ~34171-34186 / test ~68593-68698, grep-verified). The
crate has 12 pre-existing clippy `-D warnings` errors in peer/committed code — left untouched per
shared-checkout discipline.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `kneser_graph`.
- Test-only: `kneser_graph_batch_ab` A/B.

## Vein status

Twentieth result-builder batch win, and the largest. Reachable via `kneser_graph` pyo3 binding. Confirms
that a builder whose per-edge *guard* is cheap (here an O(k) disjoint test) but whose *emission* is a full
`add_edge` gets the maximum policy-drop benefit — the guard doesn't dilute it. Next: other combinatorial
generators with a cheap guard + per-edge add (grid/lattice families), or remaining expanding builders.
