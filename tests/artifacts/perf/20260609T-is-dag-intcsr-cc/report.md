# is_directed_acyclic_graph: integer-CSR Kahn — 2x slower -> 5.9x FASTER (br-r37-c1-isdagidx)

## Problem
The native kernel (used directly: wrapper == native binding speed) ran Kahn's
algorithm String-keyed: in_degree on HashMap<&str,usize>, digraph.in_degree(name)
per node, and digraph.successors(name) (allocates a Vec<&str> + a String lookup
per edge). ~2x slower than nx at n=5000.

## Lever
Integer-CSR: accumulate in-degrees from the integer out-adjacency
(successors_indices) and peel zero-in-degree node INDICES via a VecDeque<usize>.
No String hashing, no per-node Vec<&str> alloc. The result (count == n) is
queue-order-invariant so output is byte-identical (bool).

## Proof
- Parity vs nx 0/240 (80 seeds x {dag, cyclic, self-loop}); string-node DAG,
  single self-loop (False), empty (True) all match; golden sha 7d8ed8d1ab8f0893;
  pytest -k acyclic/dag 467 passed.
- Speed n=5000 deg8 (min-of-15): fnx 1.123ms vs nx 6.597ms = 0.17x = 5.9x FASTER
  (was 2.04x slower).

## NOTE (negative results this session, recorded)
topological_sort + dag_longest_path_length integer rewrites were CORRECT (0/120,
0/240) but NOT wins — node-collection results are conversion-bound (Vec->Python
node objects) and dag_longest_path_length's wrapper computes the length in pure
Python from dag_longest_path (br-r37-c1-jwa0g), bypassing the kernel. Both reverted.
Only SCALAR-returning kernels (bool/float/int that the wrapper actually returns)
are String-tax-fixable — like is_directed_acyclic_graph and flow_hierarchy.
