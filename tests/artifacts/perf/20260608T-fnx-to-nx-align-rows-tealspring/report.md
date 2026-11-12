# br-r37-c1-f5q2u - fnx_to_nx row-alignment gate

## Lever

Use the native `fnx_to_nx_adjacency` bulk row order as the source order for
`_fnx_to_nx` row alignment when the graph has no z6uka adjacency-cell display
overrides. The new PyO3 getters expose the override state for `Graph` adjacency
rows and `DiGraph` successor/predecessor rows. Mixed hash-equal row overrides
fall back to the existing `list(fg.adj[x])` / `list(fg.pred[x])` path.

## Proof

- Golden proof cases: 4100.
- Proof file hash: `819d3937ddbabcbdc702f163b05087be64416e8b8fc0eab05cc04734a75c0173`.
- Internal corpus SHA: `5b4239ab4257506e18549e295990e957d9dd593050ea4cf339fa4411f564a8e6`.
- Additional gate proof: `proof.json` has 804 cases and zero mismatches.
- Focused pytest: `367 passed`.

Isomorphism: node order, adjacency row order, directed predecessor order, row
display objects, and tie-break inputs match same-call NetworkX snapshots.
Floating point and RNG are not part of the converter; the randomized structural
proof uses fixed seed `0xF5A2`.

## Benchmarks

- Direct convert median: `0.028639510041102767s -> 0.020270652952603996s`
  (`1.41x`).
- Direct planarity median: `0.021865289949346334s -> 0.013972265413030982s`
  (`1.57x`).
- Hyperfine convert mean: `0.44668305728s -> 0.38284449572s` (`1.17x`).
- Hyperfine planarity mean: `0.34678597834s -> 0.34307183644s` (`1.01x`).
- cProfile `_align_rows` cumulative: `0.105s -> 0.018s` in the refreshed
  import-inclusive profile.

Score: `3.2` (`Impact 2.8 * Confidence 4 / Effort 3.5`). Kept.

## Next Route

Reprofile before the next pass. The direct conversion row scan moved down; the
remaining conversion cost is dominated by NetworkX graph construction
(`add_edges_from`) and the native bulk adjacency dump.
