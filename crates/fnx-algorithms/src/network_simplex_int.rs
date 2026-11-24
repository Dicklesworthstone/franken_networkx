//! Exact-integer primal network-simplex kernel (first-class Rust API).
//!
//! A faithful transcription of NetworkX's `network_simplex`
//! (`networkx/algorithms/flow/networksimplex.py`, BSD-licensed) pivot logic,
//! specialised to integer demands/capacities/weights — the common, and the
//! only byte-exact-integer, case. Flow and cost arithmetic uses checked bounds
//! and widened `i128` intermediates; results retain the `i64` public contract.
//! A problem that exceeds that contract returns an explicit overflow status,
//! never a wrapped cost, a debug-build panic, or overflow-induced unboundedness.
//!
//! This kernel was hoisted out of the PyO3 binding crate (`fnx-python`) so that
//! sibling Rust consumers (e.g. MTDT's integer voice-leading optimal transport)
//! can use the exact-integer min-cost-flow path directly, without taking a
//! dependency on `fnx-python`/PyO3. `fnx-python` now calls this same code, so
//! there is a single source of truth for the pivot logic and both the Rust API
//! and the Python binding produce identical numeric results.
//!
//! Determinism: the entering-edge search (block search / Dantzig + Bland),
//! the leaving-edge tie-break (first minimiser in reversed cycle order,
//! matching Python's `min`), and every array update below are deterministic
//! functions of the input arrays in the order they are supplied. Given the same
//! `(node_demands, src, tgt, cap, wt)` the solver always returns the same
//! `(status, cost, flows)` — see the `determinism` unit test.
//!
//! Convention (identical to NetworkX): a node's `demand` is positive when the
//! node is a *sink* (consumes flow) and negative when it is a *source*
//! (supplies flow); the demands must sum to zero for a feasible problem.
//!
//! NetworkX uses a dummy root node and encodes "no parent" / the root via
//! Python's negative-index alias `-1` (which addresses the dummy root stored at
//! index `n`). Here the root is the explicit index `n`, and a true `None`
//! parent is `NONE = usize::MAX`.

#![allow(clippy::needless_range_loop)]

const NONE: usize = usize::MAX;

/// Sentinel used inside [`network_simplex_int`] to mean "unbounded / +infinity"
/// capacity. Exactly [`i64::MAX`] is reserved for this sentinel; the largest
/// finite capacity is [`i64::MAX`] - 1.
pub const CAP_INF: i64 = i64::MAX;

/// Result status of an exact-integer network-simplex solve.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum NetworkSimplexStatus {
    /// A minimum-cost flow satisfying all demands was found.
    Optimal,
    /// No flow satisfies all node demands (e.g. demands do not sum to zero, or
    /// insufficient capacity connects sources to sinks).
    Infeasible,
    /// The problem is unbounded below (a negative-cost cycle of infinite
    /// capacity exists).
    Unbounded,
    /// The edge arrays have different lengths, an endpoint is out of range,
    /// or a self-loop/zero-capacity edge was not removed by extraction.
    InvalidInput,
    /// The internal arithmetic bound, exact total cost, or an individual edge
    /// flow cannot be represented by the solver's integer types.
    Overflow,
}

/// Outcome of [`network_simplex_int`].
///
/// On [`NetworkSimplexStatus::Optimal`], `cost` is the exact minimum total cost
/// and `flows[i]` is the (integer) flow assigned to input edge `i` (the edges
/// in the same order they were supplied to [`network_simplex_int`]). On the
/// non-optimal statuses, `cost` is `0` and `flows` is empty.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct NetworkSimplexIntSolution {
    /// Solve status.
    pub status: NetworkSimplexStatus,
    /// Exact total cost of the flow (0 when not optimal).
    pub cost: i64,
    /// Flow on each input edge, in input order (empty when not optimal).
    pub flows: Vec<i64>,
}

/// Benchmark-only selector for the frozen allocating cycle builder and the
/// solve-local scratch implementation.
#[cfg(any(test, feature = "bench-internals"))]
#[doc(hidden)]
#[derive(Clone, Copy, Debug)]
pub enum NetworkSimplexCycleArm {
    /// Preserve the pre-scratch behavior: allocate four path vectors per pivot.
    Allocating,
    /// Clear and refill four solve-local path buffers across pivots.
    ReusedScratch,
}

#[cfg(test)]
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
struct CycleTrace {
    pivots: usize,
    path_calls: usize,
    path_hops: usize,
}

#[cfg(test)]
thread_local! {
    static CYCLE_TRACE: std::cell::Cell<CycleTrace> =
        const { std::cell::Cell::new(CycleTrace { pivots: 0, path_calls: 0, path_hops: 0 }) };
}

#[cfg(test)]
fn record_path_trace(hops: usize) {
    CYCLE_TRACE.with(|trace| {
        let mut current = trace.get();
        current.path_calls += 1;
        current.path_hops += hops;
        trace.set(current);
    });
}

struct Simplex {
    // length edge_count + n (artificial edges appended)
    edge_sources: Vec<usize>,
    edge_targets: Vec<usize>,
    edge_capacities: Vec<i128>,
    edge_weights: Vec<i128>,
    edge_flow: Vec<i128>,
    // length n
    node_potentials: Vec<i128>,
    // length n + 1 (index n == root)
    parent: Vec<usize>,
    parent_edge: Vec<usize>,
    subtree_size: Vec<usize>,
    next_node_dft: Vec<usize>,
    prev_node_dft: Vec<usize>,
    last_descendent_dft: Vec<usize>,
}

#[derive(Default)]
struct CycleScratch {
    nodes: Vec<usize>,
    edges: Vec<usize>,
    right_nodes: Vec<usize>,
    right_edges: Vec<usize>,
}

