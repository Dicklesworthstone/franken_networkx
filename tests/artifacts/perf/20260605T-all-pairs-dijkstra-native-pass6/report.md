# br-r37-c1-04z53.53 pass 6 rejection report

## Target

- Profile-backed bead: `[perf][no-gaps] Native generator-compatible weighted all_pairs_dijkstra residual`.
- Candidate lever: route integer-weight `all_pairs_dijkstra_path_length` through a native Rust implementation instead of delegating to NetworkX.
- Final decision: rejected and backed out. No Dijkstra code change is shipped.

## Benchmark

Command family:

```text
/data/projects/franken_networkx/.venv/bin/python tests/artifacts/perf/20260604T-delegation-goldmine-sweep/bench_delegation_goldmines.py --case all_pairs_dijkstra_weighted --impl {fnx,nx} --repeats 30
```

| Run | Impl | Mean | Median | Stddev |
| --- | --- | ---: | ---: | ---: |
| Baseline | FNX | 2.05861847290s | 2.05707200900s | 0.03259058992s |
| Baseline | NX | 2.22974200830s | 2.24212767950s | 0.10001781065s |
| Native-route trial | FNX | 2.65917294910s | 2.56546468740s | 0.29630557845s |
| Native-route trial | NX | 2.18978837790s | 2.17681395890s | 0.07117818545s |

The native-route trial regressed FNX mean by 29.15% and median by 24.71%, so Score < 2.0. The lever was fully backed out.

## Behavior proof

- Probe digests matched NetworkX and the existing FNX delegate on the representative weighted case.
- Baseline golden artifact sha256: `eae81a71d8de43a730b3d12ff3b1ea367a87cb86cb8c747e22154bcd6c332fbc`.
- Trial golden artifact sha256: `a408485bc547ae8aff0edc27c383d32505fd5b00f535a1735b63896781bdbe65`.
- Ordering and typed key parity passed during the trial, but performance failed the keep gate.

## Next primitive

The next Dijkstra attack must not be raw eager all-pairs materialization. The deeper primitive is an indexed multi-source shortest-path engine with cache-local adjacency, typed node-id interning, and deterministic output materialization only at the Python boundary. Target ratio: 1.3x to 2.0x over the delegate on the weighted all-pairs residual while preserving NetworkX insertion order and numeric behavior.
