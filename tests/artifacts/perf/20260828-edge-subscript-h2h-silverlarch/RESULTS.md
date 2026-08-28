# Edge-attribute lookup: the bead's 0.211x is stale by 2.5x, and the real mechanism is a
# CLASS asymmetry, not the canonical rehash (br-r37-c1-tjp0g)

SilverLarch, 2026-08-28. Both arms in ONE process on ONE pinned worker CPU in ONE invocation:
`rch exec -- cargo run --release -j 2 -p fnx-python --example edge_subscript_h2h`.

    bench_elf_sha256  0a596f70a5e9fb3f42f7aa4f6dba50c00d954882086c43b05e652519edf8b34b
    fnx_extension     _fnx.abi3.so sha256=cd17e9fcc7e470b0120a59f2eb5106fecfedbb8f3a34c979...
    incumbent         networkx 3.6.1 @ /home/ubuntu/.local/lib/python3.14/site-packages/
    worker            hz2, bench cpu 15

## Result

    key   class    spelling      nx/fnx   null fnx   null nx   fnx ns   nx ns
    str   Graph    edges[u,v]    0.901x      1.023     0.962    175.0   157.7
    str   Graph    G[u][v]       1.147x      1.047     0.971    253.6   290.9
    str   DiGraph  edges[u,v]    0.557x      0.962     0.970    264.1   147.2
    str   DiGraph  G[u][v]       0.605x      1.032     0.990    423.6   256.2
    int   Graph    edges[u,v]      --        1.044     0.878    287.5   280.7   WITHHELD
    int   Graph    G[u][v]       1.195x      1.040     1.056    251.4   300.5
    int   DiGraph  edges[u,v]    0.532x      0.951     1.084    260.9   138.9
    int   DiGraph  G[u][v]       0.640x      1.007     0.994    410.6   262.9

Seven rows quotable. ONE WITHHELD rather than published: int/Graph/`edges[u,v]` had a
networkx-arm null of 0.878, i.e. two separately built networkx fixtures of the identical graph
differed by 12%, so that arm could not be timed against fnx at all. Its apparent 0.976x is not
reported as a number. Both nulls gate every row here because the arm being distorted is the one
that moves the ratio, and previous runs in this family have failed on EACH side in turn.

## THE BEAD'S NUMBERS ARE STALE BY ~2.5x, IN BOTH DIRECTIONS

br-r37-c1-tjp0g records, from 2026-08-16 on ELF cf5056fdb7f0e6e0:

    fnx G.edges[u,v] (DiGraph, full)   546.5 ns      nx 115.2 ns   -> 0.211x
    and "routing to a native slot should reach roughly Graph's 0.6793x"

Neither holds on HEAD. DiGraph `edges[u,v]` is **0.557x (str) / 0.532x (int)**, not 0.211x, and
the undirected Graph reference is **0.901x**, not 0.6793x. The fnx arm has roughly halved
(546.5 -> 264.1 ns). At least one landed change is visible in the source itself: the
`__getitem__` hit path now carries a br-r37-c1-q4wzt comment recording the removal of a
membership probe "measured at 41.7ns for the membership probe alone", which post-dates the
bead.

STILL A LOSS AND NO WIN IS CLAIMED. 0.53-0.56x is the worst ratio measured in this family and
worth attacking - it is simply not the 5x catastrophe the ready queue advertises, and anyone
sizing work off the bead's number would be sizing off a figure that is twice too pessimistic.

## THE DOMINANT EFFECT IS A CLASS ASYMMETRY, AND IT HAS A STRUCTURAL CAUSE

Same operation, same key type, same run:

    Graph    edges[u,v]   fnx 175.0 ns   nx 157.7 ns   0.901x
    DiGraph  edges[u,v]   fnx 264.1 ns   nx 147.2 ns   0.557x

networkx is FLAT across the two classes (157.7 against 147.2 ns - it is marginally CHEAPER on
the digraph). The entire ~90 ns gap is fnx-side and class-specific. The cause is visible by
probing what each class's view actually is, which costs nothing to check:

    Graph         edges view EdgeView          __getitem__ = wrapper_descriptor  (NATIVE slot)
    DiGraph       edges view OutEdgeView       __getitem__ = function            (PYTHON body)
    MultiGraph    edges view MultiEdgeView     __getitem__ = function            (PYTHON body)
    MultiDiGraph  edges view OutMultiEdgeView  __getitem__ = function            (PYTHON body)

The undirected class answers the subscript in a native slot with no Python frame; the other
three run a Python `__getitem__`. That is the same shape as the five wins already recorded
under the Python-shim-on-a-native-slot pattern, and it is a better-evidenced lever than the one
the bead proposes.

