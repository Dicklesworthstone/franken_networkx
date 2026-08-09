//! br-r37-c1-jc9e4: an allocation census for the mutation entry path.
//!
//! WHY COUNTED WORK RATHER THAN TIME. jc9e4's standing question is what a
//! native `add_edge`/`add_node` that changes nothing spends its cost on. Seven
//! candidates were eliminated by timing, and the bead then stalled on the
//! instrument: `perf_event_paranoid` is 4 on this host so sampling is
//! unavailable, and a timer pair around a ~500 ns function is a large fraction
//! of what it measures. Allocation counts do not perturb the thing being
//! counted and do not move with host load, so this census is decidable at any
//! load — which is the property every timing arm on that bead lacked.
//!
//! WHY IT LIVES IN `tests/`. `crates/fnx-classes/src/lib.rs` carries
//! `#![forbid(unsafe_code)]`. An integration test is its own crate root and is
//! not bound by it, so the counting allocator can exist here without relaxing
//! the library's guarantee. The unsafe is confined to four `GlobalAlloc`
//! methods that only bump a counter and delegate to `System`.
//!
//! THE ARMS ARE STEADY-STATE ON PURPOSE. Every measured call operates on a
//! node or edge that already exists, so nothing is inserted and no map grows.
//! That isolates the per-CALL cost, which jc9e4 measured at roughly 90% of the
//! total (no-op `add_node` 538.2 ns against a 58.0 ns insert), and it makes the
//! count a constant instead of an amortised average over IndexMap growth.
//!
//! WHAT IT HAS ESTABLISHED, each step isolated by an arm that changes one
//! thing rather than by reading the source:
//!
//!   * the residue was 2 allocations per call, independent of endpoint count.
//!     Routing the ledger's counts through `count_evidence` removed one, which
//!     identified the removed one as the count's `to_string()` and the survivor
//!     as the record's evidence `Vec`;
//!   * arm 5 measured the owned endpoint key at 1 allocation. Probing the node
//!     map borrowed and owning only on the vacant path removed it, and arm 5
//!     now reads 0;
//!   * `add_edge` then dropped from 3 to 1 when its own preamble stopped
//!     owning both endpoint keys.
//!
//! Both mutators are now at exactly one allocation per steady-state call, and
//! it is the same one: the decision record's evidence `Vec`. Removing it needs
//! a change to `EvidenceLedger`'s shape, which was scoped and declined — see
//! the bead. Until then this census is a floor, and its job is to keep it one.

use fnx_classes::digraph::{DiGraph, MultiDiGraph};
use fnx_classes::{AttrMap, Graph, MultiGraph};
use fnx_runtime::CgseValue;
use std::alloc::{GlobalAlloc, Layout, System};
use std::sync::atomic::{AtomicUsize, Ordering};

static ALLOCS: AtomicUsize = AtomicUsize::new(0);

/// Counts allocations and delegates every operation to `System` unchanged.
///
/// SAFETY: each method forwards its arguments to the corresponding `System`
/// method without modification, so the allocator contract is exactly
/// `System`'s. The only added effect is a relaxed counter bump, which touches
/// no allocation state.
struct CountingAllocator;

unsafe impl GlobalAlloc for CountingAllocator {
    unsafe fn alloc(&self, layout: Layout) -> *mut u8 {
        ALLOCS.fetch_add(1, Ordering::Relaxed);
        unsafe { System.alloc(layout) }
    }

    unsafe fn dealloc(&self, ptr: *mut u8, layout: Layout) {
        unsafe { System.dealloc(ptr, layout) }
    }

    unsafe fn alloc_zeroed(&self, layout: Layout) -> *mut u8 {
        ALLOCS.fetch_add(1, Ordering::Relaxed);
        unsafe { System.alloc_zeroed(layout) }
    }

    unsafe fn realloc(&self, ptr: *mut u8, layout: Layout, new_size: usize) -> *mut u8 {
        ALLOCS.fetch_add(1, Ordering::Relaxed);
        unsafe { System.realloc(ptr, layout, new_size) }
    }
}

#[global_allocator]
static ALLOCATOR: CountingAllocator = CountingAllocator;

