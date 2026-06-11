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
