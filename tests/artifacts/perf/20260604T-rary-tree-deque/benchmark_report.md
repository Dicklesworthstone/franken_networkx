# _tree_edges_local (full_rary_tree / balanced_tree): list pop(0) -> deque

Lever: the r-ary tree edge generator used a Python list as its BFS frontier
queue with `parents.pop(0)` -- an O(n) front-shift -- making edge generation
O(n^2). Use a collections.deque with `popleft()` (O(1)). FIFO order is
identical, so the yielded edge sequence (and the resulting tree) is
byte-identical. A complexity-class change, not a loop tweak.

## Benchmark (same-process A/B, monkeypatched generator)

| measurement                  | OLD (list) | NEW (deque) |
|------------------------------|-----------:|------------:|
| generator only, n=300000     | 2673 ms    | 65 ms (41x) |
| full_rary_tree(2, 300000)    | 4280 ms    | 1665 ms     |

End-to-end ~2.6x (the rest is the separate construction tax); now ~2x FASTER
than nx (3158 ms). The speedup grows with n (O(n^2) signature: isolated
generator 3.5x@20k -> 41x@300k).

## Isomorphism proof

Edge sequence + node set byte-identical to networkx for full_rary_tree across
r in {2,3,4,5} x n in {0,1,2,3,7,50,500,3000}, balanced_tree across
r in {2,3} x h in {0,1,3,5}, and create_using=DiGraph; tree invariants hold
(n nodes, n-1 edges, connected, is_tree) (test_rary_tree_deque_parity,
4 cases). 50 existing tree-generator tests pass.

Same "O(n^2) front-pop / re-sort in a loop -> O(n) deque/bucket" vein as the
Havel-Hakimi (d1a8d0a23) and Erdos-Gallai (1054b4622) fixes.
