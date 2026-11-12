# assortativity submodule — route to optimized fnx top-level (3.4-8.3x vs old path)

## Problem
`networkx.algorithms.assortativity` (reachable as `fnx.algorithms.assortativity`,
`fnx.assortativity`, and the `from ... import` path) was aliased verbatim to
networkx's module. Several functions did NOT dispatch to the fnx backend, so
they ran nx's pure-Python code against the fnx graph's degree/adjacency views:

| function (n=1500, deg~15)               | old submodule | fnx top-level |
|-----------------------------------------|---------------|---------------|
| degree_pearson_correlation_coefficient  | 52 ms         | 9 ms          |
| attribute_assortativity_coefficient     | 29 ms         | 4.5 ms        |
| degree_mixing_matrix                    | 34 ms         | 5.8 ms        |
| attribute_mixing_matrix                 | 27 ms         | 6.5 ms        |

## Lever
Add an `assortativity.py` shim (proven centrality/distance_measures pattern):
rebind every name networkx aliases to top level (`getattr(nx,name) is
submodule_fn` guard) to the `franken_networkx` top-level optimized impl;
register in the uncontested `algorithms/__init__.py`. No Rust change; the
contested mid-refactor `__init__.py` is untouched.

## Result
| function                                | vs old submodule | vs genuine nx |
|-----------------------------------------|------------------|---------------|
| degree_pearson_correlation_coefficient  | 3.4x             | 1.44x         |
| attribute_assortativity_coefficient     | 6.8x             | 1.37x         |
| degree_mixing_matrix                    | 8.3x             | 2.69x         |
| attribute_mixing_matrix                 | 4.4x             | 0.90x (parity)|

## Proof
- Routing identity: `fnx.algorithms.assortativity.X is fnx.X` for all 7 routed
  fns (degree/attribute/numeric assortativity, mixing matrices,
  average_neighbor_degree); import path routes too.
- Parity vs genuine nx over **120 adversarial graphs** (barabasi/powerlaw/watts/
  gnp — wide degree ranges stress the order-sensitive mixing-matrix layout):
  **0 fails** across all 6 checked functions incl. `degree_mixing_matrix` /
  `attribute_mixing_matrix` (`np.allclose` on full matrices, also
  `normalized=False`). The memory's "vectorized mixing matrix fails order" was a
  version never shipped; fnx top-level is the correct order-preserving one.
- `tests/python -k "assortativity or mixing or pearson or neighbor_degree"`:
  614 passed, 0 failed.
