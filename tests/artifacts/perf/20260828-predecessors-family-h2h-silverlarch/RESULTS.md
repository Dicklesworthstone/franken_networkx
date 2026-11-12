# DiGraph.predecessors: the bead is STALE, the conversion is parity-clean, and the
# measurement was blocked (br-r37-c1-predrow-8vytj)

SilverLarch, 2026-08-28.

## THE BEAD'S PREMISE NO LONGER HOLDS

`br-r37-c1-predrow-8vytj` is still in `br ready` and still reads as an open lever:

> `DiGraph.predecessors` is a PYTHON function that keeps its own keydict cache in the
> instance dict [...] `PyDiGraph` has no `_native_predecessors_iter`, and simply adding one
> is a LOSS rather than a win.

Both sentences are false at HEAD. The fix landed on 2026-08-24 in **4cbb18f78**, which cites
this bead by name and reports 0.383x -> 0.8237x. At HEAD:

    python/franken_networkx/__init__.py:52127
        DiGraph.predecessors = _fnx.DiGraph._native_predecessors_iter

    >>> fnx.DiGraph.predecessors is _fnx.DiGraph._native_predecessors_iter
    True
    >>> type(fnx.DiGraph.predecessors).__name__
    'method_descriptor'

All four family members - `DiGraph`/`MultiDiGraph` x `predecessors`/`successors` - are now
native method descriptors with no Python frame. An agent taking this bead off `br ready`
would re-implement work that is four days old. The beads DB has been refusing all writes for
this whole session (`database disk image is malformed: table comments rowid 3627 stores 38
payload columns but schema allows at most 5`), so this artifact and its commit are the only
durable record; the bead itself could not be closed.

## WHAT WAS VERIFIED (no worker required)

The bead named three specific risks for exactly this conversion and demanded "the
mutation-matrix treatment ... not a spot check". None of them had been independently checked
against live networkx at HEAD. All are clean:

    probe                                          steps   divergences
    randomised mutation fuzz, 2 classes x 6 seeds    480             0
    private storage: assigned _pred is authority       -             0
    unhashable node -> TypeError, absent -> error      -             0
    landing commit's own guard suite                 21 passed

The fuzz drives random add_edge / remove_edge / add_node / remove_node / clear_edges over
mixed key types (int, str, a 2000-character key), WARMS the index twin before each mutation,
and compares every node's row against networkx after every single step. Warming first is the
point: a stale row is invisible until the map behind it moves, and `restamp_neighbor_rows`
can launder a stale stamp on the next `add_edge` (br-r37-c1-txkrn).

BOTH PROBES WERE PROVEN TO HAVE TEETH, because a green probe that cannot fail certifies
nothing:

  * against a `predecessors` that ignores assigned private storage - the br-r37-c1-ppiei
    defect - the parity probe caught 2/2 (it returned the STORE's predecessors where nx
    reads the assigned mapping, and raised KeyError where nx returns an empty row);
  * against a row cache that never invalidates - the br-r37-c1-txkrn defect class - the
    fuzz pattern caught 3 divergences.

No new test file was added. The landing commit already contributed 21 guards covering this
surface and they pass; a parallel file asserting the same contract would be conformance
metastasis, not coverage.

## THE MEASUREMENT, second turn: the 0.383x is GONE and the family has converged

    bench_elf_sha256  680e59f73764a13fbf4450ef332c5ce8ad495f183117f3f305e48038eb2aa652
    fnx_extension     python/franken_networkx/_fnx.abi3.so
                      sha256=cd17e9fcc7e470b0120a59f2eb5106fecfedbb8f3a34c979255ed8c06428a935
    incumbent         networkx 3.6.1 @ /home/ubuntu/.local/lib/python3.14/site-packages/
    worker            hz4, bench cpu 63, one process, one invocation

QUOTABLE ROWS - 3-character str node keys, in-degree 3, both nulls in band:

    class         method         nx/fnx   null fnx   null nx   fnx ns   nx ns
    DiGraph       predecessors   0.960x      1.030     0.990    499.0   479.3
    DiGraph       successors     0.954x      1.026     0.990    498.4   475.7
    MultiDiGraph  predecessors   0.939x      1.024     1.000    509.6   478.7
    MultiDiGraph  successors     0.924x      1.026     0.996    515.6   476.3

**DiGraph.predecessors reads 0.960x, not 0.383x.** The bead's headline outlier is gone. It is
STILL A LOSS - 4% short of parity, and no win is claimed - but it is no longer separable from
its own controls.

THE FAMILY HAS CONVERGED, WITH NO MEMBER DISTINGUISHABLE. All four sit in 0.924-0.960x, a
spread of 3.6 points, against A/A nulls that are themselves 2.4-3.0% off unity. The spread
across the family is the same size as the spread between two separately built fixtures of the
SAME graph, so the apparent ordering inside the family is not a real ranking and is not read
as one here. What can be said is the thing the bead asked: the SAME class's successors and the
OTHER class's predecessors no longer stand apart from the subject.

The residual is ~20-40 ns on a ~480 ns operation, which is the size of the two floors already
named in br-r37-c1-native-method-attribute-lookup-tax-w7wjs (attribute lookup ~8-12 ns, the
one-arg crossing ~12 ns). Nothing here contradicts that taxonomy.

## THE DUAL NULL EARNED ITS KEEP, IN THE OPPOSITE DIRECTION FROM THE ONE EXPECTED

NOT QUOTABLE - 2000-character str node keys, same fixtures, same run:

    class         method         nx/fnx   null fnx   null nx   fnx ns   nx ns
    DiGraph       predecessors   1.170x      1.186     0.995    507.1   593.4
    DiGraph       successors     1.154x      1.180     1.000    504.1   581.7
    MultiDiGraph  predecessors   1.142x      1.174     1.002    521.2   595.1
    MultiDiGraph  successors     1.121x      1.190     1.013    516.4   579.1

