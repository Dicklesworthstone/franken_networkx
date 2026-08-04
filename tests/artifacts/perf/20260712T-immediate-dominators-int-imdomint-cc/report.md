# br-r37-c1-imdomint — immediate_dominators successor-iteration integer swap

Status: **SHIP.** 2.79x, byte-identical. My change clippy-clean (crate has pre-existing peer lint debt,
untouched).

## The target

`immediate_dominators(digraph, start)` (fnx-algorithms) is already integer-based internally (integer `idom`,
`preds`, `rpo`), but it still iterated successors by **name** in two loops — the reverse-postorder DFS and
the predecessor-building pass — each calling `digraph.successors(nodes[node])` (a `Vec<&str>` alloc per node)
then re-hashing every successor via `node_to_idx[s]` (a String hash per edge).

## The lever

Walk `digraph.successors_indices(node)` (zero-alloc `&[usize]`) directly in both loops, dropping the
`Vec<&str>` allocations and the `O(E)` `node_to_idx[s]` re-hashes.

## Byte-identical argument

`successors_indices(node)` yields the same successors as `successors(nodes[node])`, so the DFS visit order
and the `preds` lists are unchanged. Moreover the immediate-dominator map is a **unique fixpoint** of the
Cooper–Harvey–Kennedy iteration — the reverse-postorder only affects convergence speed, not the result, and
the `intersect` meet is commutative/associative — so even any successor-order difference would converge to
the identical `idom`. Verified: A/B **differential parity** `assert_eq!(old_idom_map, new_idom_map)` (inline
old-String-successors vs new-`successors_indices`, on an 8000-node DAG) passed before timing; the 11
`immediate_dominators`/dominance suite tests pass, including `chain` and `diamond` (which exercise the
`intersect`/merge).

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib immediate_dominators_int_ab -- --ignored --nocapture`

8000-node forward DAG (node i → i+1..i+5), start=0. 61 rounds. Ratio = string/index, **>1 = index faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `INT_vs_string` | **2.7890x** | 61/61 | [2.2122, 3.3708] |
| `NULL_int_vs_int` | 0.9964x | 28/61 | [0.8540, 1.1724] |

Decisive: candidate p5 (2.21) ~1.9x above the NULL p95 (1.17); all 61 rounds won.

### Sizing note

A first pass at n=5000 / out-degree 2 gave a real median win (1.76x, 61/61) but the ~1.8ms build left the
null wide (p95 1.52), so candidate p5 (1.42) didn't clear it — a timer-noise floor. Raising to n=8000 /
out-degree 5 both lengthened the build (tightening the null) and enlarged the successor-iteration fraction
(the String re-hashes), lifting the median to 2.79x and candidate p5 to 2.21, clear of the null. (Same sizing
lesson as `to_undirected`.)

## Clippy note

My change is clippy-clean (0 findings in production ~35415-35438 / test ~71003-71181, grep-verified). The
crate has 12 pre-existing clippy `-D warnings` errors in peer/committed code — left untouched per
shared-checkout discipline.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `immediate_dominators` (two successor loops).
- Test-only: `immediate_dominators_int_ab` A/B.

## Vein status

Fifth "name-keyed → integer" sub-family win. Distinct flavour: a function already integer *internally* whose
only residual was iterating successors by name. Benefits `dominance_frontiers` too (it calls
`immediate_dominators`). Next: grep for other mostly-integer fns that still call `neighbors(name)`/
`successors(name)` + a `node_to_idx[s]` re-hash inside their hot loops.
