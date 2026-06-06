# br-r37-c1-blgry Rejected Probe-Collapse Report

## Target

- Bead: `br-r37-c1-blgry`
- Surface: native `_try_add_edges_from_batch` residual after the Python wrapper
  bypass shipped in `br-r37-c1-qtb9w`.
- Profile-backed hotspot: cProfile now shows only `1,401` Python calls over 200
  builds; the time is concentrated in native `_try_add_edges_from_batch`.
- Rejected lever: collapse attributed-batch `seen_nodes` checks from
  `contains + insert` probes into insert-result probes, preserving the existing
  one-sequence-bump-per-edge-with-any-new-endpoint behavior.

## Baseline

- Golden SHA: `c6f6227073dc924849e81ae552df913fcfaf278a522aae3abccdca2605eb6f48`
- Direct timing, `n=1500`, `edges=5217`, `loops=80`:
  - FNX median: `0.0087127320s`
  - NetworkX median: `0.0034604305s`
  - Ratio: `2.5178x`
- Hyperfine process timing:
  - Mean: `0.434407s`
- cProfile, 200 FNX builds:
  - total: `1.397s`
  - native `_try_add_edges_from_batch`: `1.386s`

## After Candidate

- Golden SHA: `c6f6227073dc924849e81ae552df913fcfaf278a522aae3abccdca2605eb6f48`
- Focused add_edges parity: `15 passed`
- Direct timing:
  - FNX median: `0.0110623705s`
  - NetworkX median: `0.0040141575s`
  - Ratio: `2.7558x`
- Hyperfine process timing:
  - Mean: `0.4786s`
- cProfile, 200 FNX builds:
  - total: `1.788s`
  - native `_try_add_edges_from_batch`: `1.772s`

## Verdict

- Rejected and reverted.
- Direct FNX median regressed `0.0087127320s -> 0.0110623705s`.
- Hyperfine mean regressed `0.4344s -> 0.4786s`.
- cProfile regressed `1.397s -> 1.788s`.
- Score: Impact `0` x Confidence `5` / Effort `1` = `0`; do not keep.

## Isomorphism Proof

- Ordering preserved: candidate changed only local `HashSet` probe structure and
  left edge push order unchanged.
- Tie-breaking unchanged: no algorithm tie policy touched.
- Floating-point: unchanged.
- RNG seeds: unchanged; harness seed remains `20260606`.
- Golden outputs: unchanged SHA above.

## Next Primitive

Do not retry local `seen_nodes` micro-probe tuning. The next attempt should
replace the mirror construction model itself: build an arena-backed directed
batch descriptor that carries canonical endpoints, source PyDict handles, and
edge-key slots, then commits `edge_py_attrs` and inner adjacency from that
descriptor with fewer per-edge map transitions. Target ratio: move the current
`2.52x` direct median vs NetworkX toward `<=2.0x` while preserving live
`get_edge_data` dict identity, duplicate merge order, display-key overrides,
and unsupported-batch fallback semantics.