/// Allocations per call, taken as the MINIMUM over `rounds` passes of `calls`
/// each. The minimum is the right estimator here: the test harness and any
/// parked runtime thread can only ADD allocations to a window, never remove
/// them, so the floor is the arm's own cost.
fn allocs_per_call(rounds: usize, calls: usize, mut body: impl FnMut()) -> f64 {
    let mut best = usize::MAX;
    for _ in 0..rounds {
        let start = ALLOCS.load(Ordering::Relaxed);
        for _ in 0..calls {
            body();
        }
        let used = ALLOCS.load(Ordering::Relaxed) - start;
        best = best.min(used);
    }
    #[allow(clippy::cast_precision_loss)]
    {
        best as f64 / calls as f64
    }
}

/// br-r37-c1-jc9e4: a single-purpose target for an EXTERNAL profiler.
///
/// The census above bounds the allocation axis, and that axis is now exhausted:
/// both mutators sit at one allocation per steady-state call while `add_edge`
/// is still ~1245 ns and 0.46-0.50x vs nx, so the dominant cost is something
/// else. Attributing it needs instruction-level attribution, which
/// `perf_event_paranoid=4` blocks on this host — but callgrind counts
/// instructions by emulation, needs no privileges, and is immune to host load
/// for the same reason the census is.
///
/// Run it against the built test binary rather than through cargo:
/// ```text
/// cargo test -p fnx-classes --release --test mutation_allocation_census --no-run
/// valgrind --tool=callgrind --callgrind-out-file=cg.out \
///     <printed binary path> add_edge_profile_target --ignored --exact
/// callgrind_annotate cg.out
/// ```
/// Steady state on purpose: the edge and both endpoints already exist, so the
/// loop measures the per-CALL path and not graph growth. Note the binary
/// carries the counting allocator above, which adds one relaxed increment per
/// allocation — it shows up as its own entry rather than distorting others.
#[test]
#[ignore = "profiling target; run under callgrind, see the doc comment"]
fn add_edge_profile_target() {
    const CALLS: usize = 100_000;

    let mut graph = Graph::strict();
    for index in 0..1_000_usize {
        graph
            .add_edge_with_attrs(index.to_string(), (index + 1).to_string(), weight_attrs())
            .expect("path construction is allowed in strict mode");
    }
    for _ in 0..CALLS {
        graph
            .add_edge_with_attrs("10", "11", weight_attrs())
            .expect("re-adding an existing edge is allowed");
    }
    assert_eq!(graph.node_count(), 1_001);
}

/// br-r37-c1-jc9e4: the BUILD workload, which is the one this bead's headline
/// actually measures.
///
/// `add_edge_profile_target` above loops on an edge that already exists. That
/// isolates the per-call path, but it is NOT the workload behind the 1245
/// ns/edge and 0.46-0.50x figures — those were taken on a FRESH graph per timed
/// unit, so nearly every call creates an edge and autocreates endpoints. The
/// two run through different branches (autocreation, adjacency growth, an empty
/// attribute map to merge into) and there is no reason to assume one profile
/// describes the other, so this target exists to profile the headline path
/// directly rather than transfer conclusions across workloads.
///
/// Keys are pre-built OUTSIDE the timed region on purpose: the real caller is
/// the PyO3 boundary handing in already-canonicalised strings, so `to_string()`
/// in the loop would attribute the test harness's work to `add_edge`.
///
/// Same invocation as the sibling, with `add_edge_build_profile_target`.
#[test]
#[ignore = "profiling target; run under callgrind, see the doc comment"]
fn add_edge_build_profile_target() {
    const EDGES: usize = 100_000;

    let keys: Vec<String> = (0..=EDGES).map(|index| index.to_string()).collect();
    let mut graph = Graph::strict();
    for index in 0..EDGES {
        graph
            .add_edge_with_attrs(&keys[index], &keys[index + 1], weight_attrs())
            .expect("path construction is allowed in strict mode");
    }
    assert_eq!(graph.node_count(), EDGES + 1);
}

fn weight_attrs() -> AttrMap {
    let mut attrs = AttrMap::new();
    attrs.insert("weight".to_owned(), CgseValue::Int(1));
    attrs
}

