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

## THE MEASUREMENT DID NOT HAPPEN, AND THE REASON IS THE ENVIRONMENT

No vs-incumbent ratio is reported here. The prescribed route is a worker-side head-to-head,
and NINE sync attempts across two workers all failed in the transfer stage, before any Cargo
ran:

    sync_to_remote: timed out after 145000ms   (hz3, attempts 1/3, 2/3, 3/3)
    sync_to_remote: timed out after 145000ms   (hz4, attempts 1/3, 2/3, 3/3, then 1/3 again)
    [RCH] source sync failed before remote Cargo execution after 3/3 attempts;
          remote Cargo was not started

That is a stable blocker rather than bad luck, and the cause is measurable. rch already
excludes `.git/`, `.beads/`, `target/` and `tests/artifacts/`, so the 4 GB working tree is
not what ships - but `fuzz/` (241M), `venv/` (201M) and `artifacts/` (40M) are NOT in
`exclude_patterns`, leaving ~500M to cross the wire inside a 145 s budget while 7+ builds
from sibling projects contended for the same 14 workers.

THE OBVIOUS FIX WAS NOT APPLIED, deliberately. Adding `venv/` and `fuzz/` to
`exclude_patterns` in `~/.config/rch/config.toml` would likely unblock this, but that file is
shared by every project and agent on this host, and `fuzz/` holds real cargo-fuzz build
targets that somebody else's remote build may legitimately need. Silently narrowing a shared
config to unblock one measurement is not a trade this bead authorises. It is recorded here so
the owner can decide.

Local builds are forbidden and no local ELF may be retrieved, so there was no admissible way
to produce a number. **A ratio measured some other
way would not be the same claim**, so none is offered - the landing commit's 0.8237x /
0.8646x stands unconfirmed by this session rather than being restated as if reproduced.

TWO OPERATIONAL FINDINGS worth more than the missing number, because they are reusable:

  * **`rch exec` needs an explicit `-j`.** Without one, the job was refused with
    `no admissible workers: insufficient_total_slots=10` - 10 of 14 workers rejected the job
    outright for requesting more parallelism than they have. Adding `-j 2` made it
    admissible immediately. Sibling projects all pass `-j 1` / `-j 2`; this repo's
    documented invocations do not.
  * **`active_project_exclusion` is not always a peer.** It appeared while `rch queue`
    showed no other franken_networkx build, i.e. it can be a stale entry from one's own
    killed job.

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

## The harness ships here, NOT in examples/, and it has never been compiled

`predecessors_family_h2h.rs.uncompiled` in this directory is the head-to-head described
above. It is deliberately NOT in `crates/fnx-python/examples/`, where it began:
`cargo check --workspace --all-targets` compiles that directory, this is a SHARED checkout,
and the only route permitted for compiling anything - rch - is the very thing that is
blocked. Committing an unverified Rust file into the build path would hand every peer in this
tree a compile error I could not have detected. The extension is `.uncompiled` for the same
reason.

Its Python half IS verified: the timing block was extracted and executed against the
installed extension and live networkx, exercising all eight cells end to end, and the
`compile()` check passes. Only the Rust wrapper around it is unproven.

TO USE IT: move it to `crates/fnx-python/examples/predecessors_family_h2h.rs`, then

    rch exec -- cargo run --release -j 2 -p fnx-python --example predecessors_family_h2h

Results print to STDERR. Both arms run in one process on one pinned worker CPU in one
invocation; the binary self-reports its own SHA-256 and the extension and networkx build it
imported. The `-j 2` is load-bearing - see above. Expect to fix compile errors first.
