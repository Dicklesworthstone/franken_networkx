# br-r37-c1-04z53.70 9-Regular k_components Bitmask Certificate

## Target

Post-`08d79e17d` reprofile found the next residual in the same
`k_components` family:

- `random_regular_graph(9,20,seed=61)` still delegated through
  `_call_networkx_for_parity -> nx.k_components -> all_node_cuts`.
- Discovery profile recorded `17,351,917` calls in `7.205s`, with
  `all_node_cuts` cumulative `7.154s`.
- Formal baseline profile recorded `17,351,915` calls in `5.767s`, with
  `all_node_cuts` cumulative `5.731s`.
- Baseline direct FNX means: `rr_9_18_seed59` `1.439920572641616s`;
  `rr_9_20_seed61` `1.9591325093448784s`.
- Baseline rch-wrapped hyperfine FNX command mean:
  `2.3147389215466663s`.

## Lever

Add a bounded simple-Graph 9-regular certificate for default-flow
`k_components`. The guard checks `11 <= n <= 20`, `2m = 9n`, exact degree 9
for every adjacency row, and connectivity after every vertex removal set of
size 0 through 8.

The certificate uses compact integer adjacency and removal masks. Only if all
checks pass it emits the closed lattice
`{9: [V], 8: [V], 7: [V], 6: [V], 5: [V], 4: [V], 3: [V], 2: [V], 1: [V]}`.

All custom `flow_func`, non-9-regular, disconnected, large, and cut-failing
graphs delegate to NetworkX.

## Results

- rch-wrapped hyperfine FNX command:
  `2.3147389215466663s -> 0.9325736618466668s` (`2.48x`).
- Direct `rr_9_18_seed59` FNX mean:
  `1.439920572641616s -> 0.2053134076607724s` (`7.01x`).
- Direct `rr_9_20_seed61` FNX mean:
  `1.9591325093448784s -> 0.5727757503433774s` (`3.42x`).
- After cProfile shifted to the certificate:
  `_nine_regular_nine_connected_k_components` `1.068s`, with
  `connected_after_removing` `263,950` calls.

## Isomorphism

- Ordering preserved: yes. Certified output keys stay
  `[9, 8, 7, 6, 5, 4, 3, 2, 1]`.
- Tie-breaking unchanged: yes. Certified cases have one maximal component per
  level; cut-failing graphs delegate.
- Floating-point: N/A.
- RNG: seeded graph construction only; output has no RNG surface.
- Golden proof SHA unchanged:
  `763efdd0520c41a2b9db0f79694aecfbf8eab9a1029e562addc704f4f3137a40`.
- `sha256sum -c proof_files.sha256` replays baseline and after artifacts.

## Score

Impact `4.0` x Confidence `4.5` / Effort `1` = `18.0`.
