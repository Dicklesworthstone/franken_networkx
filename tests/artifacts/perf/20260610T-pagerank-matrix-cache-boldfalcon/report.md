# Weighted PageRank Matrix Cache

Bead: `br-r37-c1-04z53.73`

## Target

After `br-r37-c1-04z53.72`, no ready `[perf]` child bead existed. A fresh sparse-matrix sweep showed no residual sparse-conversion gap. The next profile-backed target was weighted PageRank on the deterministic metadata-heavy `DiGraph` from `20260610T-pagerank-edge-sync-boldfalcon/harness_pagerank_edge_sync.py`.

Baseline warmed cProfile for `n=1400`, `5600` edges, `100` FNX calls:

- public `pagerank`: `0.362s`
- `_pagerank_scipy`: `0.333s`
- SciPy sparse matmul/construction dominates; `adjacency_default_order_arrays` still appears at `0.018s`

## Lever

Cache the normalized SciPy row-stochastic PageRank matrix, `nodelist`, and dangling-node index array on exact `Graph`/`DiGraph` instances. The cache key is `(type(G), weight, nodes_seq, edges_seq)` and is only used when the native token reports `edge_attrs_dirty == False`.

This is one lever: eliminate repeated normalized sparse-matrix construction for repeated PageRank calls on the same clean graph. The NumPy/SciPy power-iteration loop is unchanged.

## Benchmark

RCH-wrapped hyperfine, 15 runs, 3 warmups, 80 calls/process:

- FNX: `615.417936ms +/- 22.440785ms -> 505.507236ms +/- 19.009133ms`
- NetworkX: `721.807527ms +/- 23.987695ms -> 720.194183ms +/- 32.930038ms`
- FNX self-speedup: `1.217x`
- FNX vs NetworkX: `1.17x faster -> 1.42x faster`

After profile for `100` calls:

- public `pagerank`: `0.232s`
- `_pagerank_scipy`: `0.208s`
- `adjacency_default_order_arrays` and COO construction are gone from the hot list after the first cache fill.

## Proof

Baseline and after proof files are byte-identical:

- proof file sha256: `6eccc9abe6819e4e1fa1e6a1672a07a87a3d82d0e8b3b5bc3c644940c2f4ba3b`
- embedded proof SHA: `c66ea1ffb099ce950ce1c1a069354f76290dc838a6c60479547150f46c358b7f`
- clean PageRank SHA: `8fb324f959a9872543ac098c3558dee9c793e932e5c1b0ee64f416daedb82bb8`
- dirty-edge PageRank SHA: `8d0ac324f42c1977694df98fa9f1f107e4e28d05e8beed1987b7a29714fa6de3`

Additional cache invalidation proof:

- first call populates cache, then edge weights are mutated and a new edge is added on the same graph
- first and second FNX outputs match NetworkX exactly
- invalidation proof SHA: `042ab783b58ca21dc29cc9559de460b0f18a94640794b326083c58cc5a2e5ef3`

Ordering is still `dict(zip(list(G), x))`. Tie-breaking remains unused. Floating point uses the same SciPy sparse power iteration after the cached normalized CSR matrix is built by the original path. RNG is deterministic fixture construction only.

## Gates

- `py_compile python/franken_networkx/__init__.py`: passed
- RCH `cargo check -p fnx-python --all-targets --features pyo3/abi3-py310`: passed with existing `fnx-generators` warnings
- focused PageRank pytest selector: `37 passed`
- `git diff --check`: passed
- UBS on `python/franken_networkx/__init__.py`: attempted and stopped after hanging without analyzer output
- bounded UBS on touched test/evidence files: passed with `0` criticals and `0` warnings

## Verdict

PRODUCTIVE / kept. Score `4.0` (`Impact 3.0 x Confidence 4.0 / Effort 3.0`).
