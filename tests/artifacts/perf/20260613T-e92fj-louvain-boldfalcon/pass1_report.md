# br-r37-c1-e92fj Pass 1: Louvain Baseline And Oracle

Date: 2026-06-12
Agent: BoldFalcon
Target: `franken_networkx.community.louvain_communities`

## Commands

- Build: `VIRTUAL_ENV=/data/projects/franken_networkx/.venv PATH=/data/projects/franken_networkx/.venv/bin:$PATH CARGO_TARGET_DIR=/data/projects/.scratch/fnx-e92fj-boldfalcon-target rch exec -- /data/projects/franken_networkx/.venv/bin/maturin develop --release --features pyo3/abi3-py310`
- Golden: `/data/projects/franken_networkx/.venv/bin/python tests/artifacts/perf/20260613T-e92fj-louvain-boldfalcon/louvain_pass1.py golden`
- Loop baselines: `/data/projects/franken_networkx/.venv/bin/python tests/artifacts/perf/20260613T-e92fj-louvain-boldfalcon/louvain_pass1.py loop --case ws150 --variant <variant>` and `--case ws300`
- Process baselines: `rch exec -- hyperfine --warmup 3 --runs 50 --export-json baseline_hyperfine_ws150.json ...`
- Profiles: `/data/projects/franken_networkx/.venv/bin/python tests/artifacts/perf/20260613T-e92fj-louvain-boldfalcon/louvain_pass1.py profile --case ws300 --variant <variant>`

Notes:
- `rch exec` accepted the commands, but warned that `hyperfine` is not a compilation command. Treat those hyperfine runs as local process-level routing evidence.
- The first build attempt reused the shared cargo target and produced an extension with unresolved Rust symbols. The retained build used the isolated `CARGO_TARGET_DIR` above and imports cleanly.

## Golden Oracle

Golden file: `baseline_golden.json`

Golden sha256:

```text
47785bab96bfc07a19976caa127d3f50699a5f22b833f8c33b0823935f881f09  baseline_golden.json
```

Verification:

```text
baseline_golden.json: OK
```

Sample coverage:

| Case | Public FNX equals NX original | Public FNX equals NX parity graph | Raw Rust equals public |
| --- | --- | --- | --- |
| `karate` | true | true | false |
| `ws150` | true | true | false |
| `ws300` | true | true | false |
| `ba300` | true | true | false |
| `ws150_weighted` | true | true | false |
| `ws150_resolution` | true | true | false |

Representative partition digests:

| Case | Public digest | Raw Rust digest |
| --- | --- | --- |
| `ws150` | `e5be6cd30b6110a89d335f45918fc09c47052f1853cd4ec922c6ba070151bb51` | `431945e45fd4895635d52978b2f826794d9bbc0e1d8c890566f434a1acc3f477` |
| `ws300` | `541d40853e2d6abc0ef40ad863edfaad96d1e4dc64020ee31029c05af34b3ad8` | `df2bcbccfcbf1132723a34dd838f181c8fc3bbd2980313fedc51707d584fc914` |

Isomorphism verdict:
- Public FNX preserves the NetworkX-observable ordering, tie-breaking, weighted, resolution, and seeded RNG behavior for these samples.
- The existing raw Rust kernel is much faster, but it does not preserve the public oracle. It cannot be routed until pass 2 maps and fixes the semantic deltas.

## Baseline Results

In-process loop medians:

| Case | Variant | Median seconds | Relative to public |
| --- | --- | ---: | ---: |
| `ws150` | `fnx_public` | 0.0066674795 | 1.00x |
| `ws150` | `nx_original` | 0.0058010135 | 1.15x faster than public |
| `ws150` | `nx_parity` | 0.0067698385 | 0.98x |
| `ws150` | `fnx_raw` | 0.0012213035 | 5.46x faster than public, not parity-safe |
| `ws300` | `fnx_public` | 0.0132025430 | 1.00x |
| `ws300` | `nx_original` | 0.0112374260 | 1.17x faster than public |
| `ws300` | `nx_parity` | 0.0136581715 | 0.97x |
| `ws300` | `fnx_raw` | 0.0031249140 | 4.22x faster than public, not parity-safe |

Hyperfine process means:

| Case | Variant | Mean seconds | Note |
| --- | --- | ---: | --- |
| `ws150` | `fnx_public` | 0.2884554448 | startup dominated |
| `ws150` | `nx_original` | 0.2891623914 | startup dominated |
| `ws150` | `fnx_raw` | 0.2699400075 | 1.07x process-level vs public |
| `ws300` | `fnx_public` | 0.3251657635 | startup dominated |
| `ws300` | `nx_original` | 0.3228361983 | startup dominated |
| `ws300` | `fnx_raw` | 0.2750492576 | 1.18x process-level vs public |

## Profile Summary

`fnx_public` on `ws300`, 10 repeats:

- Total: 0.336 s
- `community.py:225(louvain_communities)`: 0.287 s cumulative
- NetworkX `louvain.py:14(louvain_communities)`: 0.243 s cumulative
- NetworkX `_one_level`: 0.101 s cumulative
- `_networkx_graph_for_parity`: 0.044 s cumulative
- `backend.py:_fnx_to_nx`: 0.042 s cumulative

`fnx_raw` on `ws300`, 10 repeats:

- Total: 0.055 s
- Raw binding call: 0.007 s cumulative
- Benchmark graph generation and graph loading dominate the remaining time.

## Candidate Ranking

| Candidate | Impact | Confidence | Effort | Score | Decision |
| --- | ---: | ---: | ---: | ---: | --- |
| Exact-parity native/index-space Louvain route | 5 | 4 | 4 | 5.0 | Next, but only after semantic map |
| Conversion-tax trim for parity graph delegation | 2 | 4 | 2 | 4.0 | Lower ceiling; defer behind exact native route |
| Python accessor micro-tuning around delegated Louvain | 1 | 3 | 2 | 1.5 | Reject for now |

Pass 2 target: explain and close the raw Rust semantic gap against NetworkX seed shuffle, community iteration order, resolution handling, weighted edge handling, threshold/max-level behavior, and final partition ordering.
