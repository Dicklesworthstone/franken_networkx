# astar_path / astar_path_length: sync once + gate weight scans (br-r37-c1-astgate)

A single-pair A* on an unweighted graph ran ~2.4ms vs networkx's ~0.05ms (~45x
SLOWER for a close target). The native A* search is only ~0.05ms -- the overhead
was the weight-validation machinery: each of the three negative/inf/nonnumeric
weight scans re-synced inner (4x redundant _sync_rust_edge_attrs) and all three ran
unconditionally even on unweighted graphs (three O(|E|) passes for nothing).

Lever: (1) check _should_delegate first (callable weight / cutoff) with no graph
work; (2) sync inner ONCE; (3) run the three O(|E|) weight scans only when a single
cheap native graph_has_edge_attr probe says the graph carries the weight attribute.
Behaviour is identical -- an unweighted graph never triggers negative/inf/nonnumeric,
so skipping the scans cannot change the delegation decision; weighted graphs (incl.
post-construction mutations, detected after the single sync) still run all scans.

Proof: astar parity vs networkx 0 mismatches over 120 weighted/unweighted/directed/
string graphs (values + error types); golden sha256; 88 existing astar tests pass.

before: ~2.38ms (n=400, close target) = ~45x slower than nx.
after:  ~0.54ms = 4.4x less work; unweighted single-pair now ~2.4x slower than nx
        (down from up to 45x). The residual is the mandatory O(|E|)
        _sync_rust_edge_attrs floor (the inner-AttrMap dual-representation tax);
        a sync-free / lazy-weight A* path is the deeper substrate lever.
