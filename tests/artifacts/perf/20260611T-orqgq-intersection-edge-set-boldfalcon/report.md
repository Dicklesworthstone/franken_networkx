# br-r37-c1-orqgq native intersection edge-set attempt

## Target

After `br-r37-c1-zvwgo`, local residual profiling on `83312c9b3` showed
`intersection_all` still dominated by Python set construction:

- `intersection_all`: `0.728s` over 200 calls
- reverse-edge `set.update`: `0.224s`
- reverse-edge generator: `0.085s`
- native node insertion: `0.102s`
- native edge insertion: `0.092s`

## Lever Tried

Add a native simple-`Graph` helper that constructs the exact NetworkX edge-set
shape for `intersection_all`: insert `G.edges()` tuples into a CPython set,
snapshot `list(set)` order, then add reversed tuples in that same order.

The Python call site was guarded to exact `Graph`; directed, multigraph, and
subclass paths stayed on the original implementation.

## Proof

The candidate preserved output signatures:

- `sparse_intersection` SHA unchanged and matches NetworkX:
  `a8ad08618e39d836fcdff54f962a7b4bfb8fe7c4b5942247ea9a0dbb0aaea13a`
- `equal_node_intersection` SHA unchanged and matches NetworkX:
  `52b3d4e1dc170964728fa0281d3a0232004b5079aee74fc60684256a958bedde`

Ordering, hash-equal node display, tie behavior, and edge tuple direction were
preserved. There is no floating-point or RNG surface.

## Performance

Correct local baseline before this lever is the previous current-main residual:

- Sparse intersection best: `8.0570ms`
- Sparse intersection median: `8.1791ms`
- Whole-process hyperfine mean: `280.252ms`

Corrected local candidate results:

- Sparse intersection best: `52.6146ms`
- Sparse intersection median: `56.2396ms`
- Equal-node intersection best: `0.3306ms`
- Equal-node intersection median: `0.3377ms`
- Whole-process hyperfine mean: `486.712ms`
- cProfile: `_native_intersection_edge_set` alone cost `2.264s` over 440 calls

## Verdict

REJECTED. Score `0.0`.

The PyO3/PySet tuple construction route preserved semantics but moved the hot
loop into expensive per-edge Python C-API calls. It is worse than CPython's
native set/generator path and must not ship.

## Next Route

Do not retry PySet construction from Rust. The next deeper primitive should
avoid materializing the doubled edge set at all: compute exact intersection
membership against the second graph while replaying the first graph's
NetworkX-equivalent set order, or build the output graph directly from a
compact ordered edge witness. That route needs a fresh proof because CPython set
iteration order is the contract.

---

# br-r37-c1-0pn4p compact ordered witness keep

## Target

Follow the rejected native PySet route with a Python-level Graph-only fast path
for the profiled two-graph `intersection` case. The target is the doubled
undirected edge-set construction inside `intersection_all`, not graph
construction or NetworkX comparison overhead.

## Lever Kept

For exact simple `Graph` inputs, build the output directly from:

- the node intersection,
- the original left-edge set for membership,
- a compact right-hand ordered edge witness containing right edges plus their
  reversed aliases.

This preserves the same display objects, edge tuple direction, and CPython
set-order behavior observed from the old two-graph `intersection_all` path while
avoiding the doubled left-side edge set.

Directed graphs, multigraphs, subclasses, and `intersection_all` stay on the
original implementation.

## Proof

`candidate_blackthrush_proof.json` compares FrankenNetworkX against NetworkX and
against the current-main golden output:

- `sparse_intersection`: `a8ad08618e39d836fcdff54f962a7b4bfb8fe7c4b5942247ea9a0dbb0aaea13a`
- `equal_node_intersection`: `52b3d4e1dc170964728fa0281d3a0232004b5079aee74fc60684256a958bedde`

An additional randomized probe checked 250 undirected `Graph` intersection cases
against NetworkX with identical insertion sequences.

No floating-point or RNG surface is involved.

## Performance

Baseline artifacts were captured on current `main` before the lever:

- cProfile prebuilt sparse graph, 200 calls: `0.920s`
- broad hyperfine mean: `0.36373667296000006s`

Candidate artifacts:

- cProfile prebuilt sparse graph, 200 calls: `0.663s`
- broad hyperfine mean: `0.35360194965999997s`
- focused A/B `n=1800`: median `3.154788ms -> 2.712851ms`, `1.16x`
- focused A/B `n=5000`: median `14.435411ms -> 11.432219ms`, `1.26x`

The broad whole-process benchmark remains noisy because it includes graph
construction and NetworkX timing; the focused A/B isolates the profiled residual.

## Verdict

KEPT. Score `3.0`: moderate target impact, high confidence from golden parity
and two focused sizes, low implementation complexity.
