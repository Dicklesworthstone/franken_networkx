# br-r37-c1-jzm86 common_neighbors row-key intersection

## Target

- Umbrella: `br-r37-c1-04z53`
- Child bead: `br-r37-c1-jzm86`
- Hotspot: `franken_networkx.common_neighbors` for exact plain `Graph`
- Profile-backed residual: BA(1200,4), `u=0`, `v=10`.

## Baseline

Clean-worktree scout at `994f4f4bc`:

- FNX median: `9.115137974731624 us`
- NetworkX median: `2.095531963277608 us`
- Digest: `2522865e2a699bee40f7f796f7b24c98cd03667dbd4a327387c08868f2ff9a9e`
- Profile: 20k calls spent `0.290s` in FNX, dominated by two private-aware neighbors calls and raw-neighbor dispatch.

Harness old-equivalent baseline:

- Old median: `9.756926796399057 us`
- Old SHA: `4771923fcb3ba86a786f6455f615d48096685058ba70b48809ec813774e33385`

## Lever

One Python routing lever:

- For exact plain `Graph` with no NetworkX-private storage, run before graph coercion.
- Preserve the existing missing-node checks and error messages.
- Intersect two native adjacency row key views, then discard `u` and `v`.
- Keep directed graphs, private-storage graphs, subclasses, and other graph types on the prior fallback path.

## Isomorphism Proof

- Public output is a set; ordering and tie-breaking are not observable.
- Floating-point and RNG are not involved.
- Missing-node errors are covered by focused pytest.
- Golden SHA: `9340c2974a7b8d928da698aa861e9ff21150d5ae81966fc2e09f4c6989240e91`.
- Old/new/NX case SHA for BA(1200,4): `4771923fcb3ba86a786f6455f615d48096685058ba70b48809ec813774e33385`.

## Results

Sequential harness, same case (`n=1200`, `m=4`, seed `17`, `u=0`, `v=10`, loops `5000`, repeats `15`):

- Old-equivalent median: `9.756926796399057 us`
- FNX after median: `2.0280005992390217 us`
- NetworkX reference median: `1.951611798722297 us`
- Baseline-to-after speedup: `4.8111x`
- After/reference ratio: FNX is `1.0391x` slower than NetworkX.

`rch exec -- hyperfine` process-level A/B (`25000` calls per process, graph construction included):

- Old mean: `535.6 ms +/- 22.3 ms`
- New mean: `351.0 ms +/- 16.6 ms`
- Ratio: `1.53x +/- 0.10` faster.

After-profile:

- `20000` calls in `0.102s`.
- `common_neighbors` cumulative time: `0.094s`.
- Remaining cost is membership/private-storage checking and two native row dict lookups.

## Score

- Impact: `4.8111` per-call speedup (`1.53` process-level hyperfine with construction included)
- Confidence: `4`
- Effort: `1`
- Score: `19.24` per-call (`6.10` by process-level hyperfine)
- Verdict: keep.
