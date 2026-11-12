# chain_decomposition native DFS-cycle-forest primitive

Bead: br-r37-c1-r4gg6

Target: profile-backed residual after resistance_distance landed. The delegated
FNX wrapper had a matching output digest but spent its hot path converting the
FNX graph to NetworkX and then running NetworkX's Python chain implementation.

Baseline:

- RCH hyperfine command: `chain_decomposition --impl fnx --repeats 50`
- Process-level mean: 0.4122783079 s
- cProfile, 500 calls: 3.334 s in `case_chain_decomposition`; 1.443 s in
  `_call_networkx_for_parity` / conversion; 1.856 s in NetworkX
  `chains.py:chain_decomposition`.
- Stable output digest: `4929d2c6d3c2bbdba133dcebf95c08db9f066bb46e5af63428e1be7e9528c84e`

After:

- RCH hyperfine command: same command, same repeats.
- Process-level mean: 0.3125639304 s, 1.319x command-level speedup.
- In-process sweep: FNX 0.0000774610 s vs NetworkX 0.0013528421 s,
  FNX/NX ratio 0.05726 (17.47x faster than NetworkX for the measured call).
- Same-workload before/after in-process FNX: 0.0022143446 s -> 0.0000774610 s,
  28.59x faster.
- After cProfile, 500 calls: benchmark is dominated by digest serialization;
  NetworkX conversion and NetworkX chain code are absent from the hot path.
- Stable output digest: `4929d2c6d3c2bbdba133dcebf95c08db9f066bb46e5af63428e1be7e9528c84e`

Score: Impact 5.0 x Confidence 0.95 / Effort 2.0 = 2.375.

Validation:

- `cargo fmt --check -p fnx-algorithms -p fnx-python`: pass.
- `rch exec -- cargo test -p fnx-algorithms chain_decomposition --lib`: pass,
  3 tests.
- `rch exec -- cargo check -p fnx-python --lib`: pass.
- `rch exec -- cargo clippy -p fnx-algorithms --lib -- -D warnings`: pass.
- `rch exec -- cargo clippy -p fnx-python --lib -- -D warnings`: pass.
- `maturin develop --release --features pyo3/abi3-py310` under `rch exec`:
  pass/install.
- Focused pytest for chains and eager rejection parity: pass, 9 tests.
- `python -m py_compile python/franken_networkx/__init__.py`: pass.
- UBS timed out without findings: combined touched-file scan 60s, Rust-only
  scan 60s, Python-only scan 180s. Logs and exit-code files are in this
  artifact directory.
