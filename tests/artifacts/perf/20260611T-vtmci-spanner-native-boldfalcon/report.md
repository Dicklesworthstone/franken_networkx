# br-r37-c1-vtmci Pass 65 — native `_raw_spanner` baseline/profile

Scope: artifact-only baseline and profile for the unused Rust `_raw_spanner`
kernel. No production source files were edited.

## Build

Built this detached worktree into the project venv:

```bash
VIRTUAL_ENV=/data/projects/franken_networkx/.venv \
PATH=/data/projects/franken_networkx/.venv/bin:$PATH \
rch exec -- maturin develop --release --features pyo3/abi3-py310
```

The build finished successfully at `208882e4d37fdf6238060c01a3aa669e8f15bf52`.
`rch` emitted `exec called with non-compilation command: maturin develop ...`;
the output did not show a remote worker id or an explicit local-fallback line.

Import verification:

- `franken_networkx.__file__`:
  `/data/projects/.scratch/franken_networkx-vtmci-boldfalcon-20260611T1910/python/franken_networkx/__init__.py`
- `franken_networkx._fnx.__file__`:
  `/data/projects/.scratch/franken_networkx-vtmci-boldfalcon-20260611T1910/python/franken_networkx/_fnx.abi3.so`
- `fnx._raw_spanner is fnx._fnx.spanner`: `True`

## Direct Baseline

Command:

```bash
VIRTUAL_ENV=/data/projects/franken_networkx/.venv \
PATH=/data/projects/franken_networkx/.venv/bin:$PATH \
python tests/artifacts/perf/20260611T-vtmci-spanner-native-boldfalcon/harness_spanner_native.py baseline --runs 7
```

Timing scope: prebuilt graph objects; fixture construction excluded.

| Case | Raw native median | Public fnx median | NetworkX median | Raw / NetworkX | Public / NetworkX | Raw / Public |
|---|---:|---:|---:|---:|---:|---:|
| `unweighted_n400_p004_s3` | 19.60 ms | 8.73 ms | 14.90 ms | 0.76x | 1.71x | 0.45x |
| `unweighted_n800_p002_s3` | 52.37 ms | 21.65 ms | 33.99 ms | 0.65x | 1.57x | 0.41x |
| `unweighted_n1500_p001_s3` | 100.77 ms | 44.42 ms | 71.69 ms | 0.71x | 1.61x | 0.44x |
| `weighted_n600_p0025_s4` | 41.84 ms | 33.56 ms | 32.20 ms | 0.77x | 0.96x | 0.80x |

Conclusion: raw native remains slower than NetworkX on every direct fixture, and
roughly 2.2x to 2.4x slower than the current public in-process fnx path on the
unweighted fixtures.

## Hyperfine Baseline

Command:

```bash
VIRTUAL_ENV=/data/projects/franken_networkx/.venv \
PATH=/data/projects/franken_networkx/.venv/bin:$PATH \
hyperfine --warmup 3 --runs 10 \
  --export-json tests/artifacts/perf/20260611T-vtmci-spanner-native-boldfalcon/baseline_hyperfine.json \
  -n raw_native 'python tests/artifacts/perf/20260611T-vtmci-spanner-native-boldfalcon/harness_spanner_native.py bench-one --path raw --case unweighted_n800_p002_s3' \
  -n public_fnx 'python tests/artifacts/perf/20260611T-vtmci-spanner-native-boldfalcon/harness_spanner_native.py bench-one --path public_fnx --case unweighted_n800_p002_s3' \
  -n networkx 'python tests/artifacts/perf/20260611T-vtmci-spanner-native-boldfalcon/harness_spanner_native.py bench-one --path networkx --case unweighted_n800_p002_s3'
```

Process-level timing includes Python startup and imports:

| Command | Mean | Stddev | Min | Max |
|---|---:|---:|---:|---:|
| `raw_native` | 563.3 ms | 24.9 ms | 524.8 ms | 607.1 ms |
| `public_fnx` | 504.8 ms | 24.9 ms | 455.0 ms | 529.1 ms |
| `networkx` | 511.6 ms | 22.8 ms | 470.7 ms | 552.9 ms |

Hyperfine summary: `public_fnx` was 1.12x faster than `raw_native` and 1.01x
faster than `networkx` in this process-level harness.

## Profile

Command:

```bash
VIRTUAL_ENV=/data/projects/franken_networkx/.venv \
PATH=/data/projects/franken_networkx/.venv/bin:$PATH \
python tests/artifacts/perf/20260611T-vtmci-spanner-native-boldfalcon/harness_spanner_native.py profile \
  --case unweighted_n800_p002_s3 --loops 30 --limit 40
```

