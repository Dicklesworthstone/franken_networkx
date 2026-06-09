# br-r37-c1-04z53.67 6-Regular k_components Bitmask Certificate

## Target

Fresh post-`0243da232` profile showed 6-regular `k_components` still
delegating through NetworkX:

- `random_regular_graph(6,20,seed=17)`: discovery cProfile observed
  `3,223,578` calls in `1.357s`, dominated by
  `_call_networkx_for_parity -> nx.k_components -> all_node_cuts`.
- Formal baseline profile for the same case recorded `3,228,824` calls in
  `0.998s`, with `all_node_cuts` cumulative `0.974s`.
- Baseline direct FNX means: `rr_6_20_seed17` `0.34513198758941144s`;
  `rr_6_24_seed19` `0.4867910668021068s`.
- Baseline rch-wrapped hyperfine FNX command mean:
  `0.6635180569s`.

## Lever

Add a bounded simple-Graph 6-regular certificate for default-flow
`k_components`. The guard checks `8 <= n <= 24`, `2m = 6n`, exact degree 6
for every adjacency row, and connectivity after every vertex removal set of
size 0 through 5.

Unlike the 3/4/5 set-based guards, this pass uses compact integer adjacency
and removal masks. Only if all checks pass it emits the closed lattice
`{6: [V], 5: [V], 4: [V], 3: [V], 2: [V], 1: [V]}`.

All custom `flow_func`, non-6-regular, disconnected, large, and cut-failing
graphs delegate to NetworkX.

## Results

- rch-wrapped hyperfine FNX command:
  `0.6635180569s -> 0.34557771736000004s` (`1.92x`).
- Direct `rr_6_20_seed17` FNX mean:
  `0.34513198758941144s -> 0.05418277159333229s` (`6.37x`).
- Direct `rr_6_24_seed19` FNX mean:
  `0.4867910668021068s -> 0.17097870260477066s` (`2.85x`).
- After cProfile shifted to the certificate:
  `_six_regular_six_connected_k_components` `0.108s`, with
  `connected_after_removing` `21,700` calls.

## Isomorphism

- Ordering preserved: yes. Certified output keys stay `[6, 5, 4, 3, 2, 1]`.
- Tie-breaking unchanged: yes. Certified cases have one maximal component per
  level; cut-failing graphs delegate.
- Floating-point: N/A.
- RNG: seeded graph construction only; output has no RNG surface.
- Golden proof SHA unchanged:
  `b53615f040ae14b34cbb981a188a1f6f817e14143620c414594133a0e85895b8`.
- `sha256sum -c proof_files.sha256` replays baseline and after artifacts.

## Score

Impact `4.0` x Confidence `4.5` / Effort `1` = `18.0`.
