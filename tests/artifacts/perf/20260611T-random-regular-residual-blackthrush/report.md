# br-r37-c1-random-regular-int-edge-batch-89gnr

## Target

`random_regular_graph(8, 1500, seed=12345)` after the native `circular_ladder_graph` pass.

Baseline profile was taken before editing. The residual was profile-backed:

- RCH hyperfine FNX mean: `0.8730308469s`
- RCH hyperfine NetworkX mean: `0.9390319024s`
- Direct FNX median: `0.0075949641s`
- Direct NetworkX median: `0.0065683335s`
- FNX cProfile over 160 calls: `2.266s`; `_try_creation` `1.489s`, Python `random.shuffle` `1.130s`, `add_edges_from` `0.681s`, `_try_add_edges_from_batch` `0.516s`

## Lever Tried

For the exact default `create_using is None` path, preserve the Python RNG, `_try_creation`, CPython `set` edge container, and edge iteration order, but replace final `graph.add_edges_from(edges)` with a flattened integer edge tape and the existing `graph._fast_add_int_edges(flat_edges)`.

This was intended as a narrow final-materialization lever. No RNG, tie-breaking, or candidate edge selection logic changed.

## Isomorphism Proof

Candidate proof matched NetworkX and baseline:

- `all_match`: `true`
- FNX digest: `cac80aef6f181434007d93ef151d69b54867433c4b54c30c76a3c24f3e55bf24`
- NetworkX digest: `cac80aef6f181434007d93ef151d69b54867433c4b54c30c76a3c24f3e55bf24`
- Nodes: `1500`
- Edges: `6000`

Ordering was preserved because the lever consumed the existing Python `edges` set in its native iteration order. Tie-breaking and RNG were unchanged because the Python seeded `random.Random` path and `_try_creation` loop were untouched. There is no floating-point surface.

## Rebench

The lever was rejected and source-restored.

- Direct FNX median regressed `0.0075949641s -> 0.0153827124s`
- Direct FNX mean regressed `0.0098278818s -> 0.0178923739s`
- RCH hyperfine FNX mean regressed `0.8730308469s -> 1.6236445656s`
- RCH hyperfine NetworkX control was `0.9943011154s`
- Candidate cProfile over 160 calls regressed `2.266s -> 3.346s`
- Candidate `_fast_add_int_edges` alone cost `1.347s` over 160 calls

Score: `0.0`. Impact is negative, confidence is high because direct timing, cProfile, and RCH hyperfine agree, and effort is not justified. The source change was reverted.

## Next Primitive

Do not retry final int-edge batching through `_fast_add_int_edges` for this path.

The next target is a deeper Python-RNG-compatible native state machine for `random_regular_graph`:

- Initialize stubs in NetworkX order: `list(range(n)) * d`, not grouped by node.
- Preserve seeded CPython MT19937 and `random.shuffle` semantics exactly.
- Preserve NetworkX `defaultdict` insertion order for potential-edge buckets.
- Preserve final CPython set iteration order, or produce a certificate that proves the emitted graph payload is byte-identical over adversarial hash-equal nodes and repeated seeds.

Target ratio: at least `1.5x` same-worker FNX speedup over current baseline, with digest `cac80aef6f181434007d93ef151d69b54867433c4b54c30c76a3c24f3e55bf24` unchanged.
