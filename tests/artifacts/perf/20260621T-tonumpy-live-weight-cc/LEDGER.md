# to_numpy_array weighted dirty-case — live edge_py_attrs COO (skip AttrMap sync)

- Agent: `CopperCliff` · 2026-06-21 · MEASURED · **SHIP (gap-narrowing, not domination)**
- Files: `crates/fnx-python/src/readwrite.rs` (+`adjacency_arrays_live`), `python/franken_networkx/__init__.py` (to_numpy_array weighted path)

## Diagnosis
`to_numpy_array(weight="weight")` looked 0.57x vs nx at n=1200, BUT that was a
benchmark artifact of POST-CONSTRUCTION weight mutation (`G[u][v]['weight']=w`),
which sets `edges_dirty`. Two regimes:
- **construction-set weights (not dirty):** the `_fnx_sync_edge_attrs_to_inner`
  call self-gates (early-returns on `!edges_dirty`), so no sync fires and fnx
  reads `inner` directly — **already beats nx** (n=700 1.13ms vs nx 1.31ms = 1.27x;
  DiGraph 1.45x). UNTOUCHED by this change.
- **mutated weights (dirty):** sync rebuilds the ENTIRE Rust AttrMap
  (`py_dict_to_attr_map` + `replace_edge_attrs` over every edge) just to read one
  `weight` key back via `adjacency_arrays`. THIS is the cost: ~0.64x vs nx.

## Lever
New `adjacency_arrays_live` (readwrite.rs) walks the same `inner` edge order
(nx order) but resolves each weight from the live `edge_py_attrs` mirror dict,
falling back to `inner` when no mirror exists — eliminating the AttrMap rebuild.
Byte-identity is by construction: the mirror value is routed through the SAME
`py_value_to_cgse(..).as_f64()` the sync path uses (so bool→1/0, int, float incl
NaN/inf, Rust-parsed numeric strings, Map→default all match exactly). Wrapper
gates on the `edges_dirty` token so the already-faster not-dirty path is intact.

## Measured (warm min-of-15, gnm n*4 edges, this host)
| case | OLD(sync) | NEW(live) | nx | new/old | new/nx |
|------|-----------|-----------|----|---------|--------|
| N=700  Graph   | 2.047ms | 1.422ms | 1.307ms | **1.44x** | 0.92x |
| N=700  DiGraph | 1.601ms | 0.947ms | 0.883ms | **1.69x** | 0.93x |
| N=1500 Graph   | 5.478ms | 4.011ms | 3.295ms | **1.37x** | 0.82x |
| N=1500 DiGraph | 4.492ms | 2.829ms | 2.465ms | **1.59x** | 0.87x |
| N=3000 Graph   | 49.99ms | 43.48ms | 42.15ms | 1.15x | 0.97x |
| N=3000 DiGraph | 48.08ms | 40.48ms | 38.07ms | 1.19x | 0.94x |

## Honest verdict
This is a **strict self-improvement** of the dirty path (1.15–1.69x faster than
the prior fnx sync path), narrowing the nx gap from ~0.64x to ~0.82–0.97x.
It does **NOT dominate** nx in the dirty case: the residual is the per-edge
Python-dict boundary cost (`edge_py_attrs` HashMap lookup + `PyDict.get_item`)
that nx's single-representation `for u,v,d in G.edges(data=True): A[i,j]=d.get(w)`
loop avoids. The construction-set common case already dominates (1.27–1.45x).
NEGATIVE EVIDENCE: the dirty-case to_numpy_array ceiling cannot be pushed past
nx via the dual Rust-inner + Python-mirror substrate without a single canonical
weight store; logged so no peer re-attempts a "beat nx" route here.

## Correctness proof (`verify.py`)
- 64/64 byte-identical: live(dirty) == inner(not-dirty) across {int,float,bool,
  numeric-str,non-parseable-str,NaN,inf,half-missing} × {Graph,DiGraph} × nonedge
  {0,-1} × dtype {f64,f32}.
- 48/48 byte-identical fnx==nx for numeric kinds (strings excluded: nx raises on
  string weights — a PRE-EXISTING fnx-vs-nx divergence preserved unchanged).
- custom nodelist + custom weight key: fnx==nx.
- Conformance: 1011 passed across to_numpy/lazy-materialization-stress/conversion/
  matrix-nodelist/pandas/io suites. 3 unrelated failures (pagerank personalization,
  gexf classification, import version) FAIL identically on the baseline install —
  pre-existing, untouched by this change.