A NATIVE DIRECTED EDGE VIEW ALREADY EXISTS AND IS UNREACHABLE. `_fnx.DiEdgeView` is registered
(`m.add_class::<DiEdgeView>()`), has a native `__getitem__` wrapper_descriptor, and is returned
by a Rust `edges()` at crates/fnx-python/src/digraph.rs:15702 - but `DiGraph.edges` hands back
`OutEdgeView`, whose MRO is `['OutEdgeView', 'object']`, so the native class is never in the
lookup chain. It also cannot be built from Python (`cannot create
'franken_networkx.DiEdgeView' instances`). The Python view is presumably there to carry
networkx's full EdgeView surface (`__call__`, `.data()`, set algebra, nx's exact KeyError
ordering), so this is NOT a "just rebind it" fix - but the native half of it is already written.

## WHAT THIS RUN DOES **NOT** SHOW: the bead's stated mechanism

The bead attributes the cost to string canonicalisation - fnx builds `"str:{len}:{s}"` and
SipHashes those bytes every call, where "CPython pays neither" because a str caches its hash.
This run does not support or refute that, and it is important not to read it as doing either:

    DiGraph  edges[u,v]   str 0.557x     int 0.532x
    DiGraph  G[u][v]      str 0.605x     int 0.640x

int and str behave the same within ~5%. That is NOT evidence against the rehash, because fnx
canonicalises INT keys to strings too (`write_int_decimal`), so both arms of this comparison
pay a canonicalisation - the axis does not discriminate.

WHAT DISCRIMINATES IT IS KEY LENGTH, AND EVERY ROW ABOVE IS SHORT-KEY. That is the regime in
which this lever is already known to have nothing to win, so these numbers cannot be used to
judge the bead's proposal in either direction.

## Consequence for the bead

The bead's acceptance criterion is "`G.edges[u,v]` crosses 1.0x on at least the simple
classes". The undirected simple class is already at 0.901x with `G[u][v]` at 1.147-1.195x - a
WIN - so most of what the bead asks for on the simple classes has arrived by other means. What
remains is the directed and multi classes, and the evidence here points at the Python-bodied
`__getitem__` rather than at an object-keyed lookaside.

