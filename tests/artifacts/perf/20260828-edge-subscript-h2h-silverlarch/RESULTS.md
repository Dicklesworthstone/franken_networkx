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

## Reproduce

    rch exec -- cargo run --release -j 2 -p fnx-python --example edge_subscript_h2h

Results print to STDERR. The `-j 2` is load-bearing: without an explicit `-j`, 10 of 14 workers
refuse the job with `insufficient_total_slots`.