impl Simplex {
    #[inline]
    fn reduced_cost(&self, i: usize) -> i128 {
        let c = self.edge_weights[i] - self.node_potentials[self.edge_sources[i]]
            + self.node_potentials[self.edge_targets[i]];
        if self.edge_flow[i] == 0 { c } else { -c }
    }

    #[inline]
    fn residual_capacity(&self, i: usize, p: usize) -> i128 {
        if self.edge_sources[i] == p {
            self.edge_capacities[i] - self.edge_flow[i]
        } else {
            self.edge_flow[i]
        }
    }

    fn find_apex(&self, mut p: usize, mut q: usize) -> usize {
        let mut size_p = self.subtree_size[p];
        let mut size_q = self.subtree_size[q];
        loop {
            while size_p < size_q {
                p = self.parent[p];
                size_p = self.subtree_size[p];
            }
            while size_p > size_q {
                q = self.parent[q];
                size_q = self.subtree_size[q];
            }
            if size_p == size_q {
                if p != q {
                    p = self.parent[p];
                    size_p = self.subtree_size[p];
                    q = self.parent[q];
                    size_q = self.subtree_size[q];
                } else {
                    return p;
                }
            }
        }
    }

    /// Frozen allocating baseline for the cycle-scratch A/B test.
    #[cfg(any(test, feature = "bench-internals"))]
    fn trace_path(&self, mut p: usize, w: usize) -> (Vec<usize>, Vec<usize>) {
        let mut wn = vec![p];
        let mut we = Vec::new();
        while p != w {
            we.push(self.parent_edge[p]);
            p = self.parent[p];
            wn.push(p);
        }
        #[cfg(test)]
        record_path_trace(we.len());
        (wn, we)
    }

    /// Frozen allocating baseline for the cycle-scratch A/B test.
    #[cfg(any(test, feature = "bench-internals"))]
    fn find_cycle(&self, i: usize, p: usize, q: usize) -> (Vec<usize>, Vec<usize>) {
        let w = self.find_apex(p, q);
        let (mut wn, mut we) = self.trace_path(p, w);
        wn.reverse();
        we.reverse();
        if we.len() != 1 || we[0] != i {
            we.push(i);
        }
        let (mut wnr, wer) = self.trace_path(q, w);
        wnr.pop(); // del WnR[-1]
        wn.extend(wnr);
        we.extend(wer);
        (wn, we)
    }

    fn trace_path_into(
        &self,
        mut p: usize,
        w: usize,
        nodes: &mut Vec<usize>,
        edges: &mut Vec<usize>,
    ) {
        nodes.clear();
        edges.clear();
        nodes.push(p);
        while p != w {
            edges.push(self.parent_edge[p]);
            p = self.parent[p];
            nodes.push(p);
        }
        #[cfg(test)]
        record_path_trace(edges.len());
    }

    /// Fills solve-local scratch with the fundamental cycle created by adding
    /// edge `i == (p, q)`, oriented from `p` to `q`.
    fn find_cycle_into(&self, i: usize, p: usize, q: usize, scratch: &mut CycleScratch) {
        let w = self.find_apex(p, q);
        self.trace_path_into(p, w, &mut scratch.nodes, &mut scratch.edges);
        scratch.nodes.reverse();
        scratch.edges.reverse();
        if scratch.edges.len() != 1 || scratch.edges[0] != i {
            scratch.edges.push(i);
        }
        self.trace_path_into(q, w, &mut scratch.right_nodes, &mut scratch.right_edges);
        scratch.right_nodes.pop(); // del WnR[-1]
        scratch.nodes.extend_from_slice(&scratch.right_nodes);
        scratch.edges.extend_from_slice(&scratch.right_edges);
    }

    fn augment_flow(&mut self, wn: &[usize], we: &[usize], f: i128) {
        for (idx, &i) in we.iter().enumerate() {
            let p = wn[idx];
            if self.edge_sources[i] == p {
                self.edge_flow[i] += f;
            } else {
                self.edge_flow[i] -= f;
            }
        }
    }

    /// Returns (j, s, t): the leaving edge in the cycle (Wn, We).
    /// nx: `min(zip(reversed(We), reversed(Wn)), key=residual_capacity)` — the
    /// FIRST minimiser in reversed order (Python min keeps the first on ties).
    fn find_leaving_edge(&self, wn: &[usize], we: &[usize]) -> (usize, usize, usize) {
        let mut best_j = we[we.len() - 1];
        let mut best_s = wn[wn.len() - 1];
        let mut best_rc = self.residual_capacity(best_j, best_s);
        // iterate reversed; keep first minimiser (strictly-less replaces)
        for k in (0..we.len()).rev() {
            let j = we[k];
            let s = wn[k];
            let rc = self.residual_capacity(j, s);
            if rc < best_rc {
                best_rc = rc;
                best_j = j;
                best_s = s;
            }
        }
        let t = if self.edge_sources[best_j] == best_s {
            self.edge_targets[best_j]
        } else {
            self.edge_sources[best_j]
        };
        (best_j, best_s, t)
    }

    #[inline]
    fn process_cycle(&mut self, i: usize, mut p: usize, mut q: usize, wn: &[usize], we: &[usize]) {
        let (j, mut s, mut t) = self.find_leaving_edge(wn, we);
        let rc = self.residual_capacity(j, s);
        self.augment_flow(wn, we, rc);
        if i != j {
            if self.parent[t] != s {
                std::mem::swap(&mut s, &mut t);
            }
            // We.index(i) > We.index(j): first occurrence positions
            let pos_i = we
                .iter()
                .position(|&edge| edge == i)
                .expect("fundamental cycle must contain its entering edge");
            let pos_j = we
                .iter()
                .position(|&edge| edge == j)
                .expect("fundamental cycle must contain its leaving edge");
            if pos_i > pos_j {
                std::mem::swap(&mut p, &mut q);
            }
            self.remove_edge(s, t);
            self.make_root(q);
            self.add_edge(i, p, q);
            self.update_potentials(i, p, q);
        }
    }

