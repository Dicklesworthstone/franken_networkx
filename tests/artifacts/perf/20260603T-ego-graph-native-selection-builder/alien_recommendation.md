# Alien Recommendation

The selection-builder candidate lowered Python call count but failed the direct and hyperfine gates. This is the rejected-lever trigger: stop tuning this `ego_graph` construction loop.

Next target class:

- GraphBLAS-style CSR/frontier kernels for algorithms where the output is numeric or list-like rather than a full Python-visible graph object.
- Selection-vector or lazy materialization only where the API can preserve NetworkX observation order without eagerly constructing every node and edge dict.

Target ratio for the next pass: at least `1.3x` direct operation speedup and non-regressing hyperfine on a profile-backed residual.
