# perf(prefix_tree): O(1) children index — fixes prefix_tree + dag_to_branching

br-r37-c1-vuzc5

## Problem
`prefix_tree(paths)` (also the engine of `dag_to_branching`) found each path
step's existing child by SCANNING `tree.successors(parent)` and doing a PyO3
`tree.nodes[succ].get("source")` read for EVERY candidate — O(path_len * fanout)
with a Rust crossing per candidate. dag_to_branching was 4-9.7x slower than nx
(scaling); prefix_tree itself 16x (586ms vs 37ms at ~1061 paths, n=1600 DAG).

## Lever (one)
Maintain a `{parent: {source_value: child_id}}` index for O(1) child lookup
(exactly what nx's prefix_tree keeps) instead of the linear successors scan +
per-candidate attr read. A trie never has two children of one parent sharing a
`source` value, so the map is exact. Pure-Python; no rebuild.

Touched: python/franken_networkx/__init__.py (prefix_tree only).

## Proof (behavior-preserving)
The change is mechanism-only (O(1) dict returns the same child the linear scan
would, same create-vs-reuse order => same node numbering). Verified byte-
identical to HEAD over 500 cases (random integer + string path lists,
0 mismatches). dag_to_branching: 0 mismatches vs nx over 40 DAGs. pytest -k
"prefix_tree or branching or dag": 572 passed.
PREFIX_TREE_SHA 8f32ce7fcfb2864d8236d575f8220ebf44ee4cd929600e3e7403b800e3504ce1

NOTE: a PRE-EXISTING fnx-vs-nx node-numbering divergence in prefix_tree (nx
numbers BFS-style, fnx path-by-path; isomorphic trees, different integer ids)
is unchanged by this lever — filed separately. (nx.dag_to_branching dispatches
to the fnx backend, masking it on that path.)

## Timing (warm min-of-5)
| call                        | before  | after  | vs nx after |
|-----------------------------|--------:|-------:|------------:|
| prefix_tree (#paths=1061)   | 586ms   | 36ms   | 2.67x       |
| prefix_tree (#paths=2138)   | ~1180ms | 92ms   | 3.10x       |
| dag_to_branching n=800      | ~75ms*  | 75ms   | 2.33x (was 4.2x) |
| dag_to_branching n=1600     | ~340ms  | 170ms  | 1.89x (was ~4x)  |
| dag_to_branching n=3200     | ~660ms  | 203ms  | 1.23x (was 9.7x) |

prefix_tree 16x self-speedup; residual ~2-3x is fnx DiGraph construction tax
(add_node/add_edge per trie node) — the known-deferred bulk-construction issue.

## Score
Impact: high (16x self-speedup on prefix_tree, fixes dag_to_branching scaling).
Confidence: high (0/500 vs HEAD byte-identical, 572 tests). Effort: low
(one-function pure-Python index). Score >> 2.0.
