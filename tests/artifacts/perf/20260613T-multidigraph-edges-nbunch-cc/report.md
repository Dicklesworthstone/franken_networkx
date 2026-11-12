# MultiDiGraph.edges(nbunch) per-source walk — 295x → 1.4x vs nx

Bead: br-r37-c1-edgesnbunch (Multi view-asymmetry sweep)
Agent: cc
Date: 2026-06-13

## Problem

`MultiDiGraph.edges(u)` for a single source node `u` was ~295x slower than
nx (≈750µs/call on a 1000-node / 3000-edge graph). Two root causes in the
native `MultiDiGraphEdgeView.__call__`:

1. It built the result from `g.inner.edges_ordered()` — the **owned** snapshot
   that **clones every edge's `AttrMap`** — then filtered by membership in the
   nbunch set. So every call was O(E) clones regardless of how few sources were
   requested. (The cloned attrs were never even used: edge data is read from
   `edge_py_attrs`, not the Rust `AttrMap`.)
2. It allocated a fresh `Vec<String>` of **all** node keys (`expected_nodes`)
   per call, only to read `.len()` for the mutation guard.

It also harbored a latent **ordering bug**: it emitted edges in node-iteration
order filtered by nbunch membership, whereas nx's `OutMultiEdgeView` walks
`nbunch` in user-given order (first-occurrence dedup, skipping missing nodes).
For multi-node nbunch whose order differed from node order, fnx diverged from
nx (e.g. `edges([5,3,1])`).

## Fix

- New `MultiDiGraph::out_edges_ordered_borrowed(node)` in fnx-classes: walks one
  source's `successors[node].keys()` then key-buckets, **borrowing** attrs — zero
  clones, O(out-deg(node)).
- `parse_edge_nbunch_for_multidigraph` now returns an **ordered, first-occurrence
  deduped `Vec<String>`** (nx `nbunch_iter` semantics) instead of a `HashSet`.
- `__call__` walks only the requested sources' out-edges in nbunch order via the
  borrowed walker (full-graph `edges(None)` uses `edges_ordered_borrowed()` —
  also clone-free). `expected_nodes` Vec replaced by `g.inner.node_count()`.

This fixes both the speed and the ordering divergence in one change.

## Proof

- Parity sweep: 12 seeds × {single, multi in/out-of-order, duplicate, missing
  nbunch} × {data False/True/'weight'} × {keys False/True} = **720 checks, 0
  mismatches** vs nx (values, order, and exception type all byte-identical).
- Golden sha256 over `edges(s, keys=True, data=True)` for a fixed 200-node /
  600-edge graph: `28bdc1b553989cfd049bdea48e0e699ea226eb95cecb123c6c5b4c8b3910a2bd`.
- Full python suite: only the 6 known pre-existing failures remain (chordal
  fallback, 2× coverage-gap, rcm-delegation, child-module-parity, gexf).

## Timing (1000 nodes, 3000 edges, min-of-5×200)

| call                     | before  | after   | nx      | after vs nx |
|--------------------------|---------|---------|---------|-------------|
| `edges(5)`               | ~750µs  | 3.74µs  | 2.68µs  | 1.4x slower |
| `edges(5, keys, data)`   | ~750µs  | 4.37µs  | 2.77µs  | 1.6x slower |
| `edges([5,7,9])`         | —       | 7.14µs  | 5.12µs  | 1.4x slower |

≈200x self-speedup; 295x-slower-than-nx → 1.4x-slower-than-nx.
