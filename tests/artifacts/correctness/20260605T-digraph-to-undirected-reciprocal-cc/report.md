# fix(bug): DiGraph.to_undirected reciprocal-edge attr parity + determinism (br-r37-c1-78os5)

## Bug
PyDiGraph::to_undirected (binding, fnx-python/src/digraph.rs) merged reciprocal
directed edges a<->b by iterating `self.edge_py_attrs` — a Rust HashMap with
NON-DETERMINISTIC iteration order — and keeping the FIRST-seen direction's attrs
(`Entry::Vacant`). networkx iterates G.edges() in node->successor order and the
LATTER direction's attrs win (dict.update). So the fnx reciprocal-edge winner was
RANDOM (depended on the process's hash seed): up to 32/60 random DiGraphs (after a
remove_node, which perturbs the edge_py_attrs HashMap) diverged from nx, and the
result was non-deterministic across runs.

## Fix
Iterate edges via `self.inner.edges_ordered()` (canonical node->successor order),
and merge with nx's latter-wins semantics: the inner `add_edge_with_attrs`
already `extend`s (updates) existing edge attrs, and the Python-side
`edge_py_attrs` now does dict.update on an existing undirected edge (else a fresh
copy). Deterministic and byte-exact with nx.

## Proof
parity_proof.py: 200-case randomized differential vs networkx (reciprocal edges,
some with EXTRA keys to exercise the dict.update merge, + random remove_node):
0 mismatches on edge order + node order + merged edge attrs. golden sha 39a131ad.
Determinism: two to_undirected() calls on the same (post-remove) graph are
identical. Full Python suite: see suite log.

Note: MultiDiGraph.to_undirected likely shares the same HashMap-order pattern —
filed as a follow-up.