    fn remove_edge(&mut self, s: usize, t: usize) {
        let size_t = self.subtree_size[t];
        let prev_t = self.prev_node_dft[t];
        let last_t = self.last_descendent_dft[t];
        let next_last_t = self.next_node_dft[last_t];
        self.parent[t] = NONE;
        self.parent_edge[t] = NONE;
        self.next_node_dft[prev_t] = next_last_t;
        self.prev_node_dft[next_last_t] = prev_t;
        self.next_node_dft[last_t] = t;
        self.prev_node_dft[t] = last_t;
        let mut s = s;
        while s != NONE {
            self.subtree_size[s] -= size_t;
            if self.last_descendent_dft[s] == last_t {
                self.last_descendent_dft[s] = prev_t;
            }
            s = self.parent[s];
        }
    }

    fn make_root(&mut self, q: usize) {
        let mut ancestors = Vec::new();
        let mut cur = q;
        while cur != NONE {
            ancestors.push(cur);
            cur = self.parent[cur];
        }
        ancestors.reverse();
        for w in 0..ancestors.len().saturating_sub(1) {
            let p = ancestors[w];
            let q = ancestors[w + 1];
            let size_p = self.subtree_size[p];
            let mut last_p = self.last_descendent_dft[p];
            let prev_q = self.prev_node_dft[q];
            let last_q = self.last_descendent_dft[q];
            let next_last_q = self.next_node_dft[last_q];
            self.parent[p] = q;
            self.parent[q] = NONE;
            self.parent_edge[p] = self.parent_edge[q];
            self.parent_edge[q] = NONE;
            self.subtree_size[p] = size_p - self.subtree_size[q];
            self.subtree_size[q] = size_p;
            self.next_node_dft[prev_q] = next_last_q;
            self.prev_node_dft[next_last_q] = prev_q;
            self.next_node_dft[last_q] = q;
            self.prev_node_dft[q] = last_q;
            if last_p == last_q {
                self.last_descendent_dft[p] = prev_q;
                last_p = prev_q;
            }
            self.prev_node_dft[p] = last_q;
            self.next_node_dft[last_q] = p;
            self.next_node_dft[last_p] = q;
            self.prev_node_dft[q] = last_p;
            self.last_descendent_dft[q] = last_p;
        }
    }

    fn add_edge(&mut self, i: usize, p: usize, q: usize) {
        let last_p = self.last_descendent_dft[p];
        let next_last_p = self.next_node_dft[last_p];
        let size_q = self.subtree_size[q];
        let last_q = self.last_descendent_dft[q];
        self.parent[q] = p;
        self.parent_edge[q] = i;
        self.next_node_dft[last_p] = q;
        self.prev_node_dft[q] = last_p;
        self.prev_node_dft[next_last_p] = last_q;
        self.next_node_dft[last_q] = next_last_p;
        let mut p = p;
        while p != NONE {
            self.subtree_size[p] += size_q;
            if self.last_descendent_dft[p] == last_p {
                self.last_descendent_dft[p] = last_q;
            }
            p = self.parent[p];
        }
    }

    fn update_potentials(&mut self, i: usize, p: usize, q: usize) {
        let d = if q == self.edge_targets[i] {
            self.node_potentials[p] - self.edge_weights[i] - self.node_potentials[q]
        } else {
            self.node_potentials[p] + self.edge_weights[i] - self.node_potentials[q]
        };
        // trace_subtree(q): q, then follow next_node_dft until last_descendent.
        let l = self.last_descendent_dft[q];
        let mut cur = q;
        loop {
            self.node_potentials[cur] += d;
            if cur == l {
                break;
            }
            cur = self.next_node_dft[cur];
        }
    }
}