Every one of those four rows would have read as a 1.12-1.17x WIN. All four are DISQUALIFIED:
the fnx-arm null is 1.174-1.190, i.e. two separately built fnx fixtures of the identical graph
differ by ~18% at long keys, so the arm cannot be timed against the incumbent at all here.

The instructive part is which null caught it. The landing commit (4cbb18f78) failed on its
NETWORKX arm with a clean fnx arm; this run is the exact mirror - the networkx null is clean
(0.995-1.013) and the fnx arm is the broken one. Gating on either arm alone would have passed
these rows and published four wins. This is [[separately_built_fixtures_differ]] magnified by
key length, and it is why the harness carries both nulls rather than one.

Because those rows are void, NO claim is made here about fnx being flat in key length - which
is precisely the property the conversion was built for. The networkx arm alone is internally
consistent (its own null passes) and grows 479 -> 593 ns, +24%, between the two key lengths;
the fnx side of that comparison is not measurable from this run.

## THIS RUN DISAGREES WITH THE LANDING COMMIT, AND THAT IS NOT A CORRECTION

4cbb18f78 measured DiGraph.predecessors at 0.8237x; this run reads 0.960x. Both agree the
0.383x outlier is closed and the family converged, and they disagree on the residual by ~17
points. The two differ in host (rch worker hz4 against thinkstation1), fixture (circulant
N=1000 at in-degree 3 against E=400), and load, and the absolute times differ by 2.5x
(499 ns against 195.3 ns for the same cell), so neither is offered as a correction of the
other. Harness disagreement of this size is itself the finding, and the honest reading is that
the residual is somewhere in 0.82-0.96x rather than pinned.

## THE SYNC BLOCK FROM THE PREVIOUS TURN IS FIXED, AND THE FIX IS IN THE REPO

The previous turn recorded nine sync timeouts and no measurement. The cause was found:
`rch config show` excludes `.git/`, `.beads/`, `target/` and `tests/artifacts/`, but NOT this
repo's two Python virtualenvs - `.venv` is 444M and `venv` is 201M, about 60% of a ~1.1G
payload that has to cross the wire inside a 145 s budget.

A project-local `.rchignore` now excludes them plus three tool caches. Every pattern in it is
gitignored, so nothing tracked can be lost. rch confirms it loads
(`Exclude patterns: 44 (39 from config, 5 from .rchignore)`), and the transfer that had failed
ten consecutive times then completed:

    Loaded 3 pattern(s) from .rchignore (total: 50)
    Sync completed in 126348ms
    Sync complete: 63727 files, 4485087 bytes

126 s against a 145 s budget - inside it, but not by much. CAUSATION IS NOT PROVEN by one
success: worker contention varies, and this attempt also landed on a worker holding partial
data from earlier passes. What is certain is the payload arithmetic and that the block cleared
on the first attempt after the file was added. The global
`~/.config/rch/config.toml` was deliberately left alone - it is shared by every project and
agent on this host.

Separately, the dependency-preflight stage took 15 minutes before the transfer even began
(21:50:49 -> 22:05:51). That is a second, independent bottleneck and it is NOT addressed here.

## TWO MEASUREMENT-DESIGN CORRECTIONS, MADE BEFORE SPENDING A SLOT

Recorded because the harness is committed and both errors would have produced a confident
wrong number rather than an obvious failure.

**The K axis is NODE KEY LENGTH, not row width.** The bead's table is read most naturally as
in-degree. It cannot be. Its networkx arm moves 149.4 -> 233.8 ns between K=3 and K=2000, and
materialising a 2000-element row could not cost 84 ns - that is microseconds of work. K is
characters, and the landing commit confirms it ("FLAT in node key length", "2000-character
keys"). This matters beyond bookkeeping: key length is the axis the fix was BUILT for, since
the Python shim was flat in it and a native path resolving a fresh canonical each call would
have LOST at long keys. The first draft of this harness varied in-degree and would have
measured an axis on which nothing was ever claimed.

**A single fnx/fnx A/A null is blind to the failure the landing commit actually hit.** That
commit reports all four of its rows NULL-FAILED on the NETWORKX arm (0.972-0.975) with a
clean fnx arm (0.991-1.001). A null built from two fnx fixtures reads ~1.000 through exactly
that condition, and an incumbent arm being systematically advantaged moves a LOSS ratio in
the flattering direction. The committed harness therefore carries DUAL nulls - a separately
built fnx fixture against the fnx arm and a separately built networkx fixture against the
networkx arm - and disqualifies a row if EITHER strays from 1.0.

## The harness

`crates/fnx-python/examples/predecessors_family_h2h.rs` - COMPILES, verified on hz4 in the
run above (the one warning in that build is pre-existing dead code in `fnx-python`'s lib,
`private_adj_row` never used, not from this file).

The previous turn could not compile it - the only permitted route, rch, was the very thing
blocked - so it was parked in this directory as `predecessors_family_h2h.rs.uncompiled`
rather than left in the build path of a SHARED checkout where a peer's
`cargo check --workspace --all-targets` would have hit it. That copy is byte-identical to the
file now in `examples/` and is retained only because this repo forbids deleting files without
explicit permission; it is superseded and can be removed on request.

    rch exec -- cargo run --release -j 2 -p fnx-python --example predecessors_family_h2h

Results print to STDERR. Both arms run in one process on one pinned worker CPU in one
invocation; the binary self-reports its own SHA-256 and the extension and networkx build it
imported. The `-j 2` is load-bearing - without an explicit `-j`, 10 of 14 workers refuse the
job outright with `insufficient_total_slots`.
