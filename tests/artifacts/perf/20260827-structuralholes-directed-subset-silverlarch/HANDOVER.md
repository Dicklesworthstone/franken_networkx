# Directed structuralholes with nodes=<iterable>: one fixed, one open (br-r37-c1-qbj9u)

SilverLarch, 2026-08-27. Instruction counts, because host_quiet_check refuses this host.

FILED HERE RATHER THAN AS A BEAD because the beads store is malformed
("database disk image is malformed ... duplicate import comment id 965") and refused both
`br create` and `br comments add` for the whole session. Git is the durable store, so this
handover lives here. Re-file it as a bead when the store is repaired.

## What already landed

effective_size(DiGraph, nodes=<iterable>) went from 0.964x to 1068x vs networkx in
86e61d1d3 - 2,449,654,720 to 2,210,959 Ir/call - by routing to the
effective_size_directed_rust kernel that was already in the extension but unused. See
tests/python/test_effective_size_directed_conformance_guard.py for the locks.

## What this file is about

Direct sibling of br-r37-c1-qbj9u, which I landed in 86e61d1d3. Same function family
(networkx structuralholes), same two-path split, same delegated branch, same magnitude -
but this one needs a NEW Rust kernel rather than a routing change, which is why it is
filed instead of fixed.

MEASURED, whole program with OpenBLAS/OMP/MKL pinned to 1, slope over IR_REPS 2->4,
200-node DiGraph, 50 requested nodes, both arms returning identical values:

    fnx  constraint(G, nodes=<iterable>)   2,593,397,011 Ir/call
    networkx                               2,500,640,665 Ir/call     0.964x

That 0.964x and the ~93M gap are the same signature effective_size had before the fix -
fnx runs networkx's own loop by delegating, and pays a graph conversion on top.

THE SPLIT IS REAL HERE TOO. networkx serves constraint two ways and they disagree on
directed graphs: `if nodes is None and has_scipy` takes a sparse-matrix path
(P + P.T, row-normalized), anything else takes the set-order summation over
local_constraint. Measured, they differ on 19 of 40 random digraphs - and CORRECTION, added
after the fix landed: that difference is NaN PLACEMENT, not values. A node with predecessors
but NO successors gets a number from the matrix path and NaN from the loop; a search over 200
random digraphs found no case where the two paths return different NUMBERS. That is narrower
than the sibling effective_size, whose two paths do return different numbers (2.0 against 1.8
on one 6-node graph), and this file originally implied the two cases were alike. So, exactly as for
effective_size, whichever kernel serves nodes!=None must reproduce the LOOP, and the
nodes=None branch must keep the matrix path (`_structural_holes_constraint_matrix`, which
br-r37-c1-qurfc already proved 0/320 exact).

WHY IT IS NOT THE SAME ONE-LINE FIX. effective_size had a purpose-built
effective_size_directed_rust sitting unused; constraint does not. `constraint_rust` is
UNDIRECTED-ONLY and does not reproduce nx's directed loop - 548 mismatches out of 807 node
values, and not near-misses (0.269 against 0.31, 0.415 against 0.4515). So this needs a
directed constraint kernel written to nx's directed semantics, mirroring what
effective_size_directed_rust already does.

THE RECIPE IS PROVEN, because I just used it on the sibling:
  * nx's directed semantics are mutual weight I(u->v)+I(v->u) over successors UNION
    predecessors, with normalized_mutual_weight dividing by the row sum (and by the row
    MAX for the second factor in redundancy; check local_constraint's own normalization
    rather than assuming it matches);
  * the isolated-node rule is `all(u == v for u in G[v])`, and G[v] on a DiGraph is
    SUCCESSORS ONLY - a node with predecessors but no successors is nan. Getting this
    wrong is exactly what made effective_size_directed_rust look broken and got it
    reverted for months; apply the rule in the PYTHON wrapper, where both existing native
    paths already do it, rather than in Rust;
  * validate the kernel against `nx.constraint(G, nodes=list(G))` - the LOOP - never
    against `nx.constraint(G)`, which is the matrix answer and differs;
  * then route only (directed AND unweighted AND no self-loops AND not multigraph AND
    nodes is not None) to it, leaving every other case exactly where it is.

SCOPE. Weighted, multigraph and self-loop directed graphs should stay on the matrix/parity
route. The UNDIRECTED unweighted nodes!=None case already reaches constraint_rust and is
not part of this.

THIRD SIBLING, unmeasured: local_constraint is also fnx-owned (not an nx re-export) and a
local_constraint_rust kernel exists. It was not measured here and may have the same shape;
check it before assuming.

INSTRUMENT NOTE. Pin OPENBLAS_NUM_THREADS / OMP_NUM_THREADS / MKL_NUM_THREADS to 1 for any
whole-program callgrind run here - networkx pulls scipy, whose OpenBLAS spin threads
otherwise contribute wall-time-dependent instruction counts large enough to swamp the
signal. And take the slope over two rep counts; the fixture build enters the same code.
