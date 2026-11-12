# effective_size: integer mark-array tie count (br-r37-c1-chq2a)

Burt's `effective_size` native kernel counted ties among each node's neighbors
with an O(deg^2) `graph.has_edge(nbrs[i], nbrs[j])` double loop -- String-keyed
substrate lookups that made it up to ~1.6x SLOWER than networkx on dense graphs
(the gap grew with average degree). Same tax class fixed in `constraint`
(br-constraint-intadj).

Lever: precompute integer adjacency once, then count ties with a reusable
mark-array -- mark N(u), and for each w in N(u) tally the neighbors of w that also
lie in N(u). Each intra-ego edge is counted from both endpoints, so ties = total/2.
No hashing, no has_edge round-trip; O(sum deg^2) work with O(1) bool probes. `ties`
is the same exact integer as before, so `deg - 2*ties/deg` is byte-identical.

Proof: golden sha256 over fnx.effective_size on an 80-graph corpus IDENTICAL before
and after (8e31fc00...); 303/303 value parity vs networkx (dense+sparse gnp +
complete/star/cycle/path/karate/wheel/barbell/subset/isolated); 79 existing
structural-holes tests pass.

Interleaved min-of-15:

| n | m | avgdeg | nx (ms) | fnx (ms) | speedup |
|---|---|---|---|---|---|
| 300 | 5451 | 36 | 5.813 | 3.717 | 1.56x |
| 400 | 6408 | 32 | 9.581 | 4.824 | 1.99x |
| 500 | 6202 | 25 | 9.863 | 5.186 | 1.90x |
| 600 | 7131 | 24 | 11.824 | 5.690 | 2.08x |
| 800 | 9613 | 24 | 20.954 | 10.132 | 2.07x |
| 1500 | 9008 | 12 | 32.831 | 10.722 | 3.06x |

before: 0.61x-0.96x SLOWER on dense graphs.  after: 1.56x-3.06x FASTER.
