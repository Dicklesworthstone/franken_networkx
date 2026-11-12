# br-r37-c1-nj976 rejection report

Target: `MultiGraph.add_edge(i, i + 1, key=str(i))`

Attempted primitive: replace the nested per-pair multiedge `IndexMap<usize, AttrMap>` with a single-edge bucket layout, preserving NetworkX public key order and attr mutation semantics.

Baseline:
- Hyperfine FNX: 657.4525018 ms mean, 20.7586104 ms stddev.
- Hyperfine NX: 494.3655769 ms mean, 24.0734722 ms stddev.
- Profile digest: `a316d777cf3e4070855b2fca932a4f8f993dee8bbacf6d430f95624dd04d41bf`.

Behavior proof:
- Proof SHA: `ba34aacd90c0dc1b40f447778b9eacadeeee26607d06f7a8ec586fc6ad14885f`.
- Construction digest stayed `a316d777cf3e4070855b2fca932a4f8f993dee8bbacf6d430f95624dd04d41bf`.
- Checked public auto-key sequence `[0, 1, 4, 3]`, public string-key attr extension, node/neighbor/edge ordering, copy, subgraph, edge_subgraph, and pickle parity against NetworkX.
- Floating-point and RNG surfaces: not applicable to this construction path.

After:
- Hyperfine 10-run FNX: 739.4289512 ms mean, 43.5680024 ms stddev.
- Hyperfine 10-run NX: 558.8742476 ms mean, 14.5601817 ms stddev.
- Hyperfine 20-run FNX: 1046.6303574 ms mean, 177.1220494 ms stddev.
- Hyperfine 20-run NX: 823.5252103 ms mean, 147.1119243 ms stddev.
- cProfile construction mean was effectively unchanged: 0.1770586056 s after vs the bead's prior 0.1774472868 s.

Decision:
- Rejected. Same benchmark did not confirm a real win and does not clear Score >= 2.0.
- Code change reverted; only proof and rejection artifacts remain.

Next primitive:
- Stop iterating per-pair bucket layout.
- Attack a deeper PyO3/native construction primitive: avoid per-call Python hash/canonical-string/node-map overhead for monotonically fresh int endpoints with explicit string public keys, or add a true batch construction path that can amortize public-key metadata and adjacency insertion.
