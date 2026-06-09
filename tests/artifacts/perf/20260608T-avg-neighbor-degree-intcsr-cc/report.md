# average_neighbor_degree: integer-CSR kernel + drop wrapper re-key (br-r37-c1-anbrdeg)

## Problem
3.45x SLOWER than nx. Kernel kept degrees in HashMap<&str> and did a String-hash
lookup `degrees[neighbor]` PER EDGE (String-adjacency tax), then sorted results
lexicographically so the wrapper re-keyed `{node: raw[node] for node in G}`.

## Lever
Integer-CSR: degrees indexed by node INDEX (Vec, O(1)), neighbors_indices in the
per-node sum; emit scores in node-insertion order (per-node sum is over integers
-> order-invariant -> bit-identical). Wrapper returns the binding dict directly.

## Proof
- Parity 0/240 value + key order (60 seeds x int/string keys x self-loop on/off);
  non-default params (directed in/out, weighted) still delegate correctly.
  pytest -k average_neighbor 18 passed.
- Speed n=400 (interleaved min-of-15): 0.224ms vs nx 0.412ms = 3.45x slower ->
  0.54x = 1.85x FASTER than nx.
