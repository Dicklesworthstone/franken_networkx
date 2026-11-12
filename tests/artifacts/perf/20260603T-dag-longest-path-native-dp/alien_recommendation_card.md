# Alien Primitive Card

- Skill pass: `/alien-graveyard` plus `/extreme-software-optimization`
- Borrowed primitive: communication-avoiding adjacency snapshot for graph dynamic programming.
- Local application: replace per-node predecessor-view materialization with one bulk in-edge snapshot, then run stable Python DP over compact predecessor lists.
- Safety boundary: exact `DiGraph` only; views, subclasses, multigraphs, explicit topo orders, and unsupported native helpers fall back.
- Target ratio: close the 4.26x direct current-vs-NetworkX gap on the deterministic 400-node DAG by removing the profiled AtlasView predecessor walk.
- Observed result: FNX direct per-call pair improved `0.00866313304999494s -> 0.002495367919909768s` (`3.47x`), and rch hyperfine improved `1.00276056072s -> 0.4922190647400001s` (`2.04x`).

