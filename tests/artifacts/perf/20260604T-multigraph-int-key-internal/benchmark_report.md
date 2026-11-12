# Multigraph Int Explicit-Key Internal Storage

Bead: `br-r37-c1-ryruk`

## Baseline

- Direct rch benchmark: FNX `0.23689856544822557s`, NetworkX `0.08767032589013171s`, ratio `2.702152216761535x`.
- cProfile: `_fast_add_explicit_int_edge` `1.000s / 2.012s`, 250000 calls.
- Hyperfine: FNX `1.3025723993400002s +/- 0.09287884168170756s`; NetworkX `0.6918750813399999s +/- 0.02808256126670711s`.

## After

- Direct rch benchmark: FNX `0.19797158788423985s`, NetworkX `0.08987467422331166s`, ratio `2.202751660521625x`.
- Final-build direct confirmation: FNX `0.20116643910943013s`, NetworkX `0.09002397944115931s`, ratio `2.2345872772811024x`.
- cProfile: `_fast_add_explicit_int_edge` `0.777s / 1.493s`, 250000 calls.
- Hyperfine: FNX `1.13044225758s +/- 0.07858973934219864s`; NetworkX `0.7099842360800002s +/- 0.07638180734642724s`.

## Delta

- Direct FNX mean: `0.23689856544822557s -> 0.19797158788423985s` (`1.197x` self-speedup).
- cProfile total: `2.012s -> 1.493s`.
- Native fast path: `1.000s -> 0.777s`.
- Hyperfine FNX mean: `1.3025723993400002s -> 1.13044225758s` (`1.152x` self-speedup).

## Validation

- `cargo fmt --check -p fnx-classes -p fnx-python` passed.
- `rch exec -- cargo test -p fnx-classes multigraph_add_fresh_edge_with_key_unrecorded_preserves_key -- --nocapture` passed.
- `rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310 --all-targets` passed.
- `rch exec -- cargo clippy -p fnx-classes -p fnx-python --features pyo3/abi3-py310 --all-targets -- -D warnings` passed after the formatting/clippy fix.
- `rch exec -- maturin develop --release --features pyo3/abi3-py310` rebuilt the final wheel.
- `key_semantics_golden_after_final_build.py` output matched NetworkX and `sha256sum -c` passed.
