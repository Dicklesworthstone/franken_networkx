# s_metric: route to the unused native kernel (br-r37-c1-yxmdc)

## Problem
nx.s_metric is PURE PYTHON (sum deg(u)*deg(v) over edges) yet fnx's Python loop
was 3.4x SLOWER (6.33ms vs 1.87ms @n=1500) because fnx's per-edge G.edges()
dispatch is much slower than nx's C-dict edge iteration. A native _fnx.s_metric
kernel (sums over CSR adjacency, no Python iteration) was registered+exposed but
UNUSED by the wrapper.

## Lever (ONE)
Route the wrapper to _fnx.s_metric. The kernel is undirected-only and its degree
convention counts a self-loop once where nx counts it twice, so gate to
undirected / simple / self-loop-free; keep the Python loop (correct everywhere)
otherwise.

## Proof
- Parity: 0/160 mismatches across Graph/DiGraph/MultiGraph/MultiDiGraph x
  self-loop on/off x 20 seeds (directed/multi/self-loop all take the Python path;
  error contracts match).
- pytest -k s_metric: 64 passed.
- Speed n=1500 undirected: 6.33ms -> 3.70ms (1.7x self), gap vs nx 3.4x -> 1.96x.

## Residual
Still 1.96x nx: the native kernel itself is ~2.57ms (slower than nx's 1.87ms
Python loop -- anomalous for a native O(E) sum) + the self-loop gate adds
number_of_selfloops overhead. The kernel's internals (extract_graph / degree
build) are the next lever to actually BEAT nx (filed under yxmdc).
