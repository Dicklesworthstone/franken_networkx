# br-r37-c1-04z53.30 Isomorphism Proof

## Candidate Scope

The rejected candidate changed only the exact simple-Graph empty-edge copy path inside `ego_graph`. It was tested with the same deterministic BA(3000, 4, seed=42) graph used by the baseline.

## Golden Output

All sampled outputs kept the same digest:

`a66fe1d2d36fe1f69a5966fab6d739d8b5b34ed0aae622b17565fbba8ce603d6`

Matching samples:

- NetworkX oracle baseline
- fnx baseline
- fnx candidate direct sample
- fnx baseline profile sample
- fnx candidate profile sample

## Ordering, Tie-Breaking, Floating Point, RNG

- Node order stayed tied to the original `G.nodes()` insertion order filtered to the ego set.
- Edge order stayed tied to source edge insertion order for the benchmark graph.
- No traversal frontier or tie-break policy changed.
- No floating-point operation changed in the unweighted benchmark path.
- RNG behavior was unchanged; graph generation kept seed `42`.

## Rejection

Behavior was preserved, but performance did not improve. Direct rch sample regressed by 3.69 percent and hyperfine regressed by 8.32 percent. Candidate source was removed after measurement.
