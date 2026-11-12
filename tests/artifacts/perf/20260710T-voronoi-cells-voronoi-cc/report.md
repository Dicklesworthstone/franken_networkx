# br-r37-c1-voronoi — `voronoi_cells` integer-adjacency multi-source BFS

Status: **SHIP.** 4.14x median self-speedup, byte-identical.

## The target

`voronoi_cells(graph, center_nodes)` partitions the graph by nearest center via one
multi-source BFS. The old kernel walked `graph.neighbors(nodes[v])` (a fresh
`Vec<&str>` allocation per pop) and re-hashed each neighbour name through `idx` to
recover its integer index:

```rust
while let Some(v) = queue.pop_front() {
    let d = dist[v];
    if let Some(nbrs) = graph.neighbors(nodes[v]) {        // Vec<&str> alloc / pop
        for nb in nbrs {
            if let Some(&ni) = idx.get(nb) && dist[ni] > d + 1 {   // String hash-probe
                dist[ni] = d + 1;
                nearest[ni] = nearest[v];
                queue.push_back(ni);
            }
        }
    }
}
```

`dist` and `nearest` were already integer-indexed; only the neighbour walk paid the
String tax (V allocs + E hashes).

## The lever

Walk `graph.neighbors_indices(v)` (zero-alloc `&[usize]`) directly. `idx.get(nb)`
never rejected a neighbour (every neighbour is a node), so every neighbour index is
visited exactly as before. `idx` is retained only to resolve the `center_nodes`
names to indices.

## Byte-identical argument

`neighbors_indices(v)` yields the same neighbour set in the same adjacency order as
`neighbors(nodes[v])`, so the FIFO BFS traversal order is unchanged. Since the
nearest-center assignment on an equidistant node is decided by which center's wave
reaches it first (traversal order) and the relaxation `dist[ni] > d+1` /
`nearest[ni] = nearest[v]` is untouched, `nearest` and `dist` are identical → the
cells (a node partition, integer distances, no float) are identical. Verified
in-test: the integer cells are `assert_eq!`-equal to the String baseline
(`voronoi_cells_orig_string`, kept `#[cfg(test)]`).

## Median A/B (paired-interleaved, one binary, NULL control)

`cargo test --release -p fnx-algorithms --lib voronoi_cells_voronoi_ab -- --ignored --nocapture`

Pseudo-random graph n=1500 deg~10, 5 spread-out centers. fnx candidate (integer
BFS) vs the preserved String baseline, interleaved in one process, 121 rounds.
Ratio = base/cand, so **>1 means the integer-BFS kernel is faster**.

| row | median | win_rate | p5_p95 |
|-----|-------:|---------:|--------|
| `INT_vs_string` | **4.1450x** | 121/121 | [3.8364, 4.5101] |
| `NULL_int_vs_int` | 1.0022x | 63/121 | [0.8660, 1.1209] |

The lever median (4.14x) clears the NULL floor: candidate p5 (3.84) is ~3.4x above
the NULL p95 (1.12), and every one of 121 paired rounds won. More modest than the
all-pairs / per-node targets because this is a single O(V+E) traversal, but the
whole per-pop `Vec<&str>` alloc + per-edge String hash is removed.

## Gates

- `cargo check -p fnx-algorithms --all-targets` (remote): exit 0, clean.
- clippy `-D warnings` (remote): clean.
- Existing `voronoi_cells` unit tests (path, single center): green.

## Files

- Production: `crates/fnx-algorithms/src/lib.rs` — `voronoi_cells`.
- Test-only: `voronoi_cells_orig_string` baseline + `voronoi_cells_voronoi_ab` A/B.
