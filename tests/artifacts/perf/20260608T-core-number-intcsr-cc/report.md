# core_number: integer-CSR Batagelj-Zaversnik + drop redundant wrapper work (br-r37-c1-corenum)

## Problem
core_number was 8.76x SLOWER than nx (5.34ms vs 0.61ms @n=400). Two causes:
(1) the kernel keyed degree/pos/core on HashMap<&str> and did SEVERAL String-hash
lookups/inserts PER EDGE in the peeling loop (the String-adjacency tax);
(2) the kernel sorted the result lexicographically, so the Python wrapper re-keyed
`{node: raw[node] for node in G}` (DOUBLED wall time) and additionally ran a
redundant `number_of_selfloops` O(|E|) pass (the binding already self-loop-guards).

## Lever (ONE, three coordinated edits)
- Kernel: integer-CSR Batagelj-Zaversnik — degree/pos/vert/core as Vec indexed by
  node INDEX (O(1), no hashing); neighbors_indices in the peel; stable sort by
  degree (core numbers are tie-break-invariant); emit results in node-insertion
  order. -> binding `_raw_core_number` is 0.53ms (FASTER than nx 0.58ms).
- Wrapper: the binding now emits node order, so drop the re-key (return raw
  directly); drop the redundant `number_of_selfloops` guard (binding raises the
  identical NetworkXNotImplemented; directed self-loops delegate to nx).

## Proof
- Parity 0/120 value + KEY ORDER (60 seeds x int/string keys); self-loop
  (Graph+DiGraph), multigraph, directed error contracts all match nx;
  k_core/k_shell/k_crust/k_corona downstream 0/15 each. pytest 549 passed.
- Speed n=400 (interleaved min-of-15): 5.34ms -> 0.581ms; vs nx 0.577ms =
  8.76x slower -> 1.01x (PARITY). 8.7x self-speedup.
