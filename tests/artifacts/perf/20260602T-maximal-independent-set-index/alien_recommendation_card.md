# Alien Recommendation Card: br-r37-c1-dxm71

## Target

`maximal_independent_set` on BA(3000, 3, seed=42), public Python API with `seed=7`.

Clean-HEAD baseline:
- fnx mean: `0.08060656133214555` s
- NetworkX mean: `0.010920202199001021` s
- fnx/nx ratio: `7.381416558341698`
- cProfile: 30 calls spend `2.426` s cumulative in native `_fnx.maximal_independent_set`.

## Primitive

Alien graveyard §7.1 Succinct Data Structures and §7.2 Cache-Oblivious Data Structures.

Applied subset: dense integer node indices, contiguous adjacency-by-index, and `Vec<bool>` blocked state instead of `HashSet<String>` plus repeated Python-list materialization. The §7.2 practical fallback is the exact fit here: a simple contiguous `Vec` layout wins before heavier cache-oblivious machinery is justified.

## EV Score

Impact 5 x Confidence 5 / Effort 1 = `25.0`.

## One Lever

Replace PyO3 wrapper hot-loop string blocking with:
- `_randbelow(len)` for the same index draw used by `random.choice`;
- precomputed `node -> index` and adjacency indices;
- `Vec<bool>` blocked state;
- output remapping through `ordered_nodes[idx]`.

## Fallback

Fallback is `git revert` of the wrapper commit. The public Python wrapper still validates seed, directed graphs, subsets, self-loops, and errors before/around the raw binding.

## Result

After:
- fnx mean: `0.004619695767663264` s
- Speedup: `17.44845664867624x`
- fnx/nx ratio: `0.4230412297755689`
- Repeat-50 hyperfine: `1.1537817483199997` s -> `0.549334169` s (`2.100327657426312x`)
- Golden sha256 unchanged: `9a2bef4b166f1a6db4bf3ec4e4e89b72c8c4e2944f27c15b07b7cc9d32c73ba8`

## Next Profile Target

After reprofile, the public Python self-loop scan in `python/franken_networkx/__init__.py:maximal_independent_set` is the next visible cost: 30 calls spend `0.249` s cumulative in `has_edge` checks, while native `_fnx.maximal_independent_set` is down to `0.092` s.
