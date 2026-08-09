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

use fnx_classes::{AttrMap, Graph};
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
    // decomposition instead of reading it off the source. `add_node_with_attrs`
    // takes `impl Into<String>`: a `&str` argument allocates an owned key,
    // a `String` argument moves. Pre-building every key OUTSIDE the counted
    // window makes the difference between this arm and arm 2 the cost of that
    // one owned key and nothing else.
    let mut owned_keys: Vec<String> = (0..ROUNDS * CALLS).map(|_| "10".to_owned()).collect();
    let node_noop_owned_key = allocs_per_call(ROUNDS, CALLS, || {
        let key = owned_keys
            .pop()
            .expect("one pre-built key per counted call");
        graph.add_node_with_attrs(key, AttrMap::new());
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
    println!(
        "  -> owned key per endpoint (2-5)    : {:6.3} allocs/call",
        node_noop - node_noop_owned_key
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
        (edge_noop - caller_attrs - 4.0).abs() < f64::EPSILON,
        "add_edge entry allocated {:.3} per call excluding caller attrs, expected 4",
        edge_noop - caller_attrs
    );
    assert!(
        (node_noop - 3.0).abs() < f64::EPSILON,
        "add_node entry allocated {node_noop:.3} per call, expected 3"
    );
    assert!(
        (node_noop - node_noop_owned_key - 1.0).abs() < f64::EPSILON,
        "an owned node key must cost exactly one allocation, measured {:.3}",
        node_noop - node_noop_owned_key
    );
    assert!(
        read_control.abs() < f64::EPSILON,
        "has_node is a read and must allocate NOTHING per call: {read_control:.3}"
    );
}
