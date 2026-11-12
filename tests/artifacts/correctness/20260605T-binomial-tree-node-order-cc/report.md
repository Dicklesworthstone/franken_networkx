# fix: binomial_tree node order parity with networkx

## Bug
`fnx.binomial_tree(n)` returned nodes in SORTED order [0..2^n-1], but networkx's
node order is NOT sorted for n>=4 (e.g. n=4: [...,10,12,11,13,...] — node 12
before 11). nx builds the tree by iterative doubling: each round shifts the
current `G.edges()` by N and `add_edges_from`, so the shifted-copy nodes are
introduced in edge-encounter order, not sorted. The fnx Python wrapper called
`_add_nodes_in_order(G, range(N, 2*N))` BEFORE `add_edges_from`, forcing sorted
node order — diverging from nx. (The Rust `_rust_binomial_tree` kernel is unused;
the wrapper always takes the Python path per br-binomlabels.)

## Fix
Remove the `_add_nodes_in_order` pre-add; let `add_edges_from` introduce the
shifted nodes in nx's exact order. Every node N..2N-1 appears in some edge of a
binomial tree, so none are lost. The wrapper now mirrors networkx line-for-line.

## Proof
parity_proof.py: orders 0..15, compare full node order + edge order + error
parity vs networkx — 0 mismatches. DiGraph create_using and negative n also
verified. 10 binomial pytest pass. golden_sha256 (over nx output, now matched by
fnx): db4170ae957a8d5df0e6944934585b8b2a29d41de1f79e7657ac8f48b00abed3.

Node order matters for downstream tie-breaking/determinism parity, so this is a
behavior-parity fix (no perf change).
