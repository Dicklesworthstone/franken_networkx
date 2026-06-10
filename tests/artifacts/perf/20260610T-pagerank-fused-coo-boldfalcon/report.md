# br-r37-c1-04z53.71 rejection report

## Target

Post-`br-r37-c1-f2ohl` cProfile for weighted `pagerank` moved the hotspot out of
edge-attr sync and left two adjacent wrapper costs:

- `_pagerank_needs_networkx_weight_parity`: `0.026s / 80 calls`
- `_fnx.adjacency_default_order_arrays`: `0.020s / 80 calls`

Candidate lever: fuse finite/nonnumeric weight validation with weighted COO
emission in one PyO3 pass.

## Baseline

Command: `rch exec -- hyperfine --warmup 2 --runs 10 ...`

- FNX: `642.601 ms +/- 32.302 ms`
- NetworkX: `780.917 ms +/- 66.642 ms`
- FNX was `1.22x` faster than NetworkX on this envelope before the candidate.

Baseline proof:

- `baseline_proof.json`
- golden proof SHA: `076dba99b0467b920f6ba68c51bb395f22052483dc0d6f81bff92d52f73e34e1`
- clean and dirty-edge PageRank cases matched NetworkX exactly (`max_abs=0.0`, `max_rel=0.0`)

## Candidate Result

The candidate was proof-clean:

- `after_proof.json`: clean and dirty-edge PageRank cases matched NetworkX exactly.
- `after_fused_weight_fallback_proof.json`: finite, missing-weight, NaN, infinity, string-weight, dirty-edge infinity, directed, and undirected cases matched NetworkX.
- fallback proof SHA: `c32bc489571823cacc274eb787e4680e95f11784718a8c1b8db80e778771dcd2`

The direct before/after hyperfine looked positive but was contaminated by host
movement:

- FNX before: `642.601 ms +/- 32.302 ms`
- FNX after: `588.322 ms +/- 21.003 ms`
- NetworkX before: `780.917 ms +/- 66.642 ms`
- NetworkX after: `710.885 ms +/- 30.951 ms`

To isolate the source lever, `bench_fused_toggle.py` compared the old separate
scan+builder path against the fused path in the same candidate binary:

- fused disabled: `625.612 ms +/- 34.310 ms`
- fused enabled: `624.595 ms +/- 25.097 ms`
- result: `1.00x +/- 0.07`, below the Score>=2.0 keep gate

## Verdict

Rejected. Source was restored after the same-binary toggle showed no stable win.

Score: `0.0` (`Impact 0 * Confidence 4 / Effort 2`)

## Isomorphism Notes

- Ordering: PageRank returns `dict(zip(list(G), x))`; `list(G)` was unchanged.
- Tie-breaking: no graph traversal tie-break policy changed; sparse COO assembly is order-independent.
- Floating point: finite cases used the same scipy sparse power iteration; nonfinite/nonnumeric cases delegated to NetworkX.
- RNG: none.

## Next Primitive

The rejected lever confirms the separate preflight scan is not the right level.
Next attack: replace the repeated scipy object-construction envelope with a
native/cached row-stochastic PageRank primitive for repeated simple weighted
graphs, preserving exact node order, nonfinite fallback, dirty edge-attr sync,
and scipy-compatible convergence/error behavior. Target ratio: at least `1.25x`
over current FNX on the same 80-call weighted PageRank envelope.
