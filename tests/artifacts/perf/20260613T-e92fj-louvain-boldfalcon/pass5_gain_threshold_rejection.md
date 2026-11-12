# Pass 5 - Louvain Plain Gain-Threshold Lever

Bead: `br-r37-c1-e92fj`

Mission: test the direct NetworkX gain threshold semantics in raw Rust Louvain:
set `LOUVAIN_GAIN_EPS` from `1.0e-12` to `0.0`, leaving all other logic
unchanged.

## Candidate

- Changed only `const LOUVAIN_GAIN_EPS: f64 = 1.0e-12` to `0.0`.
- Did not change RNG, neighbor/community iteration, coarsening, modularity math,
  output ordering, Python wrapper routing, or tests.

## Result

Rejected. The candidate passed the filtered Rust Louvain unit tests, but the
golden corpus hung and had to be terminated. The Rust hunk was reverted and only
this evidence was kept.

## Commands

```bash
timeout 180s rch exec -- cargo test -p fnx-algorithms louvain --lib

VIRTUAL_ENV=/data/projects/franken_networkx/.venv \
PATH=/data/projects/franken_networkx/.venv/bin:$PATH \
CARGO_TARGET_DIR=/data/projects/.scratch/fnx-e92fj-pass5-target \
  rch exec -- /data/projects/franken_networkx/.venv/bin/maturin develop \
  --release --features pyo3/abi3-py310

/data/projects/franken_networkx/.venv/bin/python \
  tests/artifacts/perf/20260613T-e92fj-louvain-boldfalcon/louvain_pass1_harness.py golden \
  --output tests/artifacts/perf/20260613T-e92fj-louvain-boldfalcon/louvain_pass5_gain0_candidate_golden.json \
  --sha-output tests/artifacts/perf/20260613T-e92fj-louvain-boldfalcon/louvain_pass5_gain0_candidate_golden.sha256
```

Validation results:

- Remote `cargo test -p fnx-algorithms louvain --lib`: passed on `vmi1167313`, 6 tests passed.
- Candidate extension rebuild: passed.
- Golden run was terminated after it remained silent for about 90 seconds.
- No candidate golden SHA was produced.

## Isomorphism

- Ordering: unchanged.
- Tie-breaking/gain acceptance: changed to NetworkX-style `best_mod = 0`.
- Floating-point: unchanged except for accepting tiny positive gains.
- RNG seeds: unchanged.
- Golden outputs: unavailable because the candidate hung.

## Next Primitive

Do not use plain `best_gain = 0.0`. The next viable primitive is a bounded
NetworkX-gain variant:

- Keep ordinary NetworkX `gain > 0` acceptance for non-cycling moves.
- Add explicit cycle/no-progress detection for repeated community-tag swaps.
- Prove that the guard is inactive on the current 18-record corpus before using
  it for the pathological tiny-resolution case.
