# Isomorphism Proof: Multigraph Int-Key Internal Storage

Bead: `br-r37-c1-ryruk`

Change: for fresh `MultiGraph.add_edge(int, int, key=int)` calls where the explicit key is not `bool` and fits Rust `usize`, FNX stores the explicit int as the internal multigraph key. This avoids inserting a redundant `edge_py_keys` display-map entry. Negative, bool, and unrepresentable-large keys keep the previous map-backed path.

- Ordering preserved: yes. Fresh edge-pair insertion still follows call order; only the per-edge internal key value changes from synthetic `0` to the user-visible int key.
- Tie-breaking unchanged: yes. Per-pair edge-key order and auto-key-after-explicit-key behavior match NetworkX in `key_semantics_golden.py`.
- Floating-point: N/A.
- RNG seeds: N/A.
- Golden output: construction digest stayed `6041eefb1e549a77af5c18a4e08ab1dc24e9df42e2e9ef094e810d35bedf58dc`.
- Key semantics golden: FNX and NetworkX payloads matched; payload SHA `aca2a98ec252a161c6b56407139546fd553165cbfb6824800128198220e1788d`.
- SHA verification: `key_semantics_golden_after_final_build.sha256` verified OK.

Score: `Impact 4 x Confidence 5 / Effort 2 = 10.0`.
