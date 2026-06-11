# br-r37-c1-1n8g5 native set boundary keep

## Target

Fresh current-head residual sweep after `cd960c8d9` found no FNX-vs-NetworkX
slowdown in the active matrix. The closest remaining profile-backed residual was
the directed `ancestors` / `descendants` boundary:

- `descendants_dag450`: FNX median `0.168088ms`, NetworkX median `0.184530ms`
- `ancestors_dag450`: FNX median `0.162237ms`, NetworkX median `0.182325ms`

The native bindings already performed the graph traversal, but returned a
`frozenset` that the public wrapper immediately copied into an exact Python
`set`.

## Lever Kept

Return a `PySet` from the native `_raw_ancestors` / `_raw_descendants` bindings
and return that set directly from the public wrappers after the existing hash
and missing-node checks.

This keeps directed, undirected, and multigraph routing on the same native
traversal kernels while removing one redundant Python set materialization.

## Proof

`candidate_blackthrush_proof.json` matched NetworkX and the baseline proof
suite SHA:

- suite SHA: `a425f9c0dd1fea0110eb348da73779fb603761346150720aa619e0db29a09dcb`

The proof covers directed DAG ancestors/descendants, hash-equal display objects,
undirected graph behavior, and multidigraph behavior. Return type is checked as
exact `set`. No floating-point or RNG surface is involved.

## Performance

RCH-wrapped baseline:

- `ancestors_dag`: median `0.160351ms`
- `descendants_dag`: median `0.165675ms`
- combined cProfile, 1000 pairs: `0.352s`
- hyperfine process mean: `0.983163889s`

Candidate:

- `ancestors_dag`: median `0.153832ms` (`1.04x`)
- `descendants_dag`: median `0.160507ms` (`1.03x`)
- combined cProfile, 1000 pairs: `0.317s` (`1.11x`)
- hyperfine process mean: `0.911149542s` (`1.08x`)

## Verdict

KEPT. Score `2.2`: small impact, high confidence, and minimal implementation
cost.
