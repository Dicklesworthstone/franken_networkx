# fix(prefix_tree): nx-exact node numbering (parity)

br-r37-c1-6y9sr

## Problem
fnx.prefix_tree built trees ISOMORPHIC to nx but with different integer node
ids: fnx numbered nodes path-by-path (in path-arrival order) while nx numbers
in DFS-subtree order (`get_children` groups remaining paths by first element,
expands depth-first, `new_name = len(tree) - 1`). On shared-prefix path sets the
node ids diverged (64/120 random-int-path cases vs genuine nx). nx.dag_to_branching
masked it by dispatching to the fnx backend. Behavior parity is absolute.

## Fix (one lever)
Replace fnx's path-by-path construction with nx's exact get_children + DFS-stack
algorithm. Still O(total path length) with O(1) child grouping (defaultdict), so
no algorithmic regression; output is now byte-identical to nx (node ids, edges,
`source` attrs, NIL terminals).

Touched: python/franken_networkx/__init__.py (prefix_tree only).

## Proof (nx-exact)
420 cases (random int + string path lists): prefix_tree 0 mismatches vs nx;
dag_to_branching 0 mismatches vs GENUINE nx (orig_func, dispatch bypassed).
pytest -k "prefix_tree or branching or dag": 572 passed.
PREFIX_TREE_SHA 62e4a0dd2e6ec910d6a94a8532a5bb009661b15bc7d903f3e59f950d1a91e1f0

## Perf (preserved)
prefix_tree #paths=1061: 47ms (vs 586ms original path-scan, ~12x faster; vs the
interim O(1)-index 36ms — the small delta is the cost of exact nx numbering).
Still a large net win over baseline; dag_to_branching stays ~1.2-1.9x.

## Note
Supersedes the interim br-r37-c1-vuzc5 numbering (perf-only) with the
parity-correct algorithm. Both perf win and nx parity now hold.