`cProfile` result for 30 repeated raw-native calls:

| Rank | Frame | Calls | Cumulative |
|---:|---|---:|---:|
| 1 | `{built-in method franken_networkx._fnx.spanner}` | 30 | 1.512 s |
| 2 | `harness_spanner_native.py:282(run_one)` | 30 | 1.512 s |
| 3 | `harness_spanner_native.py:359(target)` | 1 | 1.617 s |

`cProfile` confirms the native PyO3 binding frame accounts for nearly all call
time, but it cannot split Rust internals.

Native sampling:

```bash
VIRTUAL_ENV=/data/projects/franken_networkx/.venv \
PATH=/data/projects/franken_networkx/.venv/bin:$PATH \
samply record --save-only \
  -o tests/artifacts/perf/20260611T-vtmci-spanner-native-boldfalcon/baseline_profile_raw_samply.json \
  -- python tests/artifacts/perf/20260611T-vtmci-spanner-native-boldfalcon/harness_spanner_native.py workload \
  --path raw --case unweighted_n800_p002_s3 --loops 200
```

`samply` captured 11,307 samples on the Python process with one lost event, but
the release extension is stripped, so leaf frames are address-only. The profile
is retained as an artifact, but the actionable hotspot split below is from
source inspection constrained by the cProfile result.

## Structural Proof

Command:

```bash
VIRTUAL_ENV=/data/projects/franken_networkx/.venv \
PATH=/data/projects/franken_networkx/.venv/bin:$PATH \
python tests/artifacts/perf/20260611T-vtmci-spanner-native-boldfalcon/harness_spanner_native.py proof
```

Status: PASS, 10/10 cases.

Proof SHA:

```text
fce14919b113d6b78743abd21df1002c382235ad98c8943680d7c8cc5dbe6856  baseline_proof.json
```

Proof contract:

- Exact spanner edge identity is not required.
- Raw output node set equals input node set.
- Raw output is an undirected simple graph.
- Every raw output edge exists in the input graph.
- Weighted raw output preserves the requested edge weight attribute.
- All-pairs distances satisfy `candidate_distance <= stretch * original_distance`.
- Deterministic graph seeds and spanner seeds were recorded; raw, public fnx,
  and NetworkX output digests were recorded for each case.

Ordering/tie/RNG note: Baswana-Sen is randomized. NetworkX tie behavior depends
on Python object identity and container iteration; raw Rust uses its deterministic
Rust seed path for the supplied integer seed. Digests are recorded for audit, not
used as exact-edge equality requirements.

## Opportunity Matrix

Score formula: `(Impact * Confidence) / Effort`; implement only Score >= 2.0.

| Opportunity | Evidence | Impact | Confidence | Effort | Score | Recommendation |
|---|---|---:|---:|---:|---:|---|
| Replace `residual_graph = graph.clone()` plus repeated `Graph::remove_edge/remove_node` with an adjacency/edge-state working set | Raw is 0.65x NetworkX and 0.41x public fnx on the mid fixture; Rust source clones the full graph then mutates graph storage during every Baswana-Sen round | 4 | 4 | 3 | 5.33 | Next single lever |
| Eliminate per-neighbor `canonical_edge` `String` allocation in `lightest_edge_dicts` and removal loops via edge ids or borrowed canonical keys | Source calls `canonical_edge(node, neighbor)` inside neighbor scans and removal loops; this allocates two owned strings per lookup path | 3 | 4 | 3 | 4.00 | Good follow-up if lever 1 is too broad |
| Replace `BTreeSet<(String, String)>` round buffers with `Vec<EdgeId>` plus deterministic final sort/dedupe | Determinism only needs stable application order; current set insertion clones/sorts string tuples during hot rounds | 3 | 3 | 2 | 4.50 | Viable but must preserve deterministic output order |
| Move clustering/node-rank maps from `HashMap<String, String>` to node-index arrays after graph extraction | Current loop repeatedly clones and hashes node strings for cluster centers | 4 | 3 | 4 | 3.00 | Larger lever, keep as second pass |
| RNG micro-optimization | No profile evidence that RNG dominates; raw is slower in graph/storage-heavy code | 1 | 2 | 2 | 1.00 | Reject for next pass |

Recommended next pass: one lever only, starting with a residual adjacency/edge-state
working set that keeps deterministic final edge order and reuses this proof
harness before/after.
