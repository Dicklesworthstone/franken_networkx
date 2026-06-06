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

## Rejected Candidate 2: Source PyDict Copy for New Mirrors

- Candidate: when an attributed edge mirror key was vacant, insert
  `src_dict.copy()` directly instead of creating an empty `PyDict` and updating
  it. Occupied mirrors still updated in place.
- Proof: golden SHA unchanged and focused add_edges parity remained `15 passed`.
- Direct timing regressed in absolute FNX time:
  - baseline FNX median: `0.0087127320s`
  - candidate FNX median: `0.0089030605s`
- Hyperfine was effectively flat:
  - baseline mean: `0.4344s`
  - candidate mean: `0.4310s`
- cProfile rejected the lever:
  - baseline total: `1.397s`
  - candidate total: `1.908s`
  - native `_try_add_edges_from_batch`: `1.386s -> 1.886s`
- Verdict: rejected and reverted. `PyDict.copy()` is not the right deeper
  primitive for this workload; the next attempt must change the representation
  and commit strategy rather than substituting one per-edge dict operation for
  another.

## Rejected Candidate 3: Lazy Inner AttrMap Deferral

- Candidate: for attributed `DiGraph.add_edges_from` batches whose attr dicts
  contain exact string keys and exact bool/float/int/string values, commit the
  live Python edge-attr mirrors immediately, insert only topology into the Rust
  inner graph with empty edge attrs, and mark edge caches dirty so weighted
  kernels sync from the Python mirrors before use.
- Proof:
  - Focused add_edges parity: `15 passed`
  - Golden SHA unchanged:
    `c6f6227073dc924849e81ae552df913fcfaf278a522aae3abccdca2605eb6f48`
- Fresh trusted-batch baseline for this candidate:
  - Direct FNX median: `0.0104194000s`
  - NetworkX median: `0.0038195670s`
  - Ratio: `2.7279x`
  - Hyperfine mean: `0.4766727983s`
  - cProfile total: `1.784s`
  - native `_try_add_edges_from_batch`: `1.767s`
- Candidate result:
  - Direct FNX median: `0.0124468925s`
  - NetworkX median: `0.0040948070s`
  - Ratio: `3.0397x`
  - Hyperfine mean: `0.5070195913s`
  - cProfile total: `1.992s`
  - native `_try_add_edges_from_batch`: `1.977s`
- Verdict: rejected and source restored. Deferring Rust inner AttrMap
  materialization increased native batch cost on the target fixture.
- Source-restored timing sanity artifact:
  `restored_after_lazy_reject_timing.json`.
- Score: Impact `0` x Confidence `5` / Effort `2` = `0`; do not keep.
- Isomorphism proof: node order, successor/predecessor row order, duplicate
  merge order, tie-breaking, floating-point values, and RNG seed `20260606`
  were preserved by the proof harness and unchanged golden SHA.
- Next primitive: do not continue lazy-inner deferral on this fixture. Attack a
  shared slot descriptor instead: canonical endpoints, directed edge key, live
  mirror handle, and inner adjacency row handles should be carried in one arena
  so mirror construction and inner adjacency commit avoid duplicate
  `String`-pair allocation/probing while preserving `get_edge_data` live dict
  identity and weighted-kernel synchronization.

## Rejected Candidate 4: Prechecked Inner Edge Slots

- Candidate: reuse the Python-side precomputed new-node list in a hidden
  `DiGraph` bulk insertion path, reserve known capacities, probe duplicate
  inner edges with borrowed directed keys, and skip repeated endpoint existence
  checks during the inner edge loop.
- Proof:
  - `cargo check -p fnx-python --all-targets`: passed via rch
  - `cargo clippy -p fnx-python --all-targets -- -D warnings`: passed via rch
  - `cargo test -p fnx-classes prechecked_attr_edge_batch_matches_generic_bulk_order_and_merges`: passed
  - Focused add_edges parity: `15 passed`
  - Golden SHA unchanged:
    `c6f6227073dc924849e81ae552df913fcfaf278a522aae3abccdca2605eb6f48`
- Fresh slot-descriptor baseline:
  - Direct FNX median: `0.0160504880s`
  - NetworkX median: `0.0055196155s`
  - Ratio: `2.9079x`
  - Hyperfine mean: `0.5491196056s`
  - cProfile total: `2.537s`
  - native `_try_add_edges_from_batch`: `2.513s`
- Candidate result:
  - Direct FNX median: `0.0166370440s`
  - NetworkX median: `0.0062379005s`
  - Ratio: `2.6671x`
  - Hyperfine mean: `0.7217507590s`
  - cProfile total: `2.635s`
  - native `_try_add_edges_from_batch`: `2.607s`
- Verdict: rejected and source restored. The borrowed-key/prechecked-node inner
  path did not remove the dominant native batch cost and worsened process
  timing.
- Score: Impact `0` x Confidence `5` / Effort `2` = `0`; do not keep.
- Isomorphism proof: node order, edge insertion order, duplicate merge order,
  successor/predecessor row order, tie-breaking, floating-point values, and RNG
  seed `20260606` were preserved by the Rust unit, focused parity, and unchanged
  golden SHA.
- Next primitive: do not continue capacity/prechecked-node variants. Attack a
  fused Python-dict decode/mirror primitive: one pass over each source attr
  dict should populate both the Rust `AttrMap` and the graph-owned Python mirror
  slot for new edges, while duplicate edges update the live slot in NetworkX
  order. Target is to remove the current double attr-dict walk
  (`py_dict_to_attr_map` then `PyDict.update`) without aliasing the caller's
  input dict.