THE BEAD'S OWN LEVER IS NOT REFUTED BY ANY OF THIS - IT IS SIMPLY IN A REGIME THIS RUN DID NOT
MEASURE, and that is worth stating plainly because the opposite is easy to conclude from the
table above. The cached-index shape the bead proposes was rejected under br-r37-c1-p1tvg and
then re-run under br-r37-c1-ptiz2 (fdf7f061a) on the sibling operation `(u,v) in G.edges`:

    (u,v) in G.edges  len=8000    0.0844x -> 1.0972x   (13x, the lever's regime)
    (u,v) in G.edges  len=3       1.0560x -> 1.0852x   (CONTROL, no regression)
    all eight A/A nulls 1.0004-1.0056

p1tvg's rejection is correct and REGIME-SCOPED: at short keys the row was already ahead of
networkx, so an index path can only shave a cost that is not there. The cost it removes scales
with key LENGTH. Every row in this artifact is short-key, so this run sits squarely inside the
regime where that lever is expected to do nothing, and says nothing about the regime where it
returned 13x.

Two levers are therefore live, not one, and they are complementary rather than competing: the
CLASS asymmetry (Python-bodied `__getitem__` on the directed and multi views) which this run
does evidence, and the KEY-LENGTH rehash which it does not reach. Note also that fdf7f061a
measured 8000-character keys with all eight nulls inside 1.0004-1.0056, so the long-key regime
IS cleanly measurable - the ~18% fnx-arm null failure the predecessors run hit at 2000-char
keys is a limitation of THAT harness, not of the axis. Its harness is the model to copy.

NOT ATTEMPTED HERE: giving the directed view a native `__getitem__`. It is a real Rust change
with a real parity surface - nx's exact KeyError ordering (`hash(u)`, membership, `hash(v)`),
the slice error, the unhashable TypeError, and the held-view private-storage contract pinned in
test_held_edge_view_private_storage_parity.py - and it wants its own measurement rather than
being bundled into a re-measurement commit.

## SECOND RUN: the cost is DECOMPOSED, and worker-side Rust A/B now works

Same harness plus a third spelling, `G.get_edge_data(u, v)` - the native lookup reached
directly, with no EdgeView subscript in front of it. Subtracting it from `edges[u,v]` on the
SAME class in the SAME invocation separates the view's cost from the lookup's.

    bench_elf_sha256  1d8f3d4a52022a79f74d156fd237b05a33bac7ff1c8b7a59aa34abf80426b8a0
    fnx_extension     .rch-target-hz2-pool-.../release/lib_fnx.so
                      sha256=d8062460576fc98b210ba6111e06c84ce4d404e985f80d4b015bce084cf153b1
    incumbent         networkx 3.6.1, worker hz2, bench cpu 15

    key   class    spelling         nx/fnx   null fnx   null nx   fnx ns   nx ns
    str   Graph    edges[u,v]       0.842x      1.071     0.945    195.7   164.8
    str   Graph    G[u][v]          1.078x      1.071     0.959    273.1   294.3
    str   Graph    get_edge_data    0.653x      1.070     1.013    149.2    97.4
    str   DiGraph  edges[u,v]       0.494x      1.067     0.999    273.7   135.3
    str   DiGraph  G[u][v]          0.546x      1.019     0.997    471.2   257.4
    str   DiGraph  get_edge_data    0.671x      1.079     0.993    146.0    97.9
    int   Graph    edges[u,v]       0.706x      0.966     0.957    216.0   152.6
    int   Graph    G[u][v]          1.025x      0.984     0.957    265.3   271.9
    int   Graph    get_edge_data    0.614x      1.002     1.000    157.4    96.6
    int   DiGraph  edges[u,v]       0.468x      0.981     0.996    281.2   131.7
    int   DiGraph  G[u][v]          0.563x      1.024     1.017    438.9   247.1
    int   DiGraph  get_edge_data    0.620x      0.986     0.984    156.2    96.8

All 12 nulls in band. The str fnx-arm nulls sit at 1.067-1.079, higher than the previous run's
0.951-1.047 - inside the gate but drifting, which is why the decomposition below is read off
DIFFERENCES within a single run rather than across runs.

### The native lookup is CLASS-INDEPENDENT; the view is not

    key   class    edges[u,v]   get_edge_data   fnx VIEW cost   nx VIEW cost
    str   Graph        195.7          149.2            46.5           67.4
    str   DiGraph      273.7          146.0           127.7           37.4
    int   Graph        216.0          157.4            58.6           56.0
    int   DiGraph      281.2          156.2           125.0           34.9

**The native lookup costs the same on both classes** - 149.2 against 146.0 ns (str), 157.4
against 156.2 (int). The directed lookup is NOT slower; the difference between 1-3 ns is noise.

**The view is where the classes diverge.** The undirected native slot adds 46.5-58.6 ns; the
directed PYTHON `__getitem__` adds 125.0-127.7 ns. That +66 to +81 ns IS the class asymmetry,
and it is now attributed rather than inferred from a structural probe.

### What each lever can actually buy, with a ceiling

For str/DiGraph, nx's whole `edges[u,v]` call is 135.3 ns against fnx's 273.7:

  * give the directed view the undirected view's overhead (127.7 -> 46.5 ns):
    273.7 -> 192.5 ns, i.e. **0.494x -> ~0.70x**, a 1.42x gain on the cell;
  * a hypothetical FREE view (overhead 0) reaches 146.0 ns -> ~0.93x. Still not parity.

So the class-asymmetry fix cannot reach 1.0x by itself, because **fnx's native lookup alone
(146.0 ns) already exceeds networkx's ENTIRE call (135.3 ns)** - the bead's original
observation, still true, just at 1.08x rather than the 1.9x it recorded. Closing the rest
needs the lookup itself, which is the key-length/rehash lever measured under br-r37-c1-ptiz2.
The two levers are complementary and both are now sized.

`G[u][v]` on DiGraph is the worst spelling at 471.2 ns - consistent with the
br-r37-c1-0k6zl note in digraph.rs that DiGraph "falls through to the PYTHON `AtlasView`,
whose per-subscript path ... re-canonicalises BOTH endpoints on every access".

### Worker-side Rust A/B is now possible, and build provenance MOVES the number

The extension loaded here is `lib_fnx.so` from the worker-scoped `CARGO_TARGET_DIR` - the
cdylib this invocation built - not the repo's prebuilt `_fnx.abi3.so`. Recipe, because rch
refuses shell-wrapped cargo (`RCH-E301: refusing shell-wrapped cargo command`): pin
`RCH_WORKER`, run `rch exec -- cargo build --release -j 2 -p fnx-python` FIRST, then
`rch exec -- cargo run --release -j 2 -p fnx-python --example <h2h>` second. The bootstrap
already prefers `$CARGO_TARGET_DIR/release/lib_fnx.so`, so it picks up the fresh build. This
is what makes a Rust change measurable here at all, and it satisfies the rule that BOTH arms
of an A/B must be builds you made yourself.

It also comes with a warning. Same harness, same worker, same CPU 15, str/DiGraph
`edges[u,v]`:

    installed _fnx.abi3.so (cd17e9fc, built elsewhere)   0.557x   fnx 264.1 ns
    fresh remote cdylib     (d8062460, built here)       0.494x   fnx 273.7 ns

An 11% ratio move from BUILD PROVENANCE ALONE - abi3 stable-ABI against a plain cdylib, plus
the known binary noise floor. Neither is "the" number, and cross-run comparisons in this family
must hold the build constant.

## Reproduce

    rch exec -- cargo run --release -j 2 -p fnx-python --example edge_subscript_h2h

Results print to STDERR. The `-j 2` is load-bearing: without an explicit `-j`, 10 of 14 workers
refuse the job with `insufficient_total_slots`.