/// Core solve: `cap` uses `i64::MAX` for +infinity. `node_demands` has length n;
/// the edge arrays have length edge_count (the real, non-self-loop, non-zero-cap
/// edges already filtered by the caller). Returns the flow on each real edge.
fn solve_impl<const REUSE_CYCLE_SCRATCH: bool>(
    node_demands: &[i64],
    src: &[usize],
    tgt: &[usize],
    cap: &[i64], // i64::MAX represents +inf
    wt: &[i64],
) -> (NetworkSimplexStatus, i64, Vec<i64>) {
    let n = node_demands.len();
    let edge_count = src.len();

    // This is a public Rust entry point as well as an internal Python kernel.
    // Do not assume that a caller ran the Python extraction/admission checks.
    if tgt.len() != edge_count
        || cap.len() != edge_count
        || wt.len() != edge_count
        || src
            .iter()
            .zip(tgt)
            .any(|(&u, &v)| u >= n || v >= n || u == v)
    {
        return (NetworkSimplexStatus::InvalidInput, 0, Vec::new());
    }
    if cap.iter().any(|&c| c < 0) {
        return (NetworkSimplexStatus::Infeasible, 0, Vec::new());
    }
    if cap.contains(&0) {
        return (NetworkSimplexStatus::InvalidInput, 0, Vec::new());
    }
    let Some(demand_sum) = node_demands
        .iter()
        .try_fold(0i128, |sum, &d| sum.checked_add(i128::from(d)))
    else {
        return (NetworkSimplexStatus::Overflow, 0, Vec::new());
    };
    if demand_sum != 0 {
        return (NetworkSimplexStatus::Infeasible, 0, Vec::new());
    }
    if n == 0 {
        return (NetworkSimplexStatus::Optimal, 0, Vec::new());
    }

    let Some(faux_inf) = artificial_capacity(node_demands, cap, wt) else {
        return (NetworkSimplexStatus::Overflow, 0, Vec::new());
    };

    // Build full edge arrays: real edges, then n artificial root edges.
    let Some(total) = edge_count.checked_add(n) else {
        return (NetworkSimplexStatus::Overflow, 0, Vec::new());
    };
    if total > isize::MAX as usize / std::mem::size_of::<i128>() {
        return (NetworkSimplexStatus::Overflow, 0, Vec::new());
    }
    let mut edge_sources = Vec::with_capacity(total);
    let mut edge_targets = Vec::with_capacity(total);
    let mut edge_capacities = Vec::with_capacity(total);
    let mut edge_weights = Vec::with_capacity(total);
    edge_sources.extend_from_slice(src);
    edge_targets.extend_from_slice(tgt);
    // Bound an infinite edge by the same exact artificial capacity. It exceeds
    // every finite capacity and the total supply plus finite cycle capacity,
    // and reaches the reference unboundedness threshold before it can constrain
    // an accepted flow. No ordinary i64 number acts as infinity internally.
    edge_capacities.extend(cap.iter().map(|&c| {
        if c == CAP_INF {
            faux_inf
        } else {
            i128::from(c)
        }
    }));
    edge_weights.extend(wt.iter().map(|&w| i128::from(w)));
    // artificial edges connect node i to the root (index n)
    for (i, &d) in node_demands.iter().enumerate() {
        if d > 0 {
            edge_sources.push(n); // root
            edge_targets.push(i);
        } else {
            edge_sources.push(i);
            edge_targets.push(n); // root
        }
    }
    edge_weights.extend(std::iter::repeat_n(faux_inf, n));
    edge_capacities.extend(std::iter::repeat_n(faux_inf, n));

    // initialize_spanning_tree(n, faux_inf)
    let mut edge_flow = vec![0i128; edge_count];
    edge_flow.extend(node_demands.iter().map(|&d| i128::from(d).abs()));
    let node_potentials: Vec<i128> = node_demands
        .iter()
        .map(|&d| if d <= 0 { faux_inf } else { -faux_inf })
        .collect();
    // parent: nodes 0..n-1 -> root (n); root -> NONE
    let mut parent = vec![n; n + 1];
    parent[n] = NONE;
    // parent_edge: node i -> artificial edge ec+i; root -> NONE
    let mut parent_edge: Vec<usize> = (edge_count..edge_count + n).collect();
    parent_edge.push(NONE); // index n (root)
    // subtree_size: [1]*n + [n+1]
    let mut subtree_size = vec![1usize; n + 1];
    subtree_size[n] = n + 1;
    // next_node_dft: [1,2,...,n-1, n(root), 0]
    let mut next_node_dft = vec![0usize; n + 1];
    for i in 0..n.saturating_sub(1) {
        next_node_dft[i] = i + 1;
    }
    if n >= 1 {
        next_node_dft[n - 1] = n; // was -1 -> root
        next_node_dft[n] = 0;
    }
    // prev_node_dft: [n(root), 0, 1, ..., n-1]
    let mut prev_node_dft = vec![0usize; n + 1];
    prev_node_dft[0] = n; // was -1 -> root
    for i in 1..=n {
        prev_node_dft[i] = i - 1;
    }
    // last_descendent_dft: [0,1,...,n-1, n-1]
    let mut last_descendent_dft = vec![0usize; n + 1];
    for i in 0..n {
        last_descendent_dft[i] = i;
    }
    last_descendent_dft[n] = n - 1;

    let mut sx = Simplex {
        edge_sources,
        edge_targets,
        edge_capacities,
        edge_weights,
        edge_flow,
        node_potentials,
        parent,
        parent_edge,
        subtree_size,
        next_node_dft,
        prev_node_dft,
        last_descendent_dft,
    };

    // Pivot loop with the block-search (Dantzig + Bland) entering-edge finder.
    if edge_count > 0 {
        let b = {
            // B = ceil(sqrt(edge_count))
            let s = (edge_count as f64).sqrt().ceil() as usize;
            s.max(1)
        };
        let big_m = edge_count.div_ceil(b);
        let mut m = 0usize; // consecutive blocks without an eligible edge
        let mut f = 0usize; // first edge in block
        let mut cycle_scratch = CycleScratch::default();
        while m < big_m {
            // next block [f, l) cyclically over 0..edge_count
            let l = f + b;
            // find first edge with the lowest reduced cost in the block
            let mut best_i = usize::MAX;
            let mut best_c = 0i128;
            if l <= edge_count {
                for e in f..l {
                    let c = sx.reduced_cost(e);
                    if best_i == usize::MAX || c < best_c {
                        best_c = c;
                        best_i = e;
                    }
                }
                f = l;
            } else {
                let l2 = l - edge_count;
                for e in f..edge_count {
                    let c = sx.reduced_cost(e);
                    if best_i == usize::MAX || c < best_c {
                        best_c = c;
                        best_i = e;
                    }
                }
                for e in 0..l2 {
                    let c = sx.reduced_cost(e);
                    if best_i == usize::MAX || c < best_c {
                        best_c = c;
                        best_i = e;
                    }
                }
                f = l2;
            }
            let i = best_i;
            let c = sx.reduced_cost(i);
            if c >= 0 {
                m += 1;
                continue;
            }
            // entering edge found
            let (p, q) = if sx.edge_flow[i] == 0 {
                (sx.edge_sources[i], sx.edge_targets[i])
            } else {
                (sx.edge_targets[i], sx.edge_sources[i])
            };
            m = 0;
            // process this entering edge (the loop body of the Python for-loop)
            #[cfg(test)]
            CYCLE_TRACE.with(|trace| {
                let mut current = trace.get();
                current.pivots += 1;
                trace.set(current);
            });
            if REUSE_CYCLE_SCRATCH {
                sx.find_cycle_into(i, p, q, &mut cycle_scratch);
                sx.process_cycle(i, p, q, &cycle_scratch.nodes, &cycle_scratch.edges);
            } else {
                #[cfg(any(test, feature = "bench-internals"))]
                {
                    let (wn, we) = sx.find_cycle(i, p, q);
                    sx.process_cycle(i, p, q, &wn, &we);
                }
                #[cfg(not(any(test, feature = "bench-internals")))]
                unreachable!("allocating cycle baseline is benchmark-only");
            }
        }
    }

    // Infeasibility: any artificial edge (indices edge_count..edge_count+n) has
    // nonzero flow.
    for i in edge_count..edge_count + n {
        if sx.edge_flow[i] != 0 {
            return (NetworkSimplexStatus::Infeasible, 0, Vec::new());
        }
    }
    // Preserve NetworkX's observable unboundedness threshold. This check is
    // deliberately separate from arithmetic overflow: all flows are <= F and
    // the admitted arithmetic envelope proves that doubling fits i128.
    for i in 0..edge_count {
        if sx.edge_flow[i] * 2 >= faux_inf {
            return (NetworkSimplexStatus::Unbounded, 0, Vec::new());
        }
    }

    let Ok(flows): Result<Vec<i64>, _> = sx.edge_flow[..edge_count]
        .iter()
        .map(|&flow| i64::try_from(flow))
        .collect()
    else {
        return (NetworkSimplexStatus::Overflow, 0, Vec::new());
    };
    let Some(cost) = exact_cost(wt, &flows) else {
        return (NetworkSimplexStatus::Overflow, 0, Vec::new());
    };
    (NetworkSimplexStatus::Optimal, cost, flows)
}

