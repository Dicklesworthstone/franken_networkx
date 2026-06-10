# br-r37-c1-04z53.69 8-Regular k_components Bitmask Certificate

## Target

Fresh post-`4d0098374` routing had no ready `[perf]` child bead, so this pass
used the next profile-backed residual from the no-gaps parent:

- `random_regular_graph(8,20,seed=53)` still delegated through
  `_call_networkx_for_parity -> nx.k_components -> all_node_cuts`.
- Formal baseline profile recorded `8,230,054` calls in `2.425s`, with
  `all_node_cuts` cumulative `2.390s`.
- Baseline direct FNX means: `rr_8_18_seed47` `0.6521624775836244s`;
  `rr_8_20_seed53` `1.0190943605732172s`.
- Baseline rch-wrapped hyperfine FNX command mean:
  `1.4358938676800002s`.

## Lever

Add a bounded simple-Graph 8-regular certificate for default-flow
`k_components`. The guard checks `10 <= n <= 20`, `2m = 8n`, exact degree 8
for every adjacency row, and connectivity after every vertex removal set of
size 0 through 7.

The certificate uses compact integer adjacency and removal masks. Only if all
checks pass it emits the closed lattice
`{8: [V], 7: [V], 6: [V], 5: [V], 4: [V], 3: [V], 2: [V], 1: [V]}`.

All custom `flow_func`, non-8-regular, disconnected, large, and cut-failing
graphs delegate to NetworkX.

## Results

- rch-wrapped hyperfine FNX command:
  `1.4358938676800002s -> 0.65611116746s` (`2.19x`).
- Direct `rr_8_18_seed47` FNX mean:
  `0.6521624775836244s -> 0.13004101503174753s` (`5.02x`).
- Direct `rr_8_20_seed53` FNX mean:
  `1.0190943605732172s -> 0.3335706826299429s` (`3.06x`).
- After cProfile shifted to the certificate:
  `_eight_regular_eight_connected_k_components` `0.591s`, with
  `connected_after_removing` `137,980` calls.

## Isomorphism

- Ordering preserved: yes. Certified output keys stay
  `[8, 7, 6, 5, 4, 3, 2, 1]`.
- Tie-breaking unchanged: yes. Certified cases have one maximal component per
  level; cut-failing graphs delegate.
- Floating-point: N/A.
- RNG: seeded graph construction only; output has no RNG surface.
- Golden proof SHA unchanged:
  `dcd52903cf4e1b83d78a1a2712c4cd2c27245aafc8b9f7dedc8d1d37a3bc77a7`.
- `sha256sum -c proof_files.sha256` replays baseline and after artifacts.

## Score

Impact `4.0` x Confidence `4.5` / Effort `1` = `18.0`.
