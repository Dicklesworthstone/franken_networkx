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

## SECOND RUN: the mechanism is a MISSING KERNEL, established without timing

Reading the source rather than guessing at the "cannot size a generator" hypothesis from the
first run: `br-r37-c1-mgaefgen` already found and fixed exactly this shape. Its comment records
that the native batch kernels are gated on `isinstance(ebunch_to_add, (list, tuple))`, so
"handing this function a GENERATOR disqualified every one of them and fell through to the
per-edge Python loop", and it materialises the generator to make them reachable again — for the
MULTIGRAPH classes. Its own note says "DiGraph is unaffected ... this is multigraph-only".

That points at a partially applied fix, and the check is deterministic — no timing, no nulls:

    class           plain batch   ATTR batch   str-keyed batch
    Graph                  True        False             False
    DiGraph                True        False             False
    MultiGraph             True         True              True
    MultiDiGraph           True         True             False

`_try_add_attr_edges_from_batch` EXISTS ON BOTH MULTIGRAPH CLASSES AND ON NEITHER SIMPLE CLASS.
The simple-class `add_edges_from` retry after materialisation (`br-aefgenbatch`) calls only
`_try_add_edges_from_batch`, the plain-2-tuple kernel, which declines a 3-tuple carrying a data
dict — so on `Graph` and `DiGraph` an ATTRIBUTED bunch has no bulk path at all, from a list or
from a generator. That is a concrete missing kernel, named, and it does not depend on any
ratio.

## The timing half, and what it does NOT establish

    class         shape  feed     nx/fnx  null fnx  null nx   fnx ms    nx ms
    DiGraph       plain  iter     1.133x     1.090    1.082    9.109   10.321
    MultiGraph    plain  iter     1.288x     1.079    1.031   25.251   32.516
    MultiGraph    plain  list     1.920x     1.078    1.012   16.341   31.370
    MultiGraph    attr   iter     1.744x     0.980    0.965   18.037   31.463
    MultiGraph    attr   list     2.225x     0.990    1.007   13.679   30.434
    MultiDiGraph  plain  iter     1.353x     1.034    0.993   19.564   26.479
    MultiDiGraph  plain  list     1.398x     1.048    0.958   18.207   25.446
    MultiDiGraph  attr   iter     1.360x     0.971    0.973   23.481   31.922
    MultiDiGraph  attr   list     1.776x     1.001    0.990   17.468   31.026

    WITHHELD (7): every Graph row, and DiGraph plain/list, attr/iter, attr/list.

THE MULTI CLASSES WIN ON ATTRIBUTED INPUT — 1.360x to 2.225x, every null in band — which is
what having the attr kernel looks like.

THE SIMPLE-CLASS ATTRIBUTED LOSS IS NOT ESTABLISHED BY THIS RUN, and saying so matters more
than repeating the first run's number. Every `Graph` row and three of four `DiGraph` rows were
withheld: precisely the cells that carry the hypothesis. `Graph attr iter` read 0.653x with an
fnx-arm null of 0.899 — just outside the band, directionally consistent with the first run's
0.782x but NOT quotable. So the loss has been observed once with passing nulls (first run) and
once un-quotably (this run). It is not contradicted; it is under-measured, and one quotable
observation is not two.

THE NULL FIXES WORKED, BUT ONLY WHERE THEY WERE NOT NEEDED MOST. Interleaving the two payload
builds element by element, shortening the slots (21 rounds x 1 call), and disabling the cyclic
collector across the timed region took the MULTI classes from mostly-withheld to 8/8 quotable
with nulls in 0.958-1.079. The simple classes got worse, not better. Their fixtures are the
cheapest to build and their constructors the fastest, so their slots are the shortest and the
most exposed to whatever the host is doing — which is the opposite of the regime the fix was
designed for. A future run on these cells should raise the per-slot work rather than lower it.

## THIRD RUN: the simple-class attributed-generator loss REPLICATES

