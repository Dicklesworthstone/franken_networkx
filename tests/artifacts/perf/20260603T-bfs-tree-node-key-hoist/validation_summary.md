# Validation Summary: BFS tree node-key lookup hoist

## Commands
- `rch exec -- cargo check -p fnx-python --features pyo3/abi3-py310`: passed on remote `vmi1153651`
- `rustfmt --edition 2024 --check crates/fnx-python/src/algorithms.rs`: passed
- `rch exec -- .venv/bin/maturin develop --release --features pyo3/abi3-py310`: passed for candidate and restored source
- Direct rch samples: baseline, NetworkX, candidate after, and restored captured
- Hyperfine rch samples: baseline and candidate after captured

## Behavior
Golden SHA remained `f9d0aa036915df76522b43e5f2ed9bcb3539215c9278de3f53d07f2c69905abf` across baseline, NetworkX, candidate, and restored runs.

## Source State
No candidate source change remains. The next pass should attack a deeper native result-representation primitive rather than another node-key dispatch micro-lever.