#[test]
fn mutation_entry_allocation_census() {
    const ROUNDS: usize = 9;
    const CALLS: usize = 2_000;

    let mut graph = Graph::strict();
    for index in 0..1_000_usize {
        graph
            .add_edge_with_attrs(index.to_string(), (index + 1).to_string(), weight_attrs())
            .expect("path construction is allowed in strict mode");
    }

    // Arm 1 — add_edge on an edge that already exists, with the attrs it
    // already carries. Nothing is inserted; this is the per-CALL cost.
    let edge_noop = allocs_per_call(ROUNDS, CALLS, || {
        graph
            .add_edge_with_attrs("10", "11", weight_attrs())
            .expect("re-adding an existing edge is allowed");
    });

    // Arm 2 — add_node on a node that already exists, no attrs. Same shape on
    // the node side.
    let node_noop = allocs_per_call(ROUNDS, CALLS, || {
        graph.add_node_with_attrs("10", AttrMap::new());
    });

    // Arm 3 — the read control. has_node shares key handling with both
    // mutators but reaches neither the ledger nor the stores, so it separates
    // "what a lookup costs" from "what the mutation entry costs".
    let read_control = allocs_per_call(ROUNDS, CALLS, || {
        assert!(graph.has_node("10"));
    });

    // Arm 4 — the attrs the caller hands in. Both mutator arms build one
    // AttrMap per call, so this is charged to them and is NOT part of what the
    // mutation entry itself spends.
    let caller_attrs = allocs_per_call(ROUNDS, CALLS, || {
        let attrs = weight_attrs();
        assert_eq!(attrs.len(), 1);
    });

    // Arm 5 — the key discriminator, and the reason this file measures the
    // decomposition instead of reading it off the source. Pre-building every
    // key OUTSIDE the counted window makes the difference between this arm and
    // arm 2 the cost of owning the key and nothing else.
    //
    // It read 1.000 when this census was written, which is what identified the
    // owned key as a real per-endpoint cost. It reads 0.000 now that
    // `add_node_with_attrs_unrecorded` probes borrowed and owns only on the
    // vacant path: handing it a `&str` and handing it a ready-made `String`
    // cost the same, because neither allocates. The arm is kept precisely
    // because a nonzero reading would mean that regressed.
    let mut owned_keys: Vec<String> = (0..ROUNDS * CALLS).map(|_| "10".to_owned()).collect();
    let node_noop_owned_key = allocs_per_call(ROUNDS, CALLS, || {
        let key = owned_keys
            .pop()
            .expect("one pre-built key per counted call");
        graph.add_node_with_attrs(key, AttrMap::new());
    });

    // Arms 6/7 — the DIRECTED siblings of arms 1 and 2. The undirected pair
    // above was brought to one allocation per call; a directed graph reaches
    // the same user-visible operation through its own code, so it needs its own
    // arm rather than an assumption that the lever transferred.
    let mut digraph = DiGraph::strict();
    for index in 0..1_000_usize {
        digraph
            .add_edge_with_attrs(index.to_string(), (index + 1).to_string(), weight_attrs())
            .expect("path construction is allowed in strict mode");
    }
    let di_edge_noop = allocs_per_call(ROUNDS, CALLS, || {
        digraph
            .add_edge_with_attrs("10", "11", weight_attrs())
            .expect("re-adding an existing edge is allowed");
    });
    let di_node_noop = allocs_per_call(ROUNDS, CALLS, || {
        digraph.add_node_with_attrs("10", AttrMap::new());
    });

    // Arms 8/9 — the MULTI siblings. A multigraph reaches the same user-visible
    // operation through `add_edge_impl`, so like the directed pair it gets its
    // own arm instead of an assumption that the lever transferred. Re-adding
    // an existing pair appends a parallel edge, so these arms are NOT no-ops
    // the way arms 1/6 are; they are still steady-state in the sense that no
    // node is created and the maps do not rehash per call.
    let mut multigraph = MultiGraph::strict();
    let mut multidigraph = MultiDiGraph::strict();
    for index in 0..1_000_usize {
        multigraph
            .add_edge_with_attrs(index.to_string(), (index + 1).to_string(), weight_attrs())
            .expect("path construction is allowed in strict mode");
        multidigraph
            .add_edge_with_attrs(index.to_string(), (index + 1).to_string(), weight_attrs())
            .expect("path construction is allowed in strict mode");
    }
    let mg_node_noop = allocs_per_call(ROUNDS, CALLS, || {
        multigraph.add_node_with_attrs("10", AttrMap::new());
    });
    let mdg_node_noop = allocs_per_call(ROUNDS, CALLS, || {
        multidigraph.add_node_with_attrs("10", AttrMap::new());
    });

    println!("mutation_entry_allocation_census rounds={ROUNDS} calls={CALLS}");
    println!("  add_edge_with_attrs, existing edge : {edge_noop:6.3} allocs/call");
    println!("  add_node_with_attrs, existing node : {node_noop:6.3} allocs/call");
    println!("  has_node (read control)            : {read_control:6.3} allocs/call");
    println!("  caller-built AttrMap (charged in)  : {caller_attrs:6.3} allocs/call");
    println!("  add_node_with_attrs, pre-owned key : {node_noop_owned_key:6.3} allocs/call");
    println!(
        "  -> add_edge entry, caller attrs out: {:6.3} allocs/call",
        edge_noop - caller_attrs
    );
    println!("  DiGraph add_edge, existing edge    : {di_edge_noop:6.3} allocs/call");
    println!("  DiGraph add_node, existing node    : {di_node_noop:6.3} allocs/call");
    println!("  MultiGraph add_node, existing      : {mg_node_noop:6.3} allocs/call");
    println!("  MultiDiGraph add_node, existing    : {mdg_node_noop:6.3} allocs/call");
    println!(
        "  -> owning the key costs (2-5)      : {:6.3} allocs/call",
        node_noop - node_noop_owned_key
    );
    println!(
        "  -> DiGraph add_edge entry          : {:6.3} allocs/call",
        di_edge_noop - caller_attrs
    );

    // EXACT LOCKS, not ceilings. Every arm above is a whole number in both
    // debug and release because these are structural allocations — one Vec,
    // one String — not allocator bookkeeping. An exact lock therefore fails on
    // any allocation ADDED to the mutation entry, which a ceiling would let
    // through, and it is what makes br-r37-c1-g2nev's borrowed constants
    // durable: before that change a single add_edge record materialised 14
    // owned Strings, so restoring `.to_owned()` on any constant evidence field
    // fails here even though the recorded VALUE would be unchanged and every
    // parity assertion would still pass.
    assert!(
        (edge_noop - caller_attrs - 1.0).abs() < f64::EPSILON,
        "add_edge entry allocated {:.3} per call excluding caller attrs, expected 1 \
         (the record's evidence Vec; neither endpoint key is owned)",
        edge_noop - caller_attrs
    );
    assert!(
        (node_noop - 1.0).abs() < f64::EPSILON,
        "add_node entry allocated {node_noop:.3} per call, expected 1 \
         (the record's evidence Vec; the occupied path owns no key)"
    );
    assert!(
        (node_noop - node_noop_owned_key).abs() < f64::EPSILON,
        "add_node on an EXISTING node must not own its key, so a &str caller \
         and a ready-made String caller must cost the same; the gap was {:.3}",
        node_noop - node_noop_owned_key
    );
    assert!(
        read_control.abs() < f64::EPSILON,
        "has_node is a read and must allocate NOTHING per call: {read_control:.3}"
    );

    // The directed pair must not drift back. It sat at the undirected pair's
    // pre-lever numbers (entry 3, node 2) until the same levers were applied
    // here, which is why these arms exist rather than an assumption that a fix
    // to `Graph` reaches `DiGraph`.
    assert!(
        (di_edge_noop - caller_attrs - 1.0).abs() < f64::EPSILON,
        "DiGraph add_edge entry allocated {:.3} per call excluding caller attrs, expected 1",
        di_edge_noop - caller_attrs
    );
    assert!(
        (di_node_noop - 1.0).abs() < f64::EPSILON,
        "DiGraph add_node entry allocated {di_node_noop:.3} per call, expected 1"
    );

    // All four graph types reach the same floor on the node side. MultiDiGraph
    // read 4.000 before its levers — it materialised the key three times, once
    // for `nodes` and once each for the `successors` / `predecessors` rows —
    // and this is what keeps any of them from drifting back independently.
    assert!(
        (mg_node_noop - 1.0).abs() < f64::EPSILON,
        "MultiGraph add_node entry allocated {mg_node_noop:.3} per call, expected 1"
    );
    assert!(
        (mdg_node_noop - 1.0).abs() < f64::EPSILON,
        "MultiDiGraph add_node entry allocated {mdg_node_noop:.3} per call, expected 1"
    );
}
