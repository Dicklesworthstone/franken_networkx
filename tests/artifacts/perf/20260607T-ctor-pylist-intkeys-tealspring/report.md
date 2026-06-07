# Graph ctor PyList positional extraction — rejected

## Target

Bead: `br-r37-c1-d58s8`

Residual from the previous rejected ctor index-batch lever: `Graph(edges)`
constructor absorb is dominated by PyO3 item extraction/canonicalization, not by
Rust edge-batch `String` cloning.

## Candidate

Add a guarded `PyList` positional constructor path for exact scalar / int-tuple
edge lists. The guard falls back to the old `PyIterator` branch for arbitrary
Python objects so list-mutation and user-code `repr` behavior stay on the prior
semantics.

Patch archived: `pylist_positional_candidate.patch`.

## Proof

Golden proof SHA stayed unchanged:

- baseline: `7da75f468095dd105f9e2c4ebf41964a08c1eb959fcb776b2a1e3321f2bfa998`
- after: `7da75f468095dd105f9e2c4ebf41964a08c1eb959fcb776b2a1e3321f2bfa998`

Proof cases covered:

- list/tuple/generator plain edge order
- attributed list edge merge order and live attr dict mutation
- graph-level attrs
- interleaved slow-node fallback
- known pre-existing `bad_third_hashable` and `bad_str_item` parity gaps

Isomorphism:

- Ordering preserved: yes; fast-list candidate used the same index order and
  the old iterator branch for unsafe objects.
- Tie-breaking unchanged: yes; edge canonicalization and duplicate cell rules
  were unchanged.
- Floating-point: unchanged; exact floats still flowed through
  `node_key_to_string`.
- RNG: N/A; fixtures use fixed seeds only for benchmark edge generation.
- Golden outputs: `sha256sum -c artifact_checksums.sha256` passed.

## Baseline vs after

Direct benchmark:

| case | before best | after best | speedup |
| --- | ---: | ---: | ---: |
| `list_plain` | 12.811 ms | 16.623 ms | 0.77x |
| `tuple_plain_control` | 14.272 ms | 18.141 ms | 0.79x |
| `generator_plain_control` | 14.663 ms | 11.067 ms | 1.32x |
| `list_attr` | 34.763 ms | 27.459 ms | 1.27x |

Hyperfine process envelope:

| case | before mean | after mean | speedup |
| --- | ---: | ---: | ---: |
| `list_plain` | 1.212 s | 1.396 s | 0.87x |
| `list_attr` | 1.736 s | 2.058 s | 0.84x |
| `tuple_plain_control` | 1.230 s | 1.237 s | 0.99x |
| `generator_plain_control` | 1.262 s | 1.547 s | 0.82x |

Verdict: rejected. The safety pre-scan and second positional pass outweighed
any iterator-protocol savings. Score `0.0`.

## Next primitive

Do not keep tuning list iteration. The next profile-backed primitive is a
fused validation + typed edge-tape constructor kernel: one native pass builds a
small typed edge tape/morsel for exact list/tuple inputs, the Python wrapper
consumes that proof instead of running `validate_ctor_edge_list` and then
re-walking the data in `__new__`.

Graveyard route:

- Vectorized/morsel execution: process data in cache-sized batches.
- Explicit state machines: make validation and absorb one auditable transition
  system.
- Succinct graph representation / Swiss-table direction: keep moving the
  substrate toward index-keyed edge rows and compact maps instead of another
  Python boundary micro-lever.
