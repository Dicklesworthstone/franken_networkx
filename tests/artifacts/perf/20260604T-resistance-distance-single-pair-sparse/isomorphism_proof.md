# resistance_distance single-pair sparse solve isomorphism proof

Bead: `br-r37-c1-resistance-distance-single-pair-pinv-bdr8q`

## Observable contract

The lever only affects `resistance_distance(G, nodeA, nodeB, ...)` when both
endpoints are provided. All dict-returning shapes still execute the dense
Laplacian pseudo-inverse path, because those shapes need values derived from
the diagonal of `L^+`.

Ordering and tie-breaking are unchanged:

- `nodelist = list(G.nodes())` remains the node order source.
- Endpoint indices are still derived from that same `nodelist`.
- The return type for the affected branch remains a single `float`.
- There is no RNG or tie-breaking policy inside `resistance_distance`.

Floating-point contract:

- Old formula: `L_pinv[i,i] + L_pinv[j,j] - L_pinv[i,j] - L_pinv[j,i]`.
- New formula: solve the grounded reduced Laplacian with
  `(e_i - e_j)_red`, then return `(e_i - e_j)_red^T x`.
- For a connected graph Laplacian these are the same effective-resistance
  quadratic form. Numerical differences are bounded by golden comparison
  against both the dense exact oracle and NetworkX.

## Golden SHA-256

`bench_resistance_distance.py golden` checks three deterministic cases:

- unweighted sparse Graph pair
- weighted sparse Graph pair with default `invert_weight=True`
- weighted sparse MultiGraph pair with default `invert_weight=True`

Each case is evaluated through current FNX, the dense-pinv oracle, and
NetworkX, rounded to 8 decimal places before digesting.

Result:

```text
golden_before embedded digest = 846e40680ebf4314cd1e5d6c48e96e1fc957e4841ea05f2b034ab53fb9d42f52
golden_after  embedded digest = 846e40680ebf4314cd1e5d6c48e96e1fc957e4841ea05f2b034ab53fb9d42f52
golden_before file sha256     = e051da0ae81ffb3e6ab40ccc7d66466f58659bd209081d2141c166167e87e80d
golden_after  file sha256     = e051da0ae81ffb3e6ab40ccc7d66466f58659bd209081d2141c166167e87e80d
```

`diff -u golden_before.json golden_after.json` is empty.

## Behavior gates

- `py_compile.log`: compiled `python/franken_networkx/__init__.py` and the
  artifact harness.
- `pytest_resistance_distance_after_rebuild.log`: 73 resistance-distance tests
  passed, 442 deselected.
- `ubs_harness_after_pathopen.log`: benchmark harness scan exit 0, 0 critical,
  0 warnings.
- `ubs_touched.log`: full `ubs` on the large shared `__init__.py` plus harness
  was attempted, but the scanner hung and was terminated after several minutes;
  it produced no findings before exit 143.
