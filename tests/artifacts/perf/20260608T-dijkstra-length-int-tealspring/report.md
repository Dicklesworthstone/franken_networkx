# br-r37-c1-1kor1 weighted Dijkstra length-only typed cutoff proof

## Lever

Move `single_source_dijkstra_path_length` onto a native length-only Dijkstra
path that emits NetworkX-observable Python `int` or `float` distances directly
and applies `cutoff` during relaxation. The old public wrapper materialized full
paths through `single_source_dijkstra`, then repaired distance types in Python.

The new kernel keeps:

- finalize-order emission for NetworkX dict key order,
- predecessor rows for mixed hash-equal display objects,
- per-path integer type tracking for int/bool/default weights,
- NetworkX cutoff semantics for finite, negative, `NaN`, and `+inf` cutoffs.

## Baseline

Current public implementation before the lever:

- Direct proof mean, public FNX: `0.011283117975108326s`.
- Direct proof mean, raw native: `0.007235832617152482s`.
- Direct proof mean, NetworkX: `0.009473288835336765s`.
- Public golden SHA: `fbad62d38556c3e346ac8cc54b38078b5a400ad944ed2784647f637ecfb88cc5`.
- Raw golden SHA: `b99bf55f47386413df0c96d7cc79d00a5cad7af9122548a3037f1cb6ec75f09b`.

The old raw binding was faster in-process but failed parity because it emitted
float distances and rejected `cutoff=...`.

## After

Final candidate after release rebuild:

- Direct proof mean, public FNX: `0.005353930596417437s` (`2.107x` faster).
- Direct proof mean, raw native: `0.004409636231139302s`.
- Direct proof mean, NetworkX: `0.010927795913691323s`.
- Public golden SHA: `fbad62d38556c3e346ac8cc54b38078b5a400ad944ed2784647f637ecfb88cc5`.
- Raw golden SHA: `fbad62d38556c3e346ac8cc54b38078b5a400ad944ed2784647f637ecfb88cc5`.

Looped hyperfine, 50 calls per process, same rebuilt extension:

- Old full-path public emulation: `1.3301393244600002s`.
- New public length-only API: `0.95504693876s` (`1.393x` faster).
- Raw length-only API: `0.9463577536599999s`.
- NetworkX: `1.1383155886599998s`.

Single-call process hyperfine stayed noisy and is retained as an artifact; it is
dominated by Python startup and fixture construction. The looped process
benchmark and direct in-process proof isolate the actual optimized path.

## Parity

- Public and raw length APIs match NetworkX row order, Python distance types,
  and values on the BA-style weighted fixture.
- Public and raw length APIs match NetworkX for undirected and directed cutoff
  cases: `None`, `1`, `2`, `-1`, `NaN`, `+inf`.
- Negative, nonnumeric, and positive-infinity edge weights still trigger the
  public NetworkX delegation gate.
- Focused pytest: `tests/python/test_dijkstra_length_typed_cutoff.py` passed.

## Gates

- `rch exec -- cargo check -p fnx-algorithms --all-targets`
- `rch exec -- cargo check -p fnx-python --all-targets --features pyo3/abi3-py310`
- `rch exec -- maturin develop --release --features pyo3/abi3-py310`
- `cargo fmt --check -p fnx-algorithms -p fnx-python`
- `rch exec -- cargo clippy -p fnx-algorithms --all-targets -- -D warnings`
- `rch exec -- cargo clippy -p fnx-python --all-targets --features pyo3/abi3-py310 -- -D warnings`
- `rch exec -- python3 -m pytest -q -p no:cacheprovider tests/python/test_dijkstra_length_typed_cutoff.py`
- `ubs` small Python harness/test scan: no critical or warning issues.
- `ubs` Rust scan returned nonzero only for broad pre-existing findings outside
  this patch, including a pre-existing equality warning at
  `crates/fnx-algorithms/src/lib.rs:33234`.

Score: `Impact 2.1 * Confidence 0.9 / Effort 0.85 = 2.2`. The same lever also
removes the raw parity blocker and makes the public API faster than NetworkX on
the target. Kept.
