# dispersion: native integer-bitset kernel (br-r37-c1-o53cp)

The dict form of dispersion is the Backstrom-Kleinberg measure: for each node u
and neighbour v, count pairs {s,t} of common neighbours that are "dispersed"
(non-adjacent, sharing no neighbour inside N(u)\{u,v}). The Python path -- even
after the precomputed-adjacency-set fix (br-r37-c1-dispadj, ~1.2x) -- runs an
O(E * |common|^2) double loop of set operations, which explodes on dense graphs.

Lever (alien: bitset memory layout + word-parallel set ops): a native Rust kernel
builds one adjacency bitset per node, precomputes cn[s] = N(s) & N(u) once per u,
and evaluates the dispersion predicate with word-parallel AND/popcount-style
intersections. The predicate `t not in nbrs_s and nbrs_s.isdisjoint(N(t))` is
SYMMETRIC in (s,t) -- both reduce to "s,t non-adjacent and no w in N(u)\{u,v}
neighbours both" -- so each unordered pair is counted identically. disp is an
order-invariant integer, so the result is byte-for-byte identical to the Python
path; the float formula (disp+b)^alpha/(emb+c) uses the same libm pow.

Gated to undirected simple loop-free graphs with normalized=True (directed
dispersion needs successor-only neighbours; normalized=False returns int disp).
Directed / multigraph / self-loop / normalized=False fall back to Python.

Proof: golden sha256 over fnx.dispersion (full dict form) on an 80-graph corpus
IDENTICAL before and after (d9d18eef...); 295/295 value parity vs networkx
(undirected dense+sparse, directed/self-loop fall-backs, custom alpha/b/c,
normalized=False); 13 dispersion tests pass.

Interleaved min-of-13:

| n | p | m | nx (ms) | fnx (ms) | speedup |
|---|---|---|---|---|---|
| 80 | 0.10 | 324 | 1.185 | 0.143 | 8.30x |
| 120 | 0.06 | 447 | 1.406 | 0.195 | 7.22x |
| 200 | 0.05 | 1025 | 3.486 | 0.433 | 8.05x |
| 300 | 0.04 | 1867 | 6.932 | 0.797 | 8.70x |
| 400 | 0.03 | 2458 | 8.768 | 1.117 | 7.85x |
| 300 | 0.15 | 6758 | 571.75 | 8.57 | 66.72x |

before: 0.31x-0.33x SLOWER (~3x) [pre-dispadj]; 1.2x [dispadj].
after:  7.2x-9.8x FASTER (sparse), 66.7x FASTER (dense) -- bitset word-parallelism
        scales with density. Beat the 3-5x target.
