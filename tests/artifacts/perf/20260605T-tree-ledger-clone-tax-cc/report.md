# br-r37-c1-wvbzw (lever 1) — bfs/dfs_tree RuntimePolicy ledger-clone tax

## Gap (warm min-of-7, n=400/E~2000 digraph)
bfs_tree 6.22x / dfs_tree 8.82x slower than nx, 100% inside the native
binding while bfs_edges/dfs_edges sit at parity (0.166ms vs 0.164ms).
Decisive probe: bfs_tree on a native-built source 2.05ms vs 10.79ms on
a ctor-built source with IDENTICAL structure (5.3x) — tree assembly
scaled with the SOURCE's RuntimePolicy decision ledger (one entry per
recorded op; per-edge ctor => E entries), cloned TWICE per call
(runtime_policy().clone() + set_runtime_policy).

## Lever (one)
Trees carry the MODE, not the history: new_empty_with_mode + fresh
ledger; both clone sites removed in bfs_tree and dfs_tree
(reference_runtime_policy_clone_tax, finally actioned).

## After
bfs_tree 1.14x (reverse 1.15x); dfs_tree 2.04x directed / 1.68x
undirected. dfs_tree residual = the per-edge PyObject->string
re-canonicalization round-trip (kernel returns canonical strings,
binding converts to PyObjects, tree build converts BACK) — lever 2,
left on the bead.

## Proof
golden battery (both fns x directed/undirected x depth_limit {None,2,5}
+ reverse + forest): 0 failures,
sha a1d12cce7abba31de441dffc306afa92b34db80f60ca3ae1542023dbf0052eb8;
build-path independence (native vs ctor source) pinned; result
mutability/independence pinned; 817 traversal tests + full pytest
21584 passed, 0 failed (peer WIP in tree during sweep). 10 new tests.

## AUDIT NOTE
runtime_policy().clone() appears in MANY result-returning bindings —
the same unbounded-ledger tax likely hits every one of them on
ctor-built sources. Grep candidates filed on the bead.