/// Prove that every unchecked operation in the pivot loop fits i128.
///
/// F = 3 * max(sum finite capacities, sum |weights|, sum |demands|), or 1.
/// Every flow lies between 0 and its capacity, at most F. A tree path reaches
/// the artificial root through one artificial edge, so |potential| <= F + W,
/// where W = sum |real weights|. Reduced costs and potential shifts are bounded
/// by 2F + 3W; even the intermediate addition of a shift to an old potential is
/// bounded by 3F + 4W. The conservative 4F + 4W check covers all of these,
/// their partial subtractions, and their negations. Final costs are checked
/// separately because products of valid flows and costs can still exceed i64.
fn artificial_capacity(node_demands: &[i64], cap: &[i64], wt: &[i64]) -> Option<i128> {
    let sum_cap = cap
        .iter()
        .filter(|&&c| c != CAP_INF)
        .try_fold(0i128, |sum, &c| sum.checked_add(i128::from(c)))?;
    let sum_w = wt
        .iter()
        .try_fold(0i128, |sum, &w| sum.checked_add(i128::from(w).abs()))?;
    let sum_d = node_demands
        .iter()
        .try_fold(0i128, |sum, &d| sum.checked_add(i128::from(d).abs()))?;
    let faux_inf = sum_cap.max(sum_w).max(sum_d).checked_mul(3)?.max(1);
    faux_inf
        .checked_mul(4)?
        .checked_add(sum_w.checked_mul(4)?)?;
    Some(faux_inf)
}

/// Sum exact products without falsely rejecting a representable cancellation.
/// Each i64 product fits i128. While both signs remain, choosing the opposite
/// sign to the running sum also keeps it in i128. Once one sign is exhausted,
/// overflow implies that the final cost cannot fit i64 either.
fn exact_cost(weights: &[i64], flows: &[i64]) -> Option<i64> {
    let products = weights
        .iter()
        .zip(flows)
        .map(|(&weight, &flow)| i128::from(weight) * i128::from(flow));
    let mut positive = products.clone().filter(|&value| value > 0);
    let mut negative = products.filter(|&value| value < 0);
    let mut cost = 0i128;
    loop {
        let next = if cost < 0 {
            positive.next().or_else(|| negative.next())
        } else {
            negative.next().or_else(|| positive.next())
        };
        let Some(value) = next else {
            return i64::try_from(cost).ok();
        };
        cost = cost.checked_add(value)?;
    }
}

fn solve(
    node_demands: &[i64],
    src: &[usize],
    tgt: &[usize],
    cap: &[i64],
    wt: &[i64],
) -> (NetworkSimplexStatus, i64, Vec<i64>) {
    solve_impl::<true>(node_demands, src, tgt, cap, wt)
}

/// Runs one benchmark arm without changing the public production entry point.
#[cfg(any(test, feature = "bench-internals"))]
#[doc(hidden)]
pub fn network_simplex_int_cycle_arm(
    node_demands: &[i64],
    src: &[usize],
    tgt: &[usize],
    cap: &[i64],
    wt: &[i64],
    arm: NetworkSimplexCycleArm,
) -> NetworkSimplexIntSolution {
    let (status, cost, flows) = match arm {
        NetworkSimplexCycleArm::Allocating => solve_impl::<false>(node_demands, src, tgt, cap, wt),
        NetworkSimplexCycleArm::ReusedScratch => {
            solve_impl::<true>(node_demands, src, tgt, cap, wt)
        }
    };
    NetworkSimplexIntSolution {
        status,
        cost,
        flows,
    }
}

