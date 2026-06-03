# Alien Recommendation Card: tree center leaf trimming

## Target
- Bead: `br-r37-c1-umbvz`
- Workload: `center(path_graph(1500))`
- Baseline FNX: `0.019387142599443904s`
- Baseline NetworkX: `0.001101763501064852s`
- Golden SHA: `8040836446332e628601060837cf031f58d89918048d3b65cf12fad0a7f49831`

## Candidate Primitive
- Graveyard family: asymptotic replacement at a narrow interface.
- Algorithm: tree leaf trimming, matching NetworkX's `nx.tree.center` branch for unweighted undirected trees.
- Lever: route only `center(G)` with `e is None`, `usebounds is False`, `weight is None`, non-empty, undirected, and `is_tree(G)` through `_tree_center_unweighted`.

## Score Before Edit
- Impact: 5
- Confidence: 5
- Effort: 2
- Score: `5 * 5 / 2 = 12.5`

## Fallback Trigger
Reject if ordered center output differs from NetworkX, if non-tree/weighted/e/usebounds behavior changes, or if hyperfine fails the `Score >= 2.0` keep threshold.

## Verdict
Kept. Direct center mean improved `0.019387142599443904s -> 0.002302988637238741s`; hyperfine improved `683.4 ms -> 359.7 ms`; golden SHA stayed unchanged.
