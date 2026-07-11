# br-r37-c1-bfslbl — `bfs_labeled_edges` integer-adjacency BFS

Status: **SHIP.** bit-identical, clippy clean. (median — see ab_measurement.log)

## The target

`bfs_labeled_edges(graph, source)` is one BFS (O(V+E)) emitting `(u, v, label)`
triples (`forward`/`nontree`/`reverse`). `visited` was already a `Vec<bool>` mark
array, but the kernel still called `graph.neighbors(nodes[v])` (a fresh `Vec<&str>`
alloc per pop) and re-hashed each neighbour name through `idx`.

## The lever

Walk `graph.neighbors_indices(v)` directly (zero-alloc `&[usize]`); `idx` dropped
(`idx.get(nb)` never rejected a neighbour); `source` resolved once via
`get_node_index`.

## Byte-identical argument

`neighbors_indices(v)` yields the same neighbour set in the same adjacency order (NO
sort), so the forward/nontree/reverse edge sequence and the `visited` semantics are
unchanged. Output is a `(String, String, String)` list (no float). Verified in-test
with `assert_eq!` against the String baseline (`bfs_labeled_edges_orig_string`,
`#[cfg(test)]`).

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib bfs_labeled_edges_bfslbl_ab -- --ignored --nocapture`

Connected pseudo-random graph n=3000 deg~10, 121 rounds. See `ab_measurement.log`
for the measured median (INT_vs_string vs NULL_int_vs_int).

## Gates

- clippy `-D warnings`: clean (batch pass verifies this + dfspost).
- A/B `cargo test --release` ran clean; parity assert green.
- pyo3 `bfs_labeled_edges` calls this kernel directly — the win reaches Python.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `bfs_labeled_edges`.
- Test-only: `bfs_labeled_edges_orig_string` baseline + `..._bfslbl_ab` A/B.
