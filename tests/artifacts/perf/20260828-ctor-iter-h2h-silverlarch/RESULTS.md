# Constructor-from-iterator: the ledger's 0.31-0.79x rows do NOT reproduce, and the deficit
# has moved to the ATTRIBUTED-GENERATOR feed (br-r37-c1-q86hv)

SilverLarch, 2026-08-28. Both arms in ONE process on ONE pinned worker CPU in ONE invocation:
`rch exec -- cargo run --release -j 2 -p fnx-python --example ctor_iter_h2h`, against the
cdylib the same run built.

    bench_elf_sha256  5de9d710aaed90443806edc024a6a29d5b5d2f099f3a0307b98083a522518e9b
    fnx_extension     .rch-target-hz2-pool-.../release/lib_fnx.so
                      sha256=030e9292d2d8cea59a1fefd2953fd19ef51f52c601cd6e7ee7020564e5ec92bf
    incumbent         networkx 3.6.1, worker hz2, bench cpu 15
    fixture           n=2000, m=10000, every row verified same edge count on both arms

## Result: 9 of 20 rows quotable, 11 WITHHELD

    class         shape  feed     nx/fnx  null fnx  null nx   fnx ms    nx ms
    Graph         plain  list     2.489x     1.018    0.930    2.927    7.286
    Graph         attr   iter     0.782x     1.013    0.910   11.866    9.282
    Graph         attr   list     1.403x     1.016    0.967    6.649    9.328
    DiGraph       plain  iter     1.245x     1.004    0.940    6.167    7.678
    DiGraph       plain  list     1.529x     1.065    0.910    5.115    7.821
    DiGraph       attr   iter     0.849x     1.041    0.929   10.364    8.803
    MultiGraph    keyed  iter     1.068x     0.981    0.907   32.369   34.580
    MultiDiGraph  plain  iter     1.661x     1.028    1.030   16.313   27.099
    MultiDiGraph  attr   list     2.053x     1.016    1.051   16.879   34.655

    WITHHELD (11): Graph/plain/iter, DiGraph/attr/list, MultiGraph/plain/iter,
    MultiGraph/plain/list, MultiGraph/attr/iter, MultiGraph/attr/list,
    MultiGraph/keyed/list, MultiDiGraph/plain/list, MultiDiGraph/attr/iter,
    MultiDiGraph/keyed/iter, MultiDiGraph/keyed/list

THE WITHHOLD RATE IS ITSELF THE FIRST FINDING, and it was predicted in the harness before the
run rather than explained after it: construction is a MUTATION workload, the allocator is in a
different state on every repeat, so these arms are non-stationary. Nine of the eleven failures
are on the NETWORKX arm (nulls 0.539-1.554), which is the arm that moves a ratio in the
flattering direction, so they are withheld rather than published. Anyone re-running this should
expect to spend most of the budget on getting the nulls to land, not on the subject.

## The ledger's headline numbers do not reproduce

br-r37-c1-q86hv records these on HEAD 7208ffd57, 2026-07-10, and calls the lever "prepared;
blocked on a remote build". Where a row is quotable today:

    row                        ledger 2026-07-10   HEAD now    move
    DiGraph(iter(edges))                   0.789      1.245    1.58x
    DiGraph(iter(attr_edges))              0.349      0.849    2.43x
    MultiGraph(iter(keyed))                0.312      1.068    3.42x
    MultiDiGraph(iter(edges))              0.472      1.661    3.52x

Every quotable row has moved 1.6x to 3.5x toward parity, and two of them are now WINS. The
worst ratio in this repo's live ledger - `MultiGraph(iter(keyed))` at 0.312x - reads 1.068x.
The bead's premise, that the three non-`Graph` classes lose on the iterator path while `Graph`
is fixed, does NOT hold at HEAD.

This says nothing about the four rows whose nulls failed. `MultiGraph(iter(edges))` and
`MultiDiGraph(iter(keyed))` are not measured here, and their ledger values are neither
confirmed nor refuted.

## Where the deficit actually is now: the ATTRIBUTED GENERATOR

Two rows are still losses, and they are not the ones the bead names:

    Graph    attr iter   0.782x
    DiGraph  attr iter   0.849x

`Graph` is the class the bead's own GUARD row certifies as already fixed (0.982x on
`Graph(iter(edges))`). It is now the worst quotable row in the table, on the attributed feed.

`Graph`/attr is the ONE cell where both feeds are quotable, so it is the only clean
decomposition available:

    fnx   generator 11.866 ms   against its own list  6.649 ms   -> 1.78x
    nx    generator  9.282 ms   against its own list  9.328 ms   -> 0.995x, FLAT

networkx does not care whether the attributed edges arrive as a list or a generator. fnx pays
1.78x for the generator. That single difference is what flips the cell from a 1.403x WIN on a
list to a 0.782x LOSS on a generator, and it is a far more specific target than "iterator
ctors are slow".

MECHANISM NOT ESTABLISHED. The obvious reading is that the constructor can size a list up
front and cannot size a generator, so the attributed path re-allocates as it streams. That is
a hypothesis; this run measures the effect, not the cause, and the DiGraph pair that would
corroborate it had its list row withheld.

## Reproduce

    rch exec -- cargo run --release -j 2 -p fnx-python --example ctor_iter_h2h

Results print to STDERR. Both arms in one process on one pinned worker CPU; the binary
self-reports its own SHA-256 and the extension and networkx build it imported. Expect a high
withhold rate and budget for it.
