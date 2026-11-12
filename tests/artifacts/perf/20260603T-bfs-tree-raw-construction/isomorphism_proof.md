# bfs_tree raw construction rejection proof

Behavior contract:

- Preserve BFS discovery edge order.
- Preserve source node handling.
- Preserve `depth_limit` behavior.
- Preserve directed/reverse/sorted-neighbor fallback behavior.
- Preserve output node and edge lists.
- Preserve RNG seed and graph-generation input.

Golden digest:

- `7dcc53d6a98a683886e2d525245875203e8db1797d6fc762de25a54aff42e592`

Digest result:

- Baseline FNX: `7dcc53d6a98a683886e2d525245875203e8db1797d6fc762de25a54aff42e592`
- Baseline NetworkX: `7dcc53d6a98a683886e2d525245875203e8db1797d6fc762de25a54aff42e592`
- Candidate FNX: `7dcc53d6a98a683886e2d525245875203e8db1797d6fc762de25a54aff42e592`
- Candidate NetworkX: `7dcc53d6a98a683886e2d525245875203e8db1797d6fc762de25a54aff42e592`
- Restored FNX: `7dcc53d6a98a683886e2d525245875203e8db1797d6fc762de25a54aff42e592`

Source restoration:

- `rg "bfs_tree_indices|BfsTreeIndexResult|extend_indexed_tree_unrecorded" crates/fnx-algorithms/src/lib.rs crates/fnx-classes/src/digraph.rs crates/fnx-python/src/algorithms.rs` returned no matches.
- `git diff -- crates/fnx-classes/src/digraph.rs crates/fnx-algorithms/src/lib.rs crates/fnx-python/src/algorithms.rs --stat` returned no source diff.

Floating point:

- No floating-point path was changed.

RNG:

- Benchmark graph seed stayed `42`.
