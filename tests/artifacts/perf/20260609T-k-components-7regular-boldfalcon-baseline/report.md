# br-r37-c1-04z53.68 7-Regular k_components Bitmask Certificate

## Target

Fresh post-`1fdbb32bb` profile showed 7-regular `k_components` still
delegating through NetworkX:

- `random_regular_graph(7,20,seed=41)`: discovery cProfile observed
  `5,221,147` calls in `1.698s`, dominated by
  `_call_networkx_for_parity -> nx.k_components -> all_node_cuts`.
- Formal baseline profile for the same case recorded `5,226,393` calls in
  `1.723s`, with `all_node_cuts` cumulative `1.694s`.
- Baseline direct FNX means: `rr_7_20_seed41` `0.6366390785900876s`;
  `rr_7_22_seed43` `0.9765449667815119s`.
- Baseline rch-wrapped hyperfine FNX command mean:
  `0.9352231128999999s`.

## Lever

Add a bounded simple-Graph 7-regular certificate for default-flow
`k_components`. The guard checks `9 <= n <= 22`, `2m = 7n`, exact degree 7
for every adjacency row, and connectivity after every vertex removal set of
size 0 through 6.

The certificate uses compact integer adjacency and removal masks. Only if all
checks pass it emits the closed lattice
`{7: [V], 6: [V], 5: [V], 4: [V], 3: [V], 2: [V], 1: [V]}`.

All custom `flow_func`, non-7-regular, disconnected, large, and cut-failing
graphs delegate to NetworkX.

## Results

- rch-wrapped hyperfine FNX command:
  `0.9352231128999999s -> 0.48668746168000004s` (`1.92x`).
- Direct `rr_7_20_seed41` FNX mean:
  `0.6366390785900876s -> 0.1521700313780457s` (`4.18x`).
- Direct `rr_7_22_seed43` FNX mean:
  `0.9765449667815119s -> 0.3090788025641814s` (`3.16x`).
- After cProfile shifted to the certificate:
  `_seven_regular_seven_connected_k_components` `0.276s`, with
  `connected_after_removing` `60,460` calls.

## Isomorphism

- Ordering preserved: yes. Certified output keys stay `[7, 6, 5, 4, 3, 2, 1]`.
- Tie-breaking unchanged: yes. Certified cases have one maximal component per
  level; cut-failing graphs delegate.
- Floating-point: N/A.
- RNG: seeded graph construction only; output has no RNG surface.
- Golden proof SHA unchanged:
  `33e0703d3539bbe94beb05e8438eb4bd05b7bcefc0dcd71f09e48356a851287b`.
- `sha256sum -c proof_files.sha256` replays baseline and after artifacts.

## Score

Impact `4.0` x Confidence `4.5` / Effort `1` = `18.0`.
