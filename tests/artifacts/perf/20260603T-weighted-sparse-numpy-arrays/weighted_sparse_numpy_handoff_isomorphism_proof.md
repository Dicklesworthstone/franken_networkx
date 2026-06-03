# Weighted Sparse Native COO NumPy Handoff Proof

- Bead: `br-r37-c1-04z53.14`
- Lever: pre-materialize native weighted COO `rows`, `cols`, and `data` as typed NumPy arrays before `scipy.sparse.coo_array` when the public call is already on the guarded native weighted sparse path.
- Baseline artifact: `before_to_scipy_weighted_float_fnx.jsonl`
- After artifact: `after_to_scipy_weighted_float_fnx.jsonl`
- Hyperfine artifacts: `hyperfine_to_scipy_weighted_float_before.json`, `hyperfine_to_scipy_weighted_float_after.json`

## Profile-Backed Target

The target came from the post-normalized residual profile for `to_scipy_weighted_float` on `barabasi_albert_graph(8000, 4, seed=42)`.

- Baseline sampled hot mean: `0.043261938749007335` s
- Baseline sampled hot median: `0.03782727450015955` s
- Baseline hyperfine process mean: `0.7787739458742857` s
- Baseline hyperfine process median: `0.78684810716` s
- Golden digest: `67df0f0442003e5ba6963b28f9aa88837492b8a9953d9e62550cc3c88ece6a77`
- cProfile signal: `to_scipy_sparse_array` included native adjacency collection, SciPy COO construction, and visible NumPy conversion cost.

## After

- After sampled hot mean: `0.04246290925220819` s
- After sampled hot median: `0.03647070650185924` s
- After hyperfine process mean: `0.7685143486257144` s
- After hyperfine process median: `0.76651673434` s
- Golden digest: `67df0f0442003e5ba6963b28f9aa88837492b8a9953d9e62550cc3c88ece6a77`

The sampled hot median improved from `0.03782727450015955` s to `0.03647070650185924` s. Hyperfine process mean improved from `0.7787739458742857` s to `0.7685143486257144` s.

## Isomorphism And Golden Proof

- Ordering: `native_nodelist` validation is unchanged before the native call, so public nodelist order and row/column labels are preserved.
- Tie-breaking: this path exports a sparse matrix and performs no graph search, ranking, sorting policy change, or tie-break decision.
- Floating point: the native weighted values are copied into a NumPy array with the caller-pinned `dtype`; the after digest is byte-identical to the baseline digest.
- RNG: the library path is deterministic and RNG-free; the benchmark graph uses fixed seed `42`.
- Fallbacks: dtype inference, non-fnx graph objects, multigraphs, non-string weights, and missing native weighted eligibility still use the existing generic path.
- Sparse structure: COO row, column, and data sequences come from the same native adjacency helper; only their container type changes before SciPy consumes them.

Golden sha256 verification is the unchanged digest:

```text
67df0f0442003e5ba6963b28f9aa88837492b8a9953d9e62550cc3c88ece6a77
```

## Score

- Impact: 1
- Confidence: 3
- Effort: 1
- Score: `Impact 1 x Confidence 3 / Effort 1 = 3.0`

The change clears the keep threshold because the hot median and process mean both improve while preserving the golden output.
