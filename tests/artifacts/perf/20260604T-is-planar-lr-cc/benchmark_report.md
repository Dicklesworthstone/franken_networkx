# is_planar: native Left-Right planarity kernel (br-r37-c1-native-is-planar-boolean-zuxh1)

Boolean-only Rust port of networkx's LRPlanarity (orientation + testing phases;
embedding omitted). Replaces is_planar's O(n^2) fnx->nx conversion + nx's pure-
Python LR embedding. Was 1.6x (n=300) -> 4.4x (n=1000) SLOWER (gap grew with n);
now ~10x FASTER across all sizes.

Parity: 815-graph golden corpus (458 planar / 357 non-planar incl K5/K6/K3,3/K4,4/
Petersen/Heawood/Moebius-Kantor + 600 random gnp + 200 grid+chord); 0 mismatches
vs networkx; golden sha256 in golden_sha256.txt.

Warm min-of-11, planar grid graphs (non-planar inputs short-circuit via Euler bound):

| graph | n | m | nx (ms) | fnx (ms) | speedup |
|---|---|---|---|---|---|
| grid 10x10 | 100 | 180 | 1.925 | 0.175 | 10.99x faster |
| grid 18x18 | 324 | 612 | 6.458 | 0.601 | 10.74x faster |
| grid 25x25 | 625 | 1200 | 13.047 | 1.165 | 11.20x faster |
| grid 32x32 | 1024 | 1984 | 21.504 | 1.969 | 10.92x faster |
