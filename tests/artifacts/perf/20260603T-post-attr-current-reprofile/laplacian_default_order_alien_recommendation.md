# Next Primitive Recommendation

## Graveyard Match

The current matrix residual maps to GraphBLAS / sparse linear algebra (§10.5) and cache-aware/succinct graph storage (§7.1, §7.2): graph kernels should operate on CSR/COO index arrays without rebuilding Python nodelists or string-key maps when insertion-order node indices are already available.

## Current Lever

Use the existing default-order COO helper for laplacian default-order construction. This removes generic Python nodelist canonicalization and string-to-index lookup from the profiled path.

## Next Target

After this commit, re-profile sparse matrix exports. If `normalized_laplacian_matrix` still shows the same generic helper cost, the next single lever is the same default-order helper route there. If SciPy conversion or NumPy concatenation becomes dominant, the next deeper primitive is a native CSR builder that emits `indptr`, `indices`, and `data` directly for `D - A`, then constructs `scipy.sparse.csr_array` without COO concatenation.
