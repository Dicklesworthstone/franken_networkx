# dfs_edges indexed traversal isomorphism proof

Bead: `br-r37-c1-04z53.37`

## Golden output

The FNX golden digest is unchanged before and after the lever:

- Before: `4e7e131ed92143a32bf58531ae1877b323e6aafaa8b9137ef190bace6bcacfd5`
- After: `4e7e131ed92143a32bf58531ae1877b323e6aafaa8b9137ef190bace6bcacfd5`

The digest check is recorded in:

- `golden_sha256.txt`
- `golden_sha256_check.txt`

The NetworkX digest in `baseline_nx.jsonl` differs from the FNX digest before this pass. This pass preserves the FNX digest exactly and does not claim to repair that pre-existing upstream parity gap.

## Ordering and tie-breaking

The old undirected DFS implementation pushed `graph.neighbors(node).iter().rev()` onto the stack and delayed `visited` marking until pop time. The new implementation pushes `neighbors_indices(node_idx).iter().rev()` and still marks `visited` on pop.

Because `neighbors_indices` follows the graph's stored neighbor order and `nodes_ordered` is used for label recovery, the following observable properties are preserved:

- Source resolution behavior for a missing source: empty result.
- Immediate-neighbor traversal order.
- Reverse-push stack order.
- Delayed duplicate suppression through visited-on-pop.
- Depth-limit behavior, including NetworkX-compatible `depth_limit=0` immediate-neighbor emission.
- CGSE decision label order.

## Floating point and RNG

No floating-point arithmetic or RNG path is touched. The benchmark graph seed remains fixed at `42`.

## Focused parity and validation

Validation commands passed:

- `rch exec -- cargo fmt --package fnx-algorithms --check`
- `rch exec -- cargo check -p fnx-algorithms --lib`
- `rch exec -- cargo test -p fnx-algorithms dfs_edges --lib -- --nocapture`
- `rch exec -- cargo clippy -p fnx-algorithms --lib --no-deps -- -D warnings`
- `rch exec -- env PYTHONPATH=python .venv/bin/python -m pytest tests/python/test_traversal.py tests/python/test_traversal_generator_parity.py tests/python/test_sort_neighbors_parity.py -q`

UBS on `crates/fnx-algorithms/src/lib.rs` exited 1 due broad pre-existing findings outside the DFS hunk, including a reported secret-comparison critical on `new_group_id != group_of[i]`. The new indexed DFS hunk introduced no unsafe code and no unwrap/expect/panic path.

