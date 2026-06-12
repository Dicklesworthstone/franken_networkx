//! br-r37-c1-8foqi: native safe-Rust integer primal network-simplex kernel.
//!
//! A faithful transcription of NetworkX's `network_simplex`
//! (`networkx/algorithms/flow/networksimplex.py`, BSD-licensed) pivot logic,
//! specialised to integer demands/capacities/weights (the common, and the only
//! byte-exact-int, case). The Python port keeps the graph I/O and flow-dict
//! construction; this kernel replaces only the array-based spanning-tree pivot
//! loop, which is the Python-bound remainder that left `min_cost_flow` ~1.25x
//! slower than nx.
//!
//! NetworkX uses a dummy root node and encodes "no parent" / the root via
//! Python's negative-index alias `-1` (which addresses the dummy root stored at
//! index `n`). Here the root is the explicit index `n`, and a true `None`
//! parent is `NONE = usize::MAX`.

#![allow(clippy::needless_range_loop)]

use pyo3::prelude::*;

const NONE: usize = usize::MAX;

/// Result status of the solve.
#[derive(PartialEq, Eq)]
pub enum NsStatus {
    Optimal,
    Infeasible,
    Unbounded,
}

struct Simplex {
    // length edge_count + n (artificial edges appended)
    edge_sources: Vec<usize>,
    edge_targets: Vec<usize>,
    edge_capacities: Vec<i64>,
    edge_weights: Vec<i64>,
    edge_flow: Vec<i64>,
    // length n
    node_potentials: Vec<i64>,
    // length n + 1 (index n == root)
    parent: Vec<usize>,
    parent_edge: Vec<usize>,
    subtree_size: Vec<usize>,
    next_node_dft: Vec<usize>,
    prev_node_dft: Vec<usize>,
    last_descendent_dft: Vec<usize>,
}

impl Simplex {
    #[inline]
    fn reduced_cost(&self, i: usize) -> i64 {
        let c = self.edge_weights[i] - self.node_potentials[self.edge_sources[i]]
            + self.node_potentials[self.edge_targets[i]];
        if self.edge_flow[i] == 0 { c } else { -c }
    }

    #[inline]
    fn residual_capacity(&self, i: usize, p: usize) -> i64 {
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

    /// Returns (Wn, We) on the path from node p up to its ancestor w.
    fn trace_path(&self, mut p: usize, w: usize) -> (Vec<usize>, Vec<usize>) {
        let mut wn = vec![p];
        let mut we = Vec::new();
        while p != w {
            we.push(self.parent_edge[p]);
            p = self.parent[p];
            wn.push(p);
        }
        (wn, we)
    }

    /// Returns (Wn, We) for the cycle created by adding edge i == (p, q),
    /// oriented from p to q.
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

    fn augment_flow(&mut self, wn: &[usize], we: &[usize], f: i64) {
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

/// Solve the integer min-cost-flow problem. `node_demands` has length n; the
/// edge arrays have length edge_count (the real, non-self-loop, non-zero-cap
/// edges already filtered by the caller). Returns the flow on each real edge.
pub fn solve(
    node_demands: &[i64],
    src: &[usize],
    tgt: &[usize],
    cap: &[i64], // i64::MAX represents +inf
    wt: &[i64],
) -> (NsStatus, i64, Vec<i64>) {
    let n = node_demands.len();
    let edge_count = src.len();

    if n == 0 {
        return (NsStatus::Optimal, 0, Vec::new());
    }

    let inf = i64::MAX;

    // faux_inf = 3 * max(sum finite caps, sum |weights|, sum |demands|) or 1
    let mut sum_cap: i64 = 0;
    for &c in cap {
        if c < inf {
            sum_cap += c;
        }
    }
    let mut sum_w: i64 = 0;
    for &w in wt {
        sum_w += w.abs();
    }
    let mut sum_d: i64 = 0;
    for &d in node_demands {
        sum_d += d.abs();
    }
    let faux_inf = {
        let m = sum_cap.max(sum_w).max(sum_d);
        if m == 0 { 1 } else { 3 * m }
    };

    // Build full edge arrays: real edges, then n artificial root edges.
    let total = edge_count + n;
    let mut edge_sources = Vec::with_capacity(total);
    let mut edge_targets = Vec::with_capacity(total);
    let mut edge_capacities = Vec::with_capacity(total);
    let mut edge_weights = Vec::with_capacity(total);
    edge_sources.extend_from_slice(src);
    edge_targets.extend_from_slice(tgt);
    edge_capacities.extend_from_slice(cap);
    edge_weights.extend_from_slice(wt);
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
    let mut edge_flow = vec![0i64; edge_count];
    edge_flow.extend(node_demands.iter().map(|d| d.abs()));
    let node_potentials: Vec<i64> = node_demands
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
        while m < big_m {
            // next block [f, l) cyclically over 0..edge_count
            let l = f + b;
            // find first edge with the lowest reduced cost in the block
            let mut best_i = usize::MAX;
            let mut best_c = 0i64;
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
            let (mut p, mut q) = if sx.edge_flow[i] == 0 {
                (sx.edge_sources[i], sx.edge_targets[i])
            } else {
                (sx.edge_targets[i], sx.edge_sources[i])
            };
            m = 0;
            // process this entering edge (the loop body of the Python for-loop)
            let (wn, we) = sx.find_cycle(i, p, q);
            let (j, mut s, mut t) = sx.find_leaving_edge(&wn, &we);
            let rc = sx.residual_capacity(j, s);
            sx.augment_flow(&wn, &we, rc);
            if i != j {
                if sx.parent[t] != s {
                    std::mem::swap(&mut s, &mut t);
                }
                // We.index(i) > We.index(j): first occurrence positions
                let pos_i = we.iter().position(|&x| x == i).unwrap();
                let pos_j = we.iter().position(|&x| x == j).unwrap();
                if pos_i > pos_j {
                    std::mem::swap(&mut p, &mut q);
                }
                sx.remove_edge(s, t);
                sx.make_root(q);
                sx.add_edge(i, p, q);
                sx.update_potentials(i, p, q);
            }
        }
    }

    // Infeasibility: any artificial edge (indices edge_count..edge_count+n) has
    // nonzero flow.
    for i in edge_count..edge_count + n {
        if sx.edge_flow[i] != 0 {
            return (NsStatus::Infeasible, 0, Vec::new());
        }
    }
    // Unboundedness: any real edge has flow*2 >= faux_inf.
    for i in 0..edge_count {
        if sx.edge_flow[i].saturating_mul(2) >= faux_inf {
            return (NsStatus::Unbounded, 0, Vec::new());
        }
    }

    let mut cost: i64 = 0;
    for i in 0..edge_count {
        cost += sx.edge_weights[i] * sx.edge_flow[i];
    }
    let flows: Vec<i64> = sx.edge_flow[..edge_count].to_vec();
    (NsStatus::Optimal, cost, flows)
}

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
    // Map the caller's +inf sentinel to i64::MAX used internally.
    let cap2: Vec<i64> = cap
        .iter()
        .map(|&c| if c >= cap_inf { i64::MAX } else { c })
        .collect();
    let (status, cost, flows) = solve(&node_demands, &src, &tgt, &cap2, &wt);
    let code = match status {
        NsStatus::Optimal => 0,
        NsStatus::Infeasible => 1,
        NsStatus::Unbounded => 2,
    };
    (code, cost, flows)
}
