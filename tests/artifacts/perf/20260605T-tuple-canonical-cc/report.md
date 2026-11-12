# perf: Rust canonical for all-int tuple node keys (br-r37-c1-y7m24)

## Problem
node_key_to_string falls to Python `key.repr()` for tuple keys — the
node shape of grid_2d / hypercube / kneser and relabeled lattices.
grid_2d_graph(60,60) spent 18.7ms of 29.7ms canonicalizing 14160 fresh
(i, j) tuples through repr() inside the edge batches (5.48x vs nx).

## Lever (one)
Fast path in node_key_to_string: tuples whose elements are ALL exact
ints (bool excluded — repr "True" differs; ints outside i64 fall back
to repr, format-consistent) build the CPython-byte-identical tuple repr
in Rust: "(0, 1)", singleton "(0,)". Helps add_node AND both edge-batch
collect paths for every int-tuple-keyed graph.

## Proof
- adversarial canonical fuzz: singleton/negative/2^62/OVERSIZED-2^63+5
  (fallback)/bool-containing/mixed/nested/empty tuples — membership,
  node order, edge order, adjacency all match nx
- equal-value lookups via different int objects (10**14 non-interned)
- 20 random int-tuple-keyed graph differentials vs nx: all match
- generator differential: grid_2d 60x60 / periodic / DiGraph,
  hypercube_8 — full repr-canon equality vs nx
  GOLDEN_CORPUS_SHA256: c67290a6a41affd077bf0b4ed490ffc2f0a079e5038764402b9b55c78144a9fb
- kneser_8_3 node-ORDER divergence found during proof is PRE-EXISTING
  (reproduced on HEAD build) — filed br-r37-c1-jv0h5

## Bench (interleaved warm min-of-10)
- grid_2d_graph(60,60): 29.7ms -> 23.9ms; 5.48x -> 4.43x (1.24x self)
- hypercube_graph(10):  -> 28.7ms; 0.86x — FASTER than nx
- grid residual = edge-batch substrate (PyDict mirrors + IndexMap,
  br-r37-c1-w1dm8) + 3600 per-node Python add_node calls (the nx
  source uses add_nodes_from — candidate follow-up lever)

## Validation
- full tests/python suite: 21389 passed; 6 failures identical to HEAD
- built in isolated worktree; ymeml-style marker-filtered hunk
  (lib.rs carries peer hunks)