/// Solve an exact-integer minimum-cost-flow problem via primal network simplex.
///
/// This is the first-class Rust entry point for the exact-integer path. It is a
/// byte-exact-integer solver — flow and cost arithmetic uses widened `i128`
/// intermediates, and the result is a deterministic function of the inputs in
/// the order supplied. There is no floating-point rounding of flow or cost.
///
/// Parameters:
/// - `node_demands`: one entry per node (node index = position). NetworkX
///   convention: positive = sink (consumes flow), negative = source (supplies
///   flow). For a feasible problem the demands must sum to zero.
/// - `src`, `tgt`: parallel arrays of edge endpoints, given as node indices into
///   `node_demands`. `src.len() == tgt.len() == cap.len() == wt.len()` is the
///   number of edges. Callers are expected to have already dropped self-loops
///   and zero-capacity edges (matching the NetworkX extraction step).
/// - `cap`: per-edge capacity. Use [`CAP_INF`] ([`i64::MAX`]) for an
///   infinite-capacity edge.
/// - `wt`: per-edge cost (weight) incurred per unit of flow.
///
/// Returns a [`NetworkSimplexIntSolution`]; on
/// [`NetworkSimplexStatus::Optimal`], `flows[i]` is the integer flow on edge `i`
/// in the same order the edges were supplied, and `cost` is the exact minimum
/// total cost. Malformed edge arrays, self-loops, or zero-capacity edges return
/// [`NetworkSimplexStatus::InvalidInput`]; negative capacities and unbalanced
/// demands return [`NetworkSimplexStatus::Infeasible`]. A cost or edge flow
/// outside i64, or an internal arithmetic bound outside i128, returns
/// [`NetworkSimplexStatus::Overflow`]. All non-optimal results have zero cost
/// and an empty flow vector.
///
/// # Determinism & exact-integer guarantees
///
/// Given identical inputs, this function always returns identical output
/// (status, cost, and per-edge flows) — the tie-breaking in the entering-edge
/// block search and the leaving-edge selection are fixed, order-dependent
/// rules. No floating-point arithmetic participates in the flow or cost values.
///
/// # Example
///
/// ```ignore
/// use fnx_algorithms::network_simplex_int::{network_simplex_int, NetworkSimplexStatus, CAP_INF};
///
/// // Node 0 supplies 4 (demand -4), node 3 consumes 4 (demand +4).
/// let demands = [-4, 0, 0, 4];
/// let src = [0, 0, 1, 2];
/// let tgt = [1, 2, 3, 3];
/// let cap = [4, 4, 2, 4];
/// let wt  = [1, 2, 1, 1];
/// let sol = network_simplex_int(&demands, &src, &tgt, &cap, &wt);
/// assert_eq!(sol.status, NetworkSimplexStatus::Optimal);
/// assert_eq!(sol.cost, 10);
/// let _ = CAP_INF;
/// ```
pub fn network_simplex_int(
    node_demands: &[i64],
    src: &[usize],
    tgt: &[usize],
    cap: &[i64],
    wt: &[i64],
) -> NetworkSimplexIntSolution {
    let (status, cost, flows) = solve(node_demands, src, tgt, cap, wt);
    NetworkSimplexIntSolution {
        status,
        cost,
        flows,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Flat `(node_demands, src, tgt, cap, wt)` arrays describing a fixed-size
    /// test problem, in the argument order [`network_simplex_int`] expects.
    type ProblemArrays = ([i64; 4], [usize; 4], [usize; 4], [i64; 4], [i64; 4]);

    /// Small transportation problem with a known exact-integer optimum.
    ///
    /// Node 0 supplies 4 units (demand -4); node 3 consumes 4 (demand +4);
    /// nodes 1 and 2 are transshipment. Edges (src,tgt,cap,wt):
    ///   0->1 cap4 wt1, 0->2 cap4 wt2, 1->3 cap2 wt1, 2->3 cap4 wt1.
    /// Cheapest route 0->1->3 (per-unit 2) is bottlenecked at 1->3 cap 2, so
    /// 2 units flow there and the remaining 2 take 0->2->3 (per-unit 3):
    ///   cost = 2*(1+1) + 2*(2+1) = 4 + 6 = 10.
    fn small_problem() -> ProblemArrays {
        let demands = [-4i64, 0, 0, 4];
        let src = [0usize, 0, 1, 2];
        let tgt = [1usize, 2, 3, 3];
        let cap = [4i64, 4, 2, 4];
        let wt = [1i64, 2, 1, 1];
        (demands, src, tgt, cap, wt)
    }

    type OwnedProblem = (Vec<i64>, Vec<usize>, Vec<usize>, Vec<i64>, Vec<i64>);

    fn assignment_problem(side: usize) -> OwnedProblem {
        const OFFSETS: [usize; 4] = [0, 1, 7, 19];

        let mut demands = vec![-1; side];
        demands.extend(std::iter::repeat_n(1, side));
        let mut src = Vec::with_capacity(side * OFFSETS.len());
        let mut tgt = Vec::with_capacity(side * OFFSETS.len());
        let mut cap = Vec::with_capacity(side * OFFSETS.len());
        let mut wt = Vec::with_capacity(side * OFFSETS.len());
        for supplier in 0..side {
            for (lane, offset) in OFFSETS.into_iter().enumerate() {
                let sink = (supplier + offset) % side;
                src.push(supplier);
                tgt.push(side + sink);
                cap.push(1);
                wt.push(((supplier * 17 + sink * 13 + lane * 5) % 11) as i64 - 5);
            }
        }
        (demands, src, tgt, cap, wt)
    }

    fn solve_with_trace<const REUSE: bool>(
        problem: &OwnedProblem,
    ) -> ((NetworkSimplexStatus, i64, Vec<i64>), CycleTrace) {
        let (demands, src, tgt, cap, wt) = problem;
        CYCLE_TRACE.with(|trace| trace.set(CycleTrace::default()));
        let result = solve_impl::<REUSE>(demands, src, tgt, cap, wt);
        let trace = CYCLE_TRACE.with(std::cell::Cell::get);
        (result, trace)
    }

    fn assert_cycle_scratch_parity(problem: &OwnedProblem) -> CycleTrace {
        let (allocating, allocating_trace) = solve_with_trace::<false>(problem);
        let (reused, reused_trace) = solve_with_trace::<true>(problem);
        assert_eq!(
            reused, allocating,
            "scratch reuse must preserve status, cost, and input-order flows"
        );
        assert_eq!(
            reused_trace, allocating_trace,
            "scratch reuse must preserve pivot and path traversal counts"
        );
        reused_trace
    }

    #[test]
    fn cycle_scratch_matches_allocating_baseline() {
        let (d, s, t, c, w) = small_problem();
        assert_cycle_scratch_parity(&(d.to_vec(), s.to_vec(), t.to_vec(), c.to_vec(), w.to_vec()));
        assert_cycle_scratch_parity(&(vec![-4, 4], vec![0], vec![1], vec![2], vec![1]));
        assert_cycle_scratch_parity(&(
            vec![-1, 0, 0, 1],
            vec![0, 1, 0, 2],
            vec![1, 3, 2, 3],
            vec![CAP_INF; 4],
            vec![1, 5, 2, 1],
        ));
        assert_cycle_scratch_parity(&(Vec::new(), Vec::new(), Vec::new(), Vec::new(), Vec::new()));
        assert_cycle_scratch_parity(&assignment_problem(32));
        assert_eq!(
            assert_cycle_scratch_parity(&assignment_problem(64)),
            CycleTrace {
                pivots: 140,
                path_calls: 280,
                path_hops: 719,
            },
            "the resurrected fixture must retain its pre-edit operation profile"
        );
    }

    #[test]
    fn known_integer_optimum() {
        let (d, s, t, c, w) = small_problem();
        let sol = network_simplex_int(&d, &s, &t, &c, &w);
        assert_eq!(sol.status, NetworkSimplexStatus::Optimal);
        assert_eq!(sol.cost, 10, "exact integer optimum cost");
        // Flows are returned in input edge order: [0->1, 0->2, 1->3, 2->3].
        assert_eq!(sol.flows, vec![2, 2, 2, 2]);
        // Cross-check: cost recomputed from flows equals reported cost, exactly.
        let recomputed: i64 = w.iter().zip(&sol.flows).map(|(wi, fi)| wi * fi).sum();
        assert_eq!(recomputed, sol.cost);
    }

    #[test]
    fn determinism_across_repeated_runs() {
        let (d, s, t, c, w) = small_problem();
        let first = network_simplex_int(&d, &s, &t, &c, &w);
        for run in 0..64 {
            let again = network_simplex_int(&d, &s, &t, &c, &w);
            assert_eq!(again, first, "run {run} diverged from the first solve");
        }
    }

    #[test]
    fn infeasible_when_capacity_insufficient() {
        // 0 supplies 4, 3 demands 4, but only a single cap-2 edge connects them.
        let demands = [-4i64, 4];
        let src = [0usize];
        let tgt = [1usize];
        let cap = [2i64];
        let wt = [1i64];
        let sol = network_simplex_int(&demands, &src, &tgt, &cap, &wt);
        assert_eq!(sol.status, NetworkSimplexStatus::Infeasible);
        assert_eq!(sol.cost, 0);
        assert!(sol.flows.is_empty());
    }

    #[test]
    fn empty_graph_is_trivially_optimal() {
        let sol = network_simplex_int(&[], &[], &[], &[], &[]);
        assert_eq!(sol.status, NetworkSimplexStatus::Optimal);
        assert_eq!(sol.cost, 0);
        assert!(sol.flows.is_empty());
    }

    #[test]
    fn infinite_capacity_shortest_path() {
        // Shortest-path-as-min-cost-flow: unit demand from 0 to 3, all edges
        // infinite capacity. Cheapest 0->..->3 path cost is the answer.
        //   0->1 wt1, 1->3 wt5, 0->2 wt2, 2->3 wt1  => best is 0->2->3 = 3.
        let demands = [-1i64, 0, 0, 1];
        let src = [0usize, 1, 0, 2];
        let tgt = [1usize, 3, 2, 3];
        let cap = [CAP_INF, CAP_INF, CAP_INF, CAP_INF];
        let wt = [1i64, 5, 2, 1];
        let sol = network_simplex_int(&demands, &src, &tgt, &cap, &wt);
        assert_eq!(sol.status, NetworkSimplexStatus::Optimal);
        assert_eq!(sol.cost, 3, "0->2->3 exact shortest path cost");
        // No flow on the expensive 0->1 / 1->3 edges; one unit on 0->2->3.
        assert_eq!(sol.flows, vec![0, 0, 1, 1]);
    }

    #[test]
    fn large_finite_capacity_keeps_a_small_optimum_exact() {
        let sol = network_simplex_int(&[-1, 1], &[0], &[1], &[i64::MAX - 1], &[1]);
        assert_eq!(sol.status, NetworkSimplexStatus::Optimal);
        assert_eq!(sol.cost, 1);
        assert_eq!(sol.flows, [1]);
    }

    #[test]
    fn extreme_i64_weights_preserve_exact_cost() {
        for weight in [i64::MIN, i64::MAX] {
            let sol = network_simplex_int(&[-1, 1], &[0], &[1], &[CAP_INF], &[weight]);
            assert_eq!(sol.status, NetworkSimplexStatus::Optimal);
            assert_eq!(sol.cost, weight);
            assert_eq!(sol.flows, [1]);
        }
    }

    #[test]
    fn minimum_i64_demand_splits_into_representable_flows() {
        let sol = network_simplex_int(
            &[i64::MIN, i64::MAX, 1],
            &[0, 0],
            &[1, 2],
            &[CAP_INF, 1],
            &[0, 0],
        );
        assert_eq!(sol.status, NetworkSimplexStatus::Optimal);
        assert_eq!(sol.cost, 0);
        assert_eq!(sol.flows, [i64::MAX, 1]);
    }

    #[test]
    fn canceling_costs_are_exact_even_when_a_prefix_exceeds_i128() {
        // Three positive products exceed i128::MAX, but the full path costs
        // exactly zero. Neither i64 multiplication nor an unchecked i128
        // input-order sum is sufficient for the public exact-cost contract.
        let bound = i64::MAX;
        let sol = network_simplex_int(
            &[-bound, 0, 0, 0, 0, 0, bound],
            &[0, 1, 2, 3, 4, 5],
            &[1, 2, 3, 4, 5, 6],
            &[CAP_INF; 6],
            &[bound, bound, bound, -bound, -bound, -bound],
        );
        assert_eq!(sol.status, NetworkSimplexStatus::Optimal);
        assert_eq!(sol.cost, 0);
        assert_eq!(sol.flows, [bound; 6]);
    }

    #[test]
    fn unrepresentable_cost_or_flow_returns_overflow() {
        for weight in [i64::MIN, i64::MAX] {
            let sol = network_simplex_int(&[-2, 2], &[0], &[1], &[2], &[weight]);
            assert_eq!(sol.status, NetworkSimplexStatus::Overflow);
            assert_eq!(sol.cost, 0);
            assert!(sol.flows.is_empty());
        }
        // The first edge must carry 2**63 units even though each input demand
        // fits i64 and the total cost is zero.
        let sol = network_simplex_int(
            &[i64::MIN, i64::MAX, 1],
            &[0, 1],
            &[1, 2],
            &[CAP_INF; 2],
            &[0, 0],
        );
        assert_eq!(sol.status, NetworkSimplexStatus::Overflow);
        assert_eq!(sol.cost, 0);
        assert!(sol.flows.is_empty());
    }

    #[test]
    fn infinite_and_finite_capacity_statuses_preserve_reference_behavior() {
        let unbounded = network_simplex_int(&[0, 0], &[0, 1], &[1, 0], &[CAP_INF; 2], &[-1, 0]);
        assert_eq!(unbounded.status, NetworkSimplexStatus::Unbounded);
        assert_eq!(unbounded.cost, 0);
        assert!(unbounded.flows.is_empty());

        // The negative cycle is limited by its finite return edge. Preserve
        // the reference optimum below its artificial-flow cutoff.
        let bounded = network_simplex_int(&[-1, 1], &[0, 1], &[1, 0], &[CAP_INF, 4], &[-1, 0]);
        assert_eq!(bounded.status, NetworkSimplexStatus::Optimal);
        assert_eq!(bounded.cost, -5);
        assert_eq!(bounded.flows, [5, 4]);

        // The largest finite capacity is still a capacity, even with a
        // negative cycle. No rounding or sentinel comparison can erase it.
        let finite = network_simplex_int(&[0, 0], &[0, 1], &[1, 0], &[i64::MAX - 1; 2], &[-1, 0]);
        assert_eq!(finite.status, NetworkSimplexStatus::Optimal);
        assert_eq!(finite.cost, -(i64::MAX - 1));
        assert_eq!(finite.flows, [i64::MAX - 1; 2]);
    }

    #[test]
    fn infeasibility_is_checked_before_wide_cost_arithmetic() {
        let insufficient = network_simplex_int(&[-2, 2], &[0], &[1], &[1], &[i64::MIN]);
        assert_eq!(insufficient.status, NetworkSimplexStatus::Infeasible);
        let negative = network_simplex_int(&[0, 0], &[0], &[1], &[-1], &[0]);
        assert_eq!(negative.status, NetworkSimplexStatus::Infeasible);
        let unbalanced = network_simplex_int(&[i64::MAX, 1], &[], &[], &[], &[]);
        assert_eq!(unbalanced.status, NetworkSimplexStatus::Infeasible);
    }

    #[test]
    fn malformed_arrays_fail_without_panicking_or_entering_the_pivot_loop() {
        let invalid = [
            network_simplex_int(&[0, 0], &[0], &[], &[1], &[0]),
            network_simplex_int(&[0, 0], &[0], &[1], &[], &[0]),
            network_simplex_int(&[0, 0], &[0], &[1], &[1], &[]),
            network_simplex_int(&[0, 0], &[2], &[1], &[1], &[0]),
            network_simplex_int(&[0, 0], &[0], &[2], &[1], &[0]),
            network_simplex_int(&[0], &[0], &[0], &[1], &[0]),
            network_simplex_int(&[0, 0], &[0], &[1], &[0], &[-1]),
            network_simplex_int(&[], &[0], &[1], &[1], &[0]),
        ];
        for sol in invalid {
            assert_eq!(sol.status, NetworkSimplexStatus::InvalidInput);
            assert_eq!(sol.cost, 0);
            assert!(sol.flows.is_empty());
        }
    }

    #[test]
    fn finite_small_networks_match_exhaustive_flow_enumeration() {
        let sources = [0, 1, 0, 2];
        let targets = [1, 2, 2, 0];
        for seed in 0..125i64 {
            let demands = [-2, 0, 2];
            let capacities = [1 + seed % 3, 1 + seed / 3 % 3, 3, 2];
            let weights = [seed % 5 - 2, seed / 5 % 5 - 2, seed / 25 % 5 - 2, -1];
            let mut best = None;
            for a in 0..=capacities[0] {
                for b in 0..=capacities[1] {
                    for c in 0..=capacities[2] {
                        for d in 0..=capacities[3] {
                            if [-a - c + d, a - b, b + c - d] == demands {
                                let cost = a * weights[0]
                                    + b * weights[1]
                                    + c * weights[2]
                                    + d * weights[3];
                                best = Some(best.map_or(cost, |previous: i64| previous.min(cost)));
                            }
                        }
                    }
                }
            }
            let sol = network_simplex_int(&demands, &sources, &targets, &capacities, &weights);
            if let Some(cost) = best {
                assert_eq!(sol.status, NetworkSimplexStatus::Optimal, "seed {seed}");
                assert_eq!(sol.cost, cost, "seed {seed}");
                let mut balance = [0; 3];
                for edge in 0..4 {
                    assert!((0..=capacities[edge]).contains(&sol.flows[edge]));
                    balance[sources[edge]] -= sol.flows[edge];
                    balance[targets[edge]] += sol.flows[edge];
                }
                assert_eq!(balance, demands, "flow conservation for seed {seed}");
                let recomputed: i64 = weights.iter().zip(&sol.flows).map(|(w, f)| w * f).sum();
                assert_eq!(recomputed, sol.cost);
            } else {
                assert_eq!(sol.status, NetworkSimplexStatus::Infeasible, "seed {seed}");
            }
        }
    }
}
