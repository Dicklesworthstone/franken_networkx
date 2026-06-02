# Isomorphism Proof: br-r37-c1-dxm71

## Change

The PyO3 `maximal_independent_set_with_random` loop now operates on dense node indices and `Vec<bool>` blocked state. It calls `_randbelow(len)` directly instead of `random.choice(seq)`, avoiding repeated Python-list clones of available node names.

## Ordering

Preserved. `ordered_nodes` is still derived from `inner.nodes_ordered()`. The candidate index vector is built in the same filtered `ordered_nodes` order. `available.retain(...)` preserves relative order just like the old `available_nodes.retain(...)`.

## Tie-Breaking

Preserved. CPython `random.choice(seq)` is `seq[self._randbelow(len(seq))]`. For seeded calls the helper receives the same `random.Random(seed)` object as before. For seedless calls it receives the module singleton `random._inst`, which is the object module-level `random.choice` delegates to. Each previous choice consumes exactly one `_randbelow` draw against the same candidate length.

## Floating Point

N/A. The algorithm has no floating-point arithmetic.

## RNG

Preserved. The same RNG object is used, and the same number of `_randbelow` calls is made in the same loop positions. Golden cases include seeded and seedless calls; the seedless case resets module RNG before each comparison.

## Errors

Preserved. Empty graph, subset validation, non-independent initial nodes, directed rejection, public seed validation, and self-loop message rewriting remain on the same public wrapper paths. The raw binding still returns the same PyO3 exception classes and messages for its validation failures.

## Golden Outputs

`baseline_golden.json` and `after_golden.json` both report:

`9a2bef4b166f1a6db4bf3ec4e4e89b72c8c4e2944f27c15b07b7cc9d32c73ba8`

The 30-call sampled benchmark output digest also stayed:

`52e0ac53afc061e6ba3f223451e6329ca586176b07505934ba42cf2bb8537286`
