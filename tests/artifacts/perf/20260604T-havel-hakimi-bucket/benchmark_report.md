# is_valid_degree_sequence_havel_hakimi: O(n^2 log n) -> O(sum)

Lever: the Havel-Hakimi check re-sorted the ENTIRE degree list on every
reduction step (`while True: seq.sort(reverse=True); ...`) -- O(n^2 log n).
With the standard bucket method (nx's algorithm) it runs in O(sum of degrees):
keep a count array num_degs[d] = #nodes of degree d and reduce stubs without
re-sorting, plus the Zverovich-Zverovich early-accept
(4*dmin*n >= (dmax+dmin+1)^2). A complexity-class change, not a loop tweak.

## Benchmark (degree sequence of watts_strogatz)

| N    | fnx BEFORE | fnx AFTER | nx       |
|------|------------|-----------|----------|
| 1000 | 1.659 ms   | 0.137 ms  | 0.268 ms |
| 1500 | ~3.5 ms    | 0.250 ms  | 0.321 ms |

~12x faster; now faster than nx. (Ratio grew with N before -- 3.4x@200,
6.9x@1000 -- the O(n^2) signature.)

## Isomorphism proof

Boolean result bit-identical to the previous code AND networkx over 6111+
sequences (random length-1..22, real graphical sequences, edge cases:
empty/all-zero/odd-sum/over-degree), via both the direct entry point and
is_graphical(method="hh"); the "hh" and "eg" methods agree on every sequence
(both test graphicality) (test_havel_hakimi_bucket_parity, 4 cases). 19 existing
graphical/degree-sequence tests pass.

Companion to last session's is_graphical(eg) O(n^2)->O(n log n) fix
(1054b4622); is_valid_degree_sequence_havel_hakimi was the remaining O(n^2)
degree-sequence predicate.
