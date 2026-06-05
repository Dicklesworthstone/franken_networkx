# perf: from_dict_of_dicts batched construction (br-r37-c1-nlanb)

## Problem

Simple-Graph `from_dict_of_dicts` ran a per-edge Python loop —
`graph.add_edge(u, v)` + `graph[u][v]` (two adjacency-view __getitem__)
+ `dict.update` per edge — 7.83x slower than nx (sweep n=1500/E=5217;
cProfile showed 2x3000 __getitem__ + 3000 Python add_edge for a
1500-edge dod).

## Lever (one)

Route the exact-`Graph` branch through ONE
`add_edges_from([(u, v, attrs), ...])` call — precisely what nx itself
does — which my pr8q6 attributed batch path commits as a single bulk
insertion. DiGraph / subclasses / multigraph branches keep the inline
loop (their add_edges_from raw paths have different malformed-input
contracts).

Bonus correctness: for a NON-dict attrs value the old loop persisted
the edge before `update()` raised; nx's add_edges_from leaves
nodes-but-no-edge. The batched path now matches nx (error message
exact too).

## Proof (parity_proof.py / parity_proof_HEAD_baseline.stdout)

51-case differential vs nx: 40 round-trip corpora (mixed
int/str/float labels, weighted+plain), isolated nodes, self-loops,
asymmetric input, shared-attr-object aliasing both directions,
malformed input, DiGraph + multigraph_input contracts, node order.

- after-change: 39 passed / 12 failed
- HEAD baseline (same suite, old loop): IDENTICAL 12 failures and
  IDENTICAL golden corpus sha
  226625513aa5801beda427be5269ba16e5239b72013cf6f8dc70371a55e3c913

=> observationally invisible except speed. The 12 failures are the
documented br-r37-c1-z6uka per-adjacency-row display-key architecture
issue (mixed hash-equal int/float keys), which equally affects the old
per-edge loop.

## Bench (interleaved warm min-of-12, n=1500/E=5217)

- from_dict_of_dicts (weighted dod): ~47ms -> 15.3ms; 7.83x -> 2.85x
  vs nx (2.7x self)
- plain dod (no attrs, 2000 edges): 2.55x
- residual = add_edges_from batch-path substrate (canonicalization +
  PyDict mirrors + CGSE dual-rep, br-r37-c1-w1dm8 / 71x9k)

## Validation

- tests/python/test_from_dict_of_dicts_batch_parity.py: 10 passed
- full tests/python suite: 21363 passed; 6 failures identical to HEAD
  (pre-existing)
- Python-only change; .so unchanged from HEAD build
- HEAD-baseline comparison run via overlay package
  (HEAD __init__.py + worktree submodules)
