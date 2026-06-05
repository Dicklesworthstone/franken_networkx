# fix: add_edges_from non-dict third element keeps endpoint nodes (br-r37-c1-a4zlp)

## Bug

nx's `add_edges_from` creates BOTH endpoint nodes (`if u not in
self._node: ... if v not in self._node: ...`) BEFORE touching the edge
datadict, so `add_edges_from([(1, 2, 1.5)])` raises
TypeError("'float' object is not iterable") with nodes 1 AND 2
persisted. fnx's raw per-edge loop attempted the `dict.update` first
and returned the error before creating any node — partial error state
diverged (missing nodes).

Found by the br-r37-c1-pr8q6 differential proof (bad-third-partial
case, verified pre-existing at HEAD).

## Fix (one lever)

In `PyGraph::add_edges_from`'s two fallible-third-element branches
(no-global-attr non-dict third; global-attr non-dict third), call
`self.add_node(py, &u/&v, None)` — the existing first-wins primitive —
before attempting the update, mirroring nx's node-then-datadict order.
Success-path end state is unchanged (add_edge finds the nodes already
present); only the error-path partial state changes.

## Proof (parity_proof.stdout)

6/6 cases match nx on full canonical state (nodes+attrs, edges+attrs,
adjacency) AND exception type+message:
- new-edge float third (the filed repro), global-attr variant,
- valid iterable-of-pairs third (both branches, success path),
- below-batch-gate single edge, string third (ValueError shape).
GOLDEN_SHA256: 8487d3ae99ee78d1e5032bdb10b7b4fa967afd7979f8e4f6e967b927b90673db

br-r37-c1-pr8q6 90-case differential: bad-third-partial flipped to
PASS (10 -> 9 failures); golden corpus sha unchanged
(275c260d...) — no behavioral drift elsewhere. Remaining 9 failures =
br-r37-c1-z6uka, root cause CORRECTED on the bead: per-adjacency-row
display-key objects (nx keeps the py object passed per _adj[u] row;
fnx has one canonical object per node) — architectural, also affects
the per-edge path, needs adj_py_keys map + view-rendering changes.

## Validation

- tests/python/test_add_edges_attr_batch_parity.py extended
  (+2 partial-prefix params): 12 passed
- full tests/python suite: 21334 passed, 6 failures identical to HEAD
  (pre-existing, verified earlier this session)
- built in isolated worktree (HEAD + a4zlp hunks only; peer's
  PyMultiGraph hunks in shared lib.rs excluded); private
  CARGO_TARGET_DIR (/data/tmp/cargo-target-cc) after shared cache hit
  a rustc-version mismatch (E0514)