Narrowed to the two simple classes (the previous run went 8/8 on the multi classes and withheld
almost every simple-class row), raised to 41 rounds, and run as TWO INDEPENDENT PASSES in one
invocation. Replication is the point: an A/A null certifies stationarity WITHIN a pass and says
nothing about common-mode drift BETWEEN passes, so agreement across passes is what makes a
number citable.

    bench_elf_sha256  6d55ef7c8c7858513ddad1ef1358353fed5bb562e4f0b2943898cc143e108dbc
    fnx_extension     .rch-target-hz2-pool-.../release/lib_fnx.so
                      sha256=030e9292d2d8cea59a1fefd2953fd19ef51f52c601cd6e7ee7020564e5ec92bf
    incumbent         networkx 3.6.1, worker hz2, bench cpu 15

    pass   class     shape  feed     nx/fnx  null fnx  null nx   fnx ms    nx ms
    pass1  Graph     plain  iter     1.769x     1.003    0.937    4.823    8.531
    pass1  Graph     plain  list     2.170x     1.084    0.960    3.770    8.180
    pass1  Graph     attr   iter     0.632x     0.995    0.996   16.998   10.748
    pass1  DiGraph   plain  iter     1.351x     1.057    0.941    6.809    9.202
    pass1  DiGraph   attr   iter     0.882x     1.014    0.973   12.955   11.423
    pass2  Graph     attr   iter     0.806x     0.956    0.923   14.591   11.765
    pass2  DiGraph   plain  iter     1.327x     1.040    0.952    6.884    9.136
    pass2  DiGraph   plain  list     1.536x     1.095    0.917    5.489    8.429
    pass2  DiGraph   attr   iter     0.874x     0.971    0.935   13.075   11.427

    WITHHELD (7): Graph attr/list both passes, Graph plain/iter + plain/list pass2,
    DiGraph plain/list pass1, DiGraph attr/list both passes. EVERY withheld row failed on
    the FNX arm (nulls 1.084-1.266); no row failed on the networkx arm.

### Replication

    cell                   pass1   pass2   spread   verdict
    Graph attr iter        0.632   0.806    27.5%   direction only
    DiGraph attr iter      0.882   0.874     0.9%   REPLICATED
    DiGraph plain iter     1.351   1.327     1.8%   REPLICATED

**`DiGraph(iter(attr_edges))` is a REPLICATED LOSS at 0.874-0.882x** — two independent passes
0.9% apart, all four nulls in band. That is the citable number this whole line of work was
after, and it is the first time this cell has been measured twice with both passes quotable.

`Graph(iter(attr_edges))` replicates in DIRECTION only: both passes are losses, 0.632x and
0.806x, but 27.5% apart. The LOSS is established; the MAGNITUDE is not, and no single figure
should be quoted for it.

`DiGraph(iter(edges))` is a replicated WIN at 1.327-1.351x, which is the control: the same
class, the same generator feed, differing only in whether the edges carry attributes. The
plain feed reaches the native batch and wins; the attributed feed has no kernel to reach and
loses. That contrast, within one class and one feed shape, is the cleanest evidence here that
the missing `_try_add_attr_edges_from_batch` is the cause rather than "generators are slow".

### What is still NOT established

The generator-versus-list penalty INSIDE the simple classes. Every `attr list` row was
withheld in both passes, so there is no quotable list arm to divide the generator arm by. The
first run's "fnx pays 1.78x for the generator where networkx is flat" figure rests on a single
pass and is NOT confirmed here; it should not be cited. The vs-networkx ratio for the
attributed generator is what replicated, and that is all.

The withhold pattern also inverted between runs — the previous run lost nine rows on the
networkx arm, this one lost all seven on the fnx arm, mostly on the `list` feed. Both arms of
this workload are non-stationary, in different ways on different days.

## Reproduce

    rch exec -- cargo run --release -j 2 -p fnx-python --example ctor_iter_h2h

Results print to STDERR. Both arms in one process on one pinned worker CPU; the binary
self-reports its own SHA-256 and the extension and networkx build it imported. Expect a high
withhold rate and budget for it.
