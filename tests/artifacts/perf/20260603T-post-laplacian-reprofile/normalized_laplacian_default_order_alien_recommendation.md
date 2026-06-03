# Next Primitive Recommendation

The current lever removes the default-order nodelist-index membrane for normalized Laplacian. If sparse matrix exports remain a residual hotspot after reprofile, the next deeper primitive should be a native default-order CSR builder for Laplacian-family matrices:

- emit `indptr`, `indices`, and `data` directly in safe Rust for exact `Graph` default order;
- construct diagonal and off-diagonal entries in CSR order without Python COO arrays or SciPy COO-to-CSR conversion;
- preserve NetworkX observable sparse shape, dtype, ordering, self-loop treatment, missing-weight fallback, and explicit-nodelist behavior;
- keep weighted-present graphs on the existing fallback until a separate profile-backed weighted CSR builder is proven.

This maps to the alien-graveyard GraphBLAS/CSR and cache-oblivious sparse-kernel primitive family rather than another Python-loop micro-tweak.
