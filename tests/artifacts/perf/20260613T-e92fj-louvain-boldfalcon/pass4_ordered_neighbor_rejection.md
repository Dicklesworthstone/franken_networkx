# Pass 4 - Louvain ordered-neighbor scan rejection

Bead: `br-r37-c1-e92fj`

## Candidate

Preserve NetworkX-style insertion order while scanning Louvain neighbor communities:

- Replace `BTreeMap` neighbor/community iteration in the native one-level Louvain pass
  with insertion-order vectors.
- Keep RNG, move gain formula, gain epsilon, coarsening, output order, and Python public
  routing unchanged.

This targets the fact that NetworkX builds `weights2com` from adjacency insertion order
and keeps the first community that reaches a tied gain, while the Rust implementation
currently scans communities sorted by id.

## Baseline

Before golden SHA:

```text
c96ae12c11d1f50e44ec2ee3ae284a07fd1ca0d46d2766fe25b6a61c56846e47  louvain_pass4_before_golden.json
```

Before summary:

```text
public failures: 0/18
raw failures:    11/18
```

Before hyperfine, raw `ws_300 seed=7 loops=20`:

```text
mean:   0.2783998687 s
stddev: 0.0156215877 s
```

## After

After golden SHA:

```text
df471a849eda5fddf715c19e3b598eb818973b868bfa46085bf30cdaeb1e7351  louvain_pass4_after_ordered_neighbors_golden.json
```

After summary:

```text
public failures: 0/18
raw failures:    11/18
```

After hyperfine, raw `ws_300 seed=7 loops=20`:

```text
mean:   0.2750377379 s
stddev: 0.0127995358 s
```

Remaining raw failures:

```text
cycle_18 seed 0
cycle_18 seed 1
cycle_18 seed 7
karate seed 0
karate seed 7
ws_150 seed 0
ws_150 seed 1
ws_150 seed 7
ws_300 seed 0
ws_300 seed 1
ws_300 seed 7
```

## Proof obligations

- Ordering: candidate changed only native neighbor/community scan order, then was
  reverted after the gate did not improve.
- Tie-breaking: no kept change.
- Floating-point: no kept change.
- RNG: no kept change.
- Golden-output verification: before and after SHA files were generated with the
  Pass 3 and candidate overlays respectively.

## Validation

- `RCH_REQUIRE_REMOTE=1 rch exec -- cargo check -p fnx-algorithms --lib`
  passed on `vmi1264463`.
- `RCH_REQUIRE_REMOTE=1 rch exec -- cargo build -p fnx-python --release --features pyo3/abi3-py310`
  passed on `vmi1264463`.

## Verdict

Rejected / evidence-only.

The candidate did not reduce raw parity failures (`11/18 -> 11/18`) and the measured
timing shift is within noise and below the Score>=2.0 keep threshold. The Rust hunk was
manually reverted. Pass 5 should attack a deeper semantic primitive: the zero-gain
move threshold / partition mutation rule, not another scan-order micro-lever.
