# br-r37-c1-04z53.66 5-Regular k_components Certificate

## Target

Fresh post-`865afdddb` profile showed 5-regular `k_components` still
delegating through NetworkX:

- `random_regular_graph(5,20,seed=7)`: cProfile `1,951,766` calls in
  `0.646s`, dominated by `_call_networkx_for_parity -> nx.k_components ->
  all_node_cuts`.
- Baseline direct FNX means: `rr_5_20_seed7` `0.21153093895409256s`;
  `rr_5_24_seed11` `0.9049479885958135s`.
- Baseline rch-wrapped hyperfine FNX command mean:
  `0.5566457288800001s`.

## Lever

Add a bounded simple-Graph 5-regular certificate for default-flow
`k_components`. The guard checks `8 <= n <= 32`, `2m = 5n`, exact degree 5
for every adjacency row, and connectivity after every vertex removal set of
size 0 through 4. Only if all checks pass it emits the closed lattice
`{5: [V], 4: [V], 3: [V], 2: [V], 1: [V]}`.

All custom `flow_func`, non-5-regular, disconnected, large, and cut-failing
graphs delegate to NetworkX.

## Results

- rch-wrapped hyperfine FNX command:
  `0.5566457288800001s -> 0.34519488394000003s` (`1.61x`).
- Direct `rr_5_20_seed7` FNX mean:
  `0.21153093895409256s -> 0.035178219177760185s` (`6.01x`).
- Direct `rr_5_24_seed11` FNX mean:
  `0.9049479885958135s -> 0.08490504962392151s` (`10.66x`).
- After cProfile shifted to the certificate:
  `_quintic_five_connected_k_components` `0.124s`, with
  `_is_connected_after_removing` `6196` calls.

## Isomorphism

- Ordering preserved: yes. Certified output keys stay `[5, 4, 3, 2, 1]`.
- Tie-breaking unchanged: yes. Certified cases have one maximal component per
  level; cut-failing graphs delegate.
- Floating-point: N/A.
- RNG: seeded graph construction only; output has no RNG surface.
- Golden proof SHA unchanged:
  `a50fe71c87fb734006c9dd24afb1ad3623937158b4ffb7f6316650f04af87b64`.
- `sha256sum -c proof_files.sha256` replays baseline and after artifacts.

## Score

Impact `5` x Confidence `4.5` / Effort `1` = `22.5`.
