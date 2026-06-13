# Pass 3 - Louvain raw output-order parity lever

Bead: `br-r37-c1-e92fj`

## Candidate

Preserve the outer community order produced by the native Louvain partition stream in
`louvain_partition_to_node_names`.

The previous conversion sorted the final communities by their first node name after the
Rust kernel had already produced a partition order. NetworkX returns the last partition
emitted by `louvain_partitions` without an extra lexicographic community sort. This lever
removes only that final outer sort.

Unchanged behavior surfaces:

- Node names inside each community are still sorted.
- Louvain move order, merge gain/tie logic, coarsening, threshold handling, RNG, and
  floating-point arithmetic are unchanged.
- Python public routing is unchanged.

## Baseline

Before SHA:

```text
c75477e6f7569ee7ea0e29c9ac85337af56e4bad30ab4adce0e708add843d7a9  louvain_pass3_before_golden.json
```

Summary:

```text
public failures: 0/18
raw failures:    15/18
```

## After

After SHA:

```text
c45228b3e6cb3b84f5dddbf48e82c0e15078abfe404d5c512a0c798b20eae8b7  louvain_pass3_after_order_golden.json
```

Summary:

```text
public failures: 0/18
raw failures:    11/18
```

Raw native parity fixed for the three `path_12` seeds and for `karate` seed 1.
Remaining raw failures are partition-shape mismatches on `cycle_18`, two `karate`
seeds, `ws_150`, and `ws_300`.

## Proof obligations

- Ordering: changed only the final outer community order to preserve the kernel's
  emitted order instead of applying a string-key sort that NetworkX does not apply.
- Tie-breaking: unchanged.
- Floating-point: unchanged.
- RNG: unchanged.
- Golden-output verification: `sha256sum -c` passed for the before and after golden
  artifacts.

## Validation

- `RCH_REQUIRE_REMOTE=1 rch exec -- cargo build -p fnx-python --release --features pyo3/abi3-py310`
  passed on `vmi1153651`.
- `RCH_REQUIRE_REMOTE=1 rch exec -- cargo check -p fnx-algorithms --lib`
  passed on `vmi1149989`.
- `RCH_REQUIRE_REMOTE=1 rch exec -- cargo clippy -p fnx-algorithms --lib -- -D warnings`
  passed on `vmi1149989`.
- `cargo fmt -p fnx-algorithms --check` still fails on pre-existing formatting drift in
  unrelated regions of `crates/fnx-algorithms/src/lib.rs`.
- `ubs crates/fnx-algorithms/src/lib.rs` completed but exits nonzero on broad
  pre-existing findings outside this Louvain hunk, including a false-positive
  "secret compare" report for `new_group_id != group_of[i]`.

## Verdict

Keep as a narrow parity-unlock lever.

Score: `(Impact 2 x Confidence 5) / Effort 1 = 10`.

The public path remains compatible with NetworkX, and the raw native kernel moved from
`15/18` to `11/18` failures without changing algorithm math or routing. Pass 4 should
target the remaining partition-shape gap in the one-level move/coarsening semantics.
