//! br-r37-c1-8foqi: PyO3 binding for the native safe-Rust integer primal
//! network-simplex kernel.
//!
//! The pivot logic itself now lives in `fnx-algorithms`
//! (`fnx_algorithms::network_simplex_int`), hoisted there so sibling Rust
//! consumers (e.g. MTDT) can use the exact-integer min-cost-flow path directly,
//! without depending on this PyO3 crate. This module is now only the Python
//! interop shim: it maps the caller's `+inf` capacity sentinel onto the kernel's
//! `i64::MAX`, invokes the shared kernel, and flattens the result into the
//! `(status_code, cost, flows)` tuple the Python `network_simplex` port expects.
//! There is no duplicated algorithm here — this is a single source of truth.

use fnx_algorithms::network_simplex_int::{NetworkSimplexStatus, network_simplex_int as ns_int};
use pyo3::prelude::*;

/// PyO3 binding: takes flat integer arrays, returns (status, cost, flows).
/// status: 0 = optimal, 1 = infeasible, 2 = unbounded.
/// `cap` uses the sentinel `cap_inf` for +infinity (caller passes a value it
/// guarantees no finite capacity reaches).
#[pyfunction]
#[pyo3(signature = (node_demands, src, tgt, cap, wt, cap_inf))]
pub fn network_simplex_int(
    node_demands: Vec<i64>,
    src: Vec<usize>,
    tgt: Vec<usize>,
    cap: Vec<i64>,
    wt: Vec<i64>,
    cap_inf: i64,
) -> (i32, i64, Vec<i64>) {
    // Map the caller's +inf sentinel to i64::MAX used internally by the kernel.
    let cap2: Vec<i64> = cap
        .iter()
        .map(|&c| if c >= cap_inf { i64::MAX } else { c })
        .collect();
    let sol = ns_int(&node_demands, &src, &tgt, &cap2, &wt);
    let code = match sol.status {
        NetworkSimplexStatus::Optimal => 0,
        NetworkSimplexStatus::Infeasible => 1,
        NetworkSimplexStatus::Unbounded => 2,
    };
    (code, sol.cost, sol.flows)
}
