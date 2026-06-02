# Alien Recommendation Card - br-r37-c1-wqtfe

## Intake
- Project: FrankenNetworkX / Python sparse matrix export
- Workload: `to_scipy_sparse_array(G, dtype=float, weight="weight")` on BA(8000, 4)
- Symptom: vs-upstream gap caused by per-edge Python/PyO3 adjacency materialization
- Baseline artifact: `hyperfine_old_native_nx.json`
- Profile artifacts: `cprofile_old.txt`, `cprofile_native.txt`
- Correctness constraints: CSR shape, dtype, indptr, indices, data bytes, nodelist ordering, default missing-weight value, post-creation attr mutation visibility, and dtype-inference behavior

## Hotspot
| Rank | Location | Metric | Value | Evidence |
|---|---|---:|---:|---|
| 1 | Python fallback `to_scipy_sparse_array` | wall time | 3.570 s for 8 conversions | `hyperfine_old_native_nx.json` |
| 2 | `_atlas` / `__getitem__` Python adjacency materialization | cumulative profile | 0.734 s / 0.730 s in 3-conversion profile | `cprofile_old.txt` |
| 3 | Native `_fnx.adjacency_arrays` | cumulative profile | 0.072 s in 3-conversion profile | `cprofile_native.txt` |

## Primitive Match
- Graveyard primitive: contiguous array / zero-allocation hot path, avoiding per-element boundary crossing.
- Alien-artifact translation: compile the sparse matrix export into deterministic COO arrays `(rows, cols, data)` in Rust storage order, then let SciPy canonicalize to the requested sparse format.
- Adoption wedge: only `weight` as a string and explicit `dtype`, where the native f64 data array is observationally pinned by the caller's dtype.

## EV Gate
| Candidate | Impact | Confidence | Reuse | Effort | Adoption Friction | EV |
|---|---:|---:|---:|---:|---:|---:|
| Native weighted COO when dtype is pinned | 5 | 5 | 5 | 1 | 1 | 125.0 |
| Broaden to dtype=None weighted path | 4 | 2 | 5 | 3 | 3 | 4.4 |

Chosen lever: native weighted COO only when the caller pins `dtype`.

## Fallback
- Trigger: any CSR byte mismatch, dtype mismatch, mutation-staleness failure, or performance regression below score gate.
- Fallback: route weighted calls back through the existing Python fallback.

## Proof Obligations
- Old fallback, native path, and upstream NetworkX CSR byte digests must match.
- `dtype=None` remains on the Python fallback so NetworkX's int-vs-float dtype inference is preserved.
- Multigraphs and non-string weight keys remain on the existing Python path.
- `_sync_rust_edge_attrs(G)` runs before native weighted export, preserving post-creation edge-attribute mutation visibility.
- No ordering/tie-breaking/RNG behavior changes; floating-point values are the same values cast through the caller-pinned dtype.
