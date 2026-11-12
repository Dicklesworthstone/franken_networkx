# br-r37-c1-wxy3x pass 3: CNM final-order semantic fix

Date: 2026-06-13
Worktree: `/data/projects/.scratch/franken_networkx-wxy3x-cnm-boldfalcon-20260613T0015`
Base evidence commit: `555968b8a`

## Change

`fnx_algorithms::greedy_modularity_communities` now sorts final raw communities
like NetworkX's public wrapper: descending community size, then stable
original-node-order tie order.

No merge math, stop condition, PyO3 binding, or Python wrapper route changed in
this pass.

## Proof

Before golden:

```text
e4446c0e162da1c2427beda5cd47f88ac9ea6a8e08c35005bd35d0e7ddb17b40  baseline_golden_v3.json
```

After golden:

```text
7d65bb29fc6d55116fd55f97b39292b1d7c5b8d1993326b22d1986d8fa1a2f19  candidate_golden_pass3.json
```

`sha256sum -c candidate_golden_pass3.sha256` passes.

Raw parity failures reduced from 7 checks to 1. Fixed cases:

- `karate`
- `watts_strogatz_150`
- `path_12`
- `cycle_18`
- `disconnected_components`
- `weighted_edge_attr_guard` explicit weighted raw ordering

Remaining failure:

- `watts_strogatz_300`: NetworkX returns 5 communities; raw Rust returns 6.
  This is a real merge-sequence/stop-shape gap, not final output ordering.

## Benchmark

Hyperfine raw path, same harness:

| Graph | Baseline mean | Candidate mean | Direction |
| --- | ---: | ---: | --- |
| `watts_strogatz_150`, repeat 20 | `0.28956050252s` | `0.31778450238s` | slower/noisy |
| `watts_strogatz_300`, repeat 5 | `0.30137380860s` | `0.25874798630s` | faster/noisy |

The change is kept as a proof-state semantic unlock, not as a production
wrapper route. Public `fnx.community.greedy_modularity_communities` still uses
NetworkX and remains behavior-preserving.

## Verification

- `VIRTUAL_ENV=/data/projects/franken_networkx/.venv PATH=/data/projects/franken_networkx/.venv/bin:$PATH CARGO_TARGET_DIR=.../target-cnm-pass3 rch exec -- maturin develop --release --features pyo3/abi3-py310` passed.
- `/data/projects/franken_networkx/.venv/bin/python -m pytest tests/python/test_community_flow_parity.py::test_greedy_and_girvan_newman_deterministic tests/python/test_community_conformance_matrix.py::test_greedy_modularity_partition_invariants -q` passed: `3 passed`.
- `CARGO_TARGET_DIR=.../target-cnm-pass3 rch exec -- cargo check -p fnx-algorithms --all-targets` passed.
- `cargo fmt --check --package fnx-algorithms` still fails on pre-existing formatting drift elsewhere in `crates/fnx-algorithms/src/lib.rs`; the CNM hunk is already rustfmt-style and was left scoped.
