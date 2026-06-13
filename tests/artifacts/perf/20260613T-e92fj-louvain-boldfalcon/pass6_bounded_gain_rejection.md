# Pass 6 - Louvain bounded gain-threshold rejection

Bead: `br-r37-c1-e92fj`

## Candidate

Test a bounded version of NetworkX's gain acceptance rule:

- Change `LOUVAIN_GAIN_EPS` from `1.0e-12` to `0.0`.
- Add a per-level repeated `node_to_community` state guard so floating-point dust
  cannot cycle forever.
- Keep RNG, neighbor/community iteration, coarsening, modularity math, output ordering,
  and Python public routing unchanged.

This was a follow-up to Pass 5, where plain `gain > 0` acceptance hung the golden
corpus.

## Baseline

Before golden SHA:

```text
90601ae09716b512406f6c56855a95023323900590f80ebd830aec92911bb98c  louvain_pass6_before_golden.json
```

Before summary:

```text
public failures: 0/18
raw failures:    11/18
```

Before hyperfine, raw `ws_300 seed=7 loops=20`:

```text
mean:   0.2919049105 s
stddev: 0.0137477897 s
```

## After

After golden SHA:

```text
1f03d2335ad25aea1e3b904b98b6bed9829ed36b1cb758ebdec540537b232010  louvain_pass6_after_bounded_gain_golden.json
```

After summary:

```text
public failures: 0/18
raw failures:    11/18
```

After hyperfine, raw `ws_300 seed=7 loops=20`:

```text
mean:   0.2895965515 s
stddev: 0.0196813128 s
```

## Proof obligations

- Ordering: unchanged.
- Tie-breaking/gain acceptance: candidate allowed any positive gain and bounded repeated
  community-label states.
- Floating-point: changed only the gain threshold acceptance floor.
- RNG: unchanged.
- Golden-output verification: before and after SHA files were generated; the after golden
  completed under a 180-second timeout instead of hanging.

## Validation

- `RCH_REQUIRE_REMOTE=1 rch exec -- cargo test -p fnx-algorithms louvain --lib`
  passed on `vmi1156319`, 6 tests passed.
- `RCH_REQUIRE_REMOTE=1 rch exec -- cargo build -p fnx-python --release --features pyo3/abi3-py310`
  passed on `vmi1156319`.

## Verdict

Rejected / evidence-only.

The bounded guard fixed the Pass 5 hang mode, but it did not improve raw parity
(`11/18 -> 11/18`) and the measured timing shift stayed inside noise and below the
Score>=2.0 keep threshold. The Rust hunk was manually reverted.

Next target: coarsened graph edge/order semantics, because first-level neighbor scan
ordering and gain-threshold acceptance have both failed to unlock the remaining
partition-shape gap.
