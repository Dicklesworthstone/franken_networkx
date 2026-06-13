# Pass 7 - Louvain coarsened edge-order rejection

Bead: `br-r37-c1-e92fj`

## Candidate

Preserve first-seen edge order while generating coarsened Louvain graphs:

- Replace the `HashMap` collect + sorted edge vector in `louvain_coarsen`.
- Track the first position of each community-pair edge and update its weight in place.
- Keep member ordering, one-level move logic, RNG, gain threshold, modularity math,
  output ordering, and Python public routing unchanged.

This targets NetworkX `_gen_graph`, which iterates old graph edges and updates an existing
coarsened edge without changing that edge's adjacency order.

## Baseline

Before golden SHA:

```text
de259e2eac7805fa8a07f0e28936165dd314ec66a30d851ff253686fbee86875  louvain_pass7_before_golden.json
```

Before summary:

```text
public failures: 0/18
raw failures:    11/18
```

Before hyperfine, raw `ws_300 seed=7 loops=20`:

```text
mean:   0.2736536456 s
stddev: 0.0154953766 s
```

## After

After golden SHA:

```text
8d6074afa0b45d4bb361be460783fc724d9c0572cd141d01164e70303bbb9a22  louvain_pass7_after_coarsen_order_golden.json
```

After summary:

```text
public failures: 0/18
raw failures:    11/18
```

After hyperfine, raw `ws_300 seed=7 loops=20`:

```text
mean:   0.3070016369 s
stddev: 0.0301171634 s
```

## Proof obligations

- Ordering: candidate changed only coarsened edge order.
- Tie-breaking/gain acceptance: unchanged.
- Floating-point: edge weight summation order changed only inside coarsening, then was
  rejected.
- RNG: unchanged.
- Golden-output verification: before and after SHA files were generated.

## Validation

- `RCH_REQUIRE_REMOTE=1 rch exec -- cargo test -p fnx-algorithms louvain --lib`
  passed on `vmi1227854`, 6 tests passed.
- `RCH_REQUIRE_REMOTE=1 rch exec -- cargo build -p fnx-python --release --features pyo3/abi3-py310`
  passed on `vmi1149989`.

## Verdict

Rejected / evidence-only.

The candidate did not improve raw parity (`11/18 -> 11/18`) and the timing gate regressed
or stayed within noise. The Rust hunk was manually reverted.

Next target: exact NetworkX partition mutation/set-materialization semantics, because
first-level neighbor order, gain acceptance, and coarsened edge order have all failed.
