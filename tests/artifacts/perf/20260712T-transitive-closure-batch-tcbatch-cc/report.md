# br-r37-c1-tcbatch — transitive_closure reachability-edge batch-insert

Status: **SHIP.** 8.51x, byte-identical. My change clippy-clean (crate has pre-existing peer lint debt,
untouched).

## The target

`transitive_closure(digraph, reflexive)` (fnx-algorithms) — for each source, BFS the reachable set (in
discovery order `order`) and add edge `(source, w)` for each reachable `w`, via a per-edge `add_edge`. The
closure is `O(reachable-pairs)`, which for a chain-like DAG is `|V|²/2 ≫ |E|`.

## The lever

Collect every reachability edge `(source, w)` across all sources (identical source-major, BFS-discovery
order) into one `Vec<(&str, &str)>` and insert with one `DiGraph::extend_edges_unrecorded`. The BFS-produced
`&str`s all borrow the input digraph, so no cloning is added.

## Byte-identical argument

Only the *destination* of each edge changed: `add_edge(source, w)` → `edges.push((source, w))` + one
`extend_edges_unrecorded` at the end. The BFS, the `order` vector, the cyclic self-loop rediscovery
(`br-r37-c1-tc-cyclic`), and the `reflexive` self-loop push are **completely unchanged**. Each `(source, w)`
is emitted once (visited-set dedup). `extend_edges_unrecorded` resolves indices, dedups on `(s_idx, t_idx)`,
and handles self-loops (`s_idx == t_idx`) exactly as `add_edge`, in the identical order; all nodes are
pre-added so every endpoint resolves to an existing index. Verified: A/B parity `assert_eq!
(edges_ordered_borrowed + nodes_ordered)` on the 200-node chain closure (19900 edges) passed before timing;
suite tests `transitive_closure_{empty, chain, preserves_hardened_mode}` pass. The cyclic + reflexive paths
share the preserved edge-emission loop, so byte-identity holds by construction.

## Why this clears the null

Chain closure output ≈ `|V|²/2` (19900 edges from 199 input edges) — strongly expanding. The per-source BFS
is O(|V|) (out-degree 1) and identical in both arms, so the per-edge policy-record drop on 19900 inserts is
the dominant differentiable cost. "Output ≫ |E|" win.

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib transitive_closure_batch_ab -- --ignored --nocapture`

Chain DAG `0→1→…→199` (closure = 200·199/2 = 19900 edges). 61 rounds. Ratio = base/cand, **>1 = batch
faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `BATCH_vs_string` | **8.5110x** | 61/61 | [7.1965, 10.4999] |
| `NULL_batch_vs_batch` | 1.0028x | 33/61 | [0.9245, 1.1561] |

Decisive: candidate p5 (7.20) ~6.2x above the NULL p95 (1.16); all 61 rounds won.

## Clippy note

My change is clippy-clean (0 findings in production ~20866-20920 / test ~68326-68450, grep-verified). The
crate has 12 pre-existing clippy `-D warnings` errors in peer/committed code — left untouched per
shared-checkout discipline.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `transitive_closure`.
- Test-only: `transitive_closure_batch_ab` A/B.

## Vein status

Eighteenth result-builder batch win. Reachable via the `transitive_closure` pyo3 binding (allow_threads).
Another strong "output ≫ |E|" expander — the per-source reachability block is the largest edge surface in the
closure/reduction family. Next: `make_clique_bipartite`, or other expanding builders.
