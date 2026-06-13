# br-r37-c1-2mfuj check_planarity conversion fast path

Status: rejected.

Profile-backed target: `check_planarity` on exact simple `Graph`, where cProfile showed `_planarity_graph_for_certificate -> _fnx_to_nx` dominating the nonplanar random case and contributing material cost to the planar grid case.

Lever tested: build the temporary NetworkX graph for planarity directly from native bulk adjacency rows, preserving row order and attribute dictionaries, instead of using the general `_fnx_to_nx` edge-emission plus row-realignment path.

Benchmark evidence:

- Grid baseline mean: `0.017027496849186717s`
- Grid candidate mean: `0.01767830565222539s`
- Grid effective speedup: `0.9631860193028879x`
- Random baseline mean: `0.007372749347268837s`
- Random candidate mean: `0.005554287951963488s`
- Random speedup: `1.3273977530571686x`
- Baseline golden SHA256: `9777eb824e38b6e96da70eb7811aeca410ca45219857d55a04604ca68331e4b0`
- Candidate golden SHA256: `9777eb824e38b6e96da70eb7811aeca410ca45219857d55a04604ca68331e4b0`
- Grid output SHA256: `003cc7efd008f28e3445319bfe2dd971559df667ed9db28aa5355d5ceece3451`
- Random output SHA256: `cf10a0acfc8dfa1af67c2f9f165ae9df9f141b97c63a597397504871cbe6d06e`

Behavior proof:

- Ordering/tie-breaking: serialized planar embedding neighbor order and nonplanar result hashes were unchanged.
- Floating point/RNG: no floating-point path changed; the random benchmark graph used fixed `seed=0`.
- Certificate contract: planar grid still returned a `PlanarEmbedding`; random nonplanar still returned `None`.

Rejection:

The lever improves the random nonplanar case but regresses the planar grid case, so it does not meet the no-regression keep bar and no production code was kept.

Next primitive:

Use a sharper nonplanar-only path: when `counterexample=False`, exact simple graphs that native LR planarity rejects can return `(False, None)` without constructing a NetworkX certificate graph. Planar graphs still delegate for the embedding.
