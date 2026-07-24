#![forbid(unsafe_code)]

pub mod digraph;

use fnx_runtime::{
    CgseValue, CompatibilityMode, DecisionAction, EvidenceLedger, EvidenceTerm, RuntimePolicy,
};
use indexmap::{IndexMap, IndexSet};
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

// br-r37-c1-fxhash: the node (String) and edge ((usize,usize)) key->index maps use
// a FAST non-cryptographic hasher instead of std's SipHash. IndexMap keeps insertion
// order in its Vec, so iteration order (nodes/edges/edges_ordered) is UNCHANGED — only
// lookup/insert hashing gets faster. The (usize,usize) edge keys especially: SipHash on
// 16 bytes (~20ns) -> FxHash on a usize (~3ns). Speeds up every has_edge/edge_attrs/
// get_index_of/construction insert across the library.
pub(crate) type FxIndexMap<K, V> = IndexMap<K, V, rustc_hash::FxBuildHasher>;
use std::collections::HashSet;
use std::fmt;

pub type AttrMap = BTreeMap<String, CgseValue>;

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
struct EdgeKey {
    left: String,
    right: String,
}

impl EdgeKey {
    fn new(left: &str, right: &str) -> Self {
        if left <= right {
            Self {
                left: left.to_owned(),
                right: right.to_owned(),
            }
        } else {
            Self {
                left: right.to_owned(),
                right: left.to_owned(),
            }
        }
    }
}

#[derive(Hash, PartialEq, Eq, Clone, Copy)]
struct EdgeKeyRef<'a> {
    left: &'a str,
    right: &'a str,
}

impl<'a> EdgeKeyRef<'a> {
    fn new(left: &'a str, right: &'a str) -> Self {
        if left <= right {
            Self { left, right }
        } else {
            Self {
                left: right,
                right: left,
            }
        }
    }
}

impl<'a> indexmap::Equivalent<EdgeKey> for EdgeKeyRef<'a> {
    fn equivalent(&self, key: &EdgeKey) -> bool {
        self.left == key.left && self.right == key.right
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum GraphError {
    FailClosed {
        operation: &'static str,
        reason: String,
    },
}

impl fmt::Display for GraphError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::FailClosed { operation, reason } => {
                write!(f, "operation `{operation}` failed closed: {reason}")
            }
        }
    }
}

impl std::error::Error for GraphError {}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct EdgeSnapshot {
    pub left: String,
    pub right: String,
    pub attrs: AttrMap,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct GraphSnapshot {
    pub mode: CompatibilityMode,
    pub nodes: Vec<String>,
    /// br-snapnodeattrs: node attributes keyed by node name. Preserved
    /// across the ``snapshot`` round-trip so a graph with
    /// ``add_node(n, attrs)`` doesn't lose those attrs when replayed.
    /// Defaults to empty for snapshots produced by old code paths;
    /// consumers that don't care can ignore it.
    #[serde(default)]
    pub node_attrs: BTreeMap<String, AttrMap>,
    pub edges: Vec<EdgeSnapshot>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct MultiEdgeSnapshot {
    pub left: String,
    pub right: String,
    pub key: usize,
    pub attrs: AttrMap,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct MultiGraphSnapshot {
    pub mode: CompatibilityMode,
    pub nodes: Vec<String>,
    /// See ``GraphSnapshot::node_attrs``.
    #[serde(default)]
    pub node_attrs: BTreeMap<String, AttrMap>,
    pub edges: Vec<MultiEdgeSnapshot>,
}

#[derive(Debug, Clone)]
pub struct Graph {
    mode: CompatibilityMode,
    revision: u64,
    nodes: FxIndexMap<String, AttrMap>,
    // br-r37-c1-d58s8 P2(c) slice 2: the String adjacency rows are GONE —
    // adj_indices (order-faithful integer rows) is the single row store;
    // String views derive through the nodes name table.
    /// Integer-indexed adjacency list for O(1) traversal. Each entry
    /// `adj_indices[i]` contains the node indices of neighbors of node i.
    /// This mirrors `adjacency` but avoids string hashing during BFS/CC.
    adj_indices: Vec<Vec<usize>>,
    /// br-r37-c1-d58s8: revision-keyed all-int weights memo (see
    /// DiGraph::all_int_cache).
    all_int_cache: std::sync::Arc<std::sync::RwLock<Option<(u64, String, bool)>>>,
    edge_index_endpoints: Vec<(usize, usize)>,
    // br-r37-c1-d58s8 edges-map flip: keyed by the INDEX-CANONICAL
    // (min_idx, max_idx) node pair — zero String allocs/hashes per
    // insert (the profiled remaining store tax). Node removal REKEYS
    // via the same remap as the row repair. edge_index_endpoints keeps
    // the string-canonical orientation for snapshot derivation.
    edges: FxIndexMap<(usize, usize), AttrMap>,
    runtime_policy: RuntimePolicy,
}

impl Graph {
    #[must_use]
    pub fn new(mode: CompatibilityMode) -> Self {
        Self {
            mode,
            revision: 0,
            nodes: FxIndexMap::default(),
            adj_indices: Vec::new(),
            all_int_cache: std::sync::Arc::default(),
            edge_index_endpoints: Vec::new(),
            edges: FxIndexMap::default(),
            runtime_policy: RuntimePolicy::new(mode),
        }
    }

    #[must_use]
    pub fn with_runtime_policy(runtime_policy: RuntimePolicy) -> Self {
        let mode = runtime_policy.mode();
        Self {
            mode,
            revision: 0,
            nodes: FxIndexMap::default(),
            adj_indices: Vec::new(),
            all_int_cache: std::sync::Arc::default(),
            edge_index_endpoints: Vec::new(),
            edges: FxIndexMap::default(),
            runtime_policy,
        }
    }

    /// br-r37-c1-clearedgesinplace (cc): drop all edges in place, keeping nodes (and
    /// their index/order/attrs). O(E) teardown + O(V) row clears -- the binding's prior
    /// path rebuilt a fresh Graph with a per-node add_node loop (ledger record_decision
    /// tax + node-attr clone + old-inner drop), ~20x slower than nx. Sibling of
    /// MultiGraph::clear_edges. adj_indices keeps its N rows (one per node), emptied;
    /// the revision bump invalidates all_int_cache.
    pub fn clear_edges(&mut self) {
        if self.edges.is_empty() && self.edge_index_endpoints.is_empty() {
            return;
        }
        self.edges.clear();
        self.edge_index_endpoints.clear();
        for row in &mut self.adj_indices {
            row.clear();
        }
        self.revision = self.revision.saturating_add(1);
    }

    #[must_use]
    pub fn strict() -> Self {
        Self::new(CompatibilityMode::Strict)
    }

    #[must_use]
    pub fn complete_graph(mode: CompatibilityMode, n: usize) -> Self {
        let edge_capacity = n.saturating_mul(n.saturating_sub(1)) / 2;
        let revision = u64::try_from(n)
            .unwrap_or(u64::MAX)
            .saturating_add(u64::try_from(edge_capacity).unwrap_or(u64::MAX));
        let node_labels = (0..n).map(|node| node.to_string()).collect::<Vec<_>>();
        let mut graph = Self {
            mode,
            revision,
            nodes: FxIndexMap::with_capacity_and_hasher(n, rustc_hash::FxBuildHasher),
            adj_indices: vec![Vec::with_capacity(n.saturating_sub(1)); n],
            all_int_cache: std::sync::Arc::default(),
            edge_index_endpoints: Vec::with_capacity(edge_capacity),
            edges: FxIndexMap::with_capacity_and_hasher(edge_capacity, rustc_hash::FxBuildHasher),
            runtime_policy: RuntimePolicy::new(mode),
        };

        for node in &node_labels {
            graph.nodes.insert(node.clone(), AttrMap::new());
        }

        for left_index in 0..n {
            let _left = &node_labels[left_index];
            for (right_index, _right) in node_labels.iter().enumerate().skip(left_index + 1) {
                // Maintain integer adjacency
                graph.adj_indices[left_index].push(right_index);
                graph.adj_indices[right_index].push(left_index);
                graph.edge_index_endpoints.push((left_index, right_index));
                graph
                    .edges
                    .insert(Graph::canon_pair(left_index, right_index), AttrMap::new());
            }
        }

        graph.record_decision(
            "complete_graph_bulk",
            0.0,
            false,
            vec![EvidenceTerm {
                signal: "nodes".to_owned(),
                observed_value: n.to_string(),
                log_likelihood_ratio: 0.0,
            }],
        );
        graph
    }

    /// Build a non-periodic 2-D grid with NetworkX's node and edge insertion
    /// sequence. Canonical node keys are row-major all-int tuple strings like
    /// "(i, j)".
    #[must_use]
    pub fn grid_2d(mode: CompatibilityMode, m: usize, n: usize) -> Self {
        let node_count = m.saturating_mul(n);
        let edge_capacity = m
            .saturating_sub(1)
            .saturating_mul(n)
            .saturating_add(n.saturating_sub(1).saturating_mul(m));
        let revision = u64::try_from(node_count)
            .unwrap_or(u64::MAX)
            .saturating_add(u64::try_from(edge_capacity).unwrap_or(u64::MAX));
        let label = |i: usize, j: usize| format!("({i}, {j})");
        let idx = |i: usize, j: usize| i * n + j;
        let mut graph = Self {
            mode,
            revision,
            nodes: FxIndexMap::with_capacity_and_hasher(node_count, rustc_hash::FxBuildHasher),
            adj_indices: vec![Vec::with_capacity(4); node_count],
            all_int_cache: std::sync::Arc::default(),
            edge_index_endpoints: Vec::with_capacity(edge_capacity),
            edges: FxIndexMap::with_capacity_and_hasher(edge_capacity, rustc_hash::FxBuildHasher),
            runtime_policy: RuntimePolicy::new(mode),
        };
        for i in 0..m {
            for j in 0..n {
                let key = label(i, j);
                graph.nodes.insert(key.clone(), AttrMap::new());
            }
        }
        fn add_grid_edge(graph: &mut Graph, _u: String, _v: String, u_idx: usize, v_idx: usize) {
            // add_edge appends v to row[u] first, then u to row[v].
            graph.adj_indices[u_idx].push(v_idx);
            graph.adj_indices[v_idx].push(u_idx);
            graph.edge_index_endpoints.push((u_idx, v_idx));
            graph
                .edges
                .insert(Graph::canon_pair(u_idx, v_idx), AttrMap::new());
        }
        // Phase 1: for (pi, i) in pairwise(rows), for j in cols.
        for i in 1..m {
            for j in 0..n {
                add_grid_edge(
                    &mut graph,
                    label(i, j),
                    label(i - 1, j),
                    idx(i, j),
                    idx(i - 1, j),
                );
            }
        }
        // Phase 2: for i in rows, for (pj, j) in pairwise(cols).
        for i in 0..m {
            for j in 1..n {
                add_grid_edge(
                    &mut graph,
                    label(i, j),
                    label(i, j - 1),
                    idx(i, j),
                    idx(i, j - 1),
                );
            }
        }
        graph.record_decision(
            "grid_2d_bulk",
            0.0,
            false,
            vec![EvidenceTerm {
                signal: "nodes".to_owned(),
                observed_value: node_count.to_string(),
                log_likelihood_ratio: 0.0,
            }],
        );
        graph
    }

    /// Build NetworkX's n-dimensional integer grid graph in one bulk pass.
    ///
    /// NetworkX constructs this as repeated cartesian products of path/cycle
    /// graphs, then flattens the nested tuple labels. The product order matters:
    /// periodic axes use cycle edge-view order, not a simple coordinate loop.
    pub fn grid_nd(
        mode: CompatibilityMode,
        dimensions: &[usize],
        periodic: &[bool],
    ) -> Result<Self, GraphError> {
        if dimensions.len() != periodic.len() {
            return Err(GraphError::FailClosed {
                operation: "grid_nd",
                reason: format!(
                    "periodic flag count {} does not match dimension count {}",
                    periodic.len(),
                    dimensions.len()
                ),
            });
        }
        if dimensions.is_empty() {
            return Ok(Self::new(mode));
        }

        #[derive(Clone)]
        struct ProductState {
            node_count: usize,
            adjacency: Vec<Vec<usize>>,
            edge_set: HashSet<(usize, usize)>,
        }

        impl ProductState {
            fn empty() -> Self {
                Self {
                    node_count: 0,
                    adjacency: Vec::new(),
                    edge_set: HashSet::new(),
                }
            }

            fn axis(size: usize, periodic: bool) -> Self {
                let mut state = Self {
                    node_count: size,
                    adjacency: vec![Vec::new(); size],
                    edge_set: HashSet::new(),
                };
                if size == 0 {
                    return state;
                }
                if periodic {
                    if size == 1 {
                        state.add_edge(0, 0);
                    } else {
                        for node in 0..(size - 1) {
                            state.add_edge(node, node + 1);
                        }
                        state.add_edge(size - 1, 0);
                    }
                } else {
                    for node in 0..size.saturating_sub(1) {
                        state.add_edge(node, node + 1);
                    }
                }
                state
            }

            fn product(axis: &Self, old: &Self) -> Result<Self, GraphError> {
                let Some(node_count) = axis.node_count.checked_mul(old.node_count) else {
                    return Err(GraphError::FailClosed {
                        operation: "grid_nd",
                        reason: "node count overflow during cartesian product".to_owned(),
                    });
                };
                if node_count == 0 {
                    return Ok(Self::empty());
                }

                let axis_edges = axis.edges_view();
                let old_edges = old.edges_view();
                let mut state = Self {
                    node_count,
                    adjacency: vec![Vec::new(); node_count],
                    edge_set: HashSet::with_capacity(
                        axis_edges
                            .len()
                            .saturating_mul(old.node_count)
                            .saturating_add(old_edges.len().saturating_mul(axis.node_count)),
                    ),
                };

                for (axis_left, axis_right) in axis_edges {
                    let left_base = axis_left * old.node_count;
                    let right_base = axis_right * old.node_count;
                    for old_index in 0..old.node_count {
                        state.add_edge(left_base + old_index, right_base + old_index);
                    }
                }
                for axis_index in 0..axis.node_count {
                    let base = axis_index * old.node_count;
                    for &(old_left, old_right) in &old_edges {
                        state.add_edge(base + old_left, base + old_right);
                    }
                }
                Ok(state)
            }

            fn add_edge(&mut self, left: usize, right: usize) {
                let key = if left <= right {
                    (left, right)
                } else {
                    (right, left)
                };
                if !self.edge_set.insert(key) {
                    return;
                }
                self.adjacency[left].push(right);
                if left != right {
                    self.adjacency[right].push(left);
                }
            }

            fn edges_view(&self) -> Vec<(usize, usize)> {
                let mut edges = Vec::with_capacity(self.edge_set.len());
                let mut seen = vec![false; self.node_count];
                for left in 0..self.node_count {
                    for &right in &self.adjacency[left] {
                        if !seen[right] {
                            edges.push((left, right));
                        }
                    }
                    seen[left] = true;
                }
                edges
            }
        }

        fn coords_from_index(mut index: usize, sizes: &[usize]) -> Vec<usize> {
            let mut coords = vec![0; sizes.len()];
            for axis in (0..sizes.len()).rev() {
                let size = sizes[axis];
                coords[axis] = index % size;
                index /= size;
            }
            coords
        }

        fn tuple_canonical(coords: &[usize]) -> String {
            if let [value] = coords {
                return value.to_string();
            }
            let mut s = String::with_capacity(coords.len() * 6 + 2);
            s.push('(');
            for (i, value) in coords.iter().enumerate() {
                if i > 0 {
                    s.push_str(", ");
                }
                s.push_str(&value.to_string());
            }
            s.push(')');
            s
        }

        let mut state = ProductState::axis(dimensions[0], periodic[0]);
        for (&size, &periodic_axis) in dimensions.iter().zip(periodic).skip(1) {
            let axis = ProductState::axis(size, periodic_axis);
            state = ProductState::product(&axis, &state)?;
        }

        let output_sizes = dimensions.iter().rev().copied().collect::<Vec<_>>();
        let labels = (0..state.node_count)
            .map(|index| tuple_canonical(&coords_from_index(index, &output_sizes)))
            .collect::<Vec<_>>();
        let edge_view = state.edges_view();
        let mut final_adjacency = vec![Vec::new(); state.node_count];
        for &(left, right) in &edge_view {
            final_adjacency[left].push(right);
            if left != right {
                final_adjacency[right].push(left);
            }
        }
        let revision = u64::try_from(state.node_count)
            .unwrap_or(u64::MAX)
            .saturating_add(u64::try_from(edge_view.len()).unwrap_or(u64::MAX));
        let mut graph = Self {
            mode,
            revision,
            nodes: FxIndexMap::with_capacity_and_hasher(
                state.node_count,
                rustc_hash::FxBuildHasher,
            ),
            adj_indices: Vec::with_capacity(state.node_count),
            all_int_cache: std::sync::Arc::default(),
            edge_index_endpoints: Vec::with_capacity(edge_view.len()),
            edges: FxIndexMap::with_capacity_and_hasher(edge_view.len(), rustc_hash::FxBuildHasher),
            runtime_policy: RuntimePolicy::new(mode),
        };

        for (index, label) in labels.iter().enumerate() {
            graph.nodes.insert(label.clone(), AttrMap::new());
            graph.adj_indices.push(final_adjacency[index].clone());
        }

        for (left, right) in edge_view {
            graph.edge_index_endpoints.push((left, right));
            graph
                .edges
                .insert(Graph::canon_pair(left, right), AttrMap::new());
        }

        graph.record_decision(
            "grid_nd_bulk",
            0.0,
            false,
            vec![EvidenceTerm {
                signal: "nodes".to_owned(),
                observed_value: state.node_count.to_string(),
                log_likelihood_ratio: 0.0,
            }],
        );
        Ok(graph)
    }

    /// br-r37-c1-z2eaa: Kneser graph K(n, k) replicating NetworkX's exact
    /// construction sequence. Nodes are k-subsets of 0..n as all-int-tuple
    /// canonicals "(a, b, ...)" (br-r37-c1-y7m24). nx builds via
    /// `add_edges_from((s, t) for s in subsets for t in
    /// combinations(universe - set(s), k))` — node order is edge-DISCOVERY
    /// order (u then v per new edge) and each unordered edge is offered
    /// twice (the second add is a structural no-op). The complement
    /// `universe - set(s)` iterates ASCENDING whenever every value fits its
    /// exact CPython set slot — the Python wrapper gates this kernel on
    /// that condition, so lexicographic combinations over the sorted
    /// complement reproduce nx byte-for-byte. For `2k > n` nodes are
    /// pre-added in subset order and no edges exist.
    #[must_use]
    pub fn kneser(mode: CompatibilityMode, n: usize, k: usize) -> Self {
        fn tuple_canonical(c: &[usize]) -> String {
            let mut s = String::with_capacity(c.len() * 6 + 2);
            s.push('(');
            for (i, v) in c.iter().enumerate() {
                if i > 0 {
                    s.push_str(", ");
                }
                s.push_str(&v.to_string());
            }
            if c.len() == 1 {
                s.push(',');
            }
            s.push(')');
            s
        }
        fn lex_combinations(m: usize, k: usize) -> Vec<Vec<usize>> {
            let mut out = Vec::new();
            if k > m {
                return out;
            }
            let mut cur: Vec<usize> = (0..k).collect();
            loop {
                out.push(cur.clone());
                let mut advanced = false;
                let mut i = k;
                while i > 0 {
                    i -= 1;
                    if cur[i] != i + m - k {
                        cur[i] += 1;
                        for j in (i + 1)..k {
                            cur[j] = cur[j - 1] + 1;
                        }
                        advanced = true;
                        break;
                    }
                }
                if !advanced {
                    break;
                }
            }
            out
        }
        let subsets = lex_combinations(n, k);
        let canonicals: Vec<String> = subsets.iter().map(|c| tuple_canonical(c)).collect();
        let total = subsets.len();
        let mut graph = Self {
            mode,
            revision: u64::try_from(total).unwrap_or(u64::MAX),
            nodes: FxIndexMap::with_capacity_and_hasher(total, rustc_hash::FxBuildHasher),
            adj_indices: Vec::new(),
            all_int_cache: std::sync::Arc::default(),
            edge_index_endpoints: Vec::new(),
            edges: FxIndexMap::default(),
            runtime_policy: RuntimePolicy::new(mode),
        };
        if 2 * k > n {
            // No disjoint pairs exist — nx pre-adds all subsets as nodes.
            for canonical in &canonicals {
                graph.nodes.insert(canonical.clone(), AttrMap::new());
            }
            graph.adj_indices = vec![Vec::new(); total];
            return graph;
        }
        // Binomial table for lexicographic combination ranking.
        let mut binom = vec![vec![0usize; k + 1]; n + 1];
        for i in 0..=n {
            binom[i][0] = 1;
            for j in 1..=k.min(i) {
                binom[i][j] = if i == j {
                    1
                } else {
                    binom[i - 1][j - 1].saturating_add(binom[i - 1][j])
                };
            }
        }
        let lex_rank = |c: &[usize]| -> usize {
            let mut r = 0usize;
            let mut prev = 0usize;
            for (i, &ci) in c.iter().enumerate() {
                for j in prev..ci {
                    r = r.saturating_add(binom[n - 1 - j][k - 1 - i]);
                }
                prev = ci + 1;
            }
            r
        };
        let mut seen = HashSet::<(usize, usize)>::with_capacity(total * 2);
        // node first-touch insertion mirroring nx add_edge (u then v)
        let mut node_idx: Vec<usize> = vec![usize::MAX; total];
        let mut in_s = vec![false; n];
        let m = n - k;
        let picks = lex_combinations(m, k);
        for (s_idx, s) in subsets.iter().enumerate() {
            for &v in s {
                in_s[v] = true;
            }
            let complement: Vec<usize> = (0..n).filter(|&v| !in_s[v]).collect();
            for pick in &picks {
                let t: Vec<usize> = pick.iter().map(|&i| complement[i]).collect();
                let t_idx = lex_rank(&t);
                let pair = (s_idx.min(t_idx), s_idx.max(t_idx));
                if seen.insert(pair) {
                    for idx in [s_idx, t_idx] {
                        if node_idx[idx] == usize::MAX {
                            let entry = graph
                                .nodes
                                .insert_full(canonicals[idx].clone(), AttrMap::new())
                                .0;
                            node_idx[idx] = entry;
                            graph.adj_indices.push(Vec::new());
                        }
                    }
                    // br-r37-c1-kneserpush (cc): we are inside `if seen.insert(pair)` — a FIRST
                    // occurrence of this (s_idx,t_idx) edge — so it is provably not yet in either
                    // adjacency row. The old `!adj_indices[..].contains(..)` guards were O(degree)
                    // linear rescans always returning true here (redundant); push directly.
                    // Byte-identical (Kneser edges have no parallel edges; self-loop s==t handled
                    // by the != guard, exactly as before).
                    graph.adj_indices[node_idx[s_idx]].push(node_idx[t_idx]);
                    if node_idx[s_idx] != node_idx[t_idx] {
                        graph.adj_indices[node_idx[t_idx]].push(node_idx[s_idx]);
                    }
                    graph
                        .edge_index_endpoints
                        .push((node_idx[s_idx], node_idx[t_idx]));
                    graph.edges.insert(
                        Graph::canon_pair(node_idx[s_idx], node_idx[t_idx]),
                        AttrMap::new(),
                    );
                }
            }
            for &v in s {
                in_s[v] = false;
            }
        }
        // adj_indices maintained inline above (P2(c) slice 2).
        graph.revision = u64::try_from(graph.nodes.len() + graph.edges.len()).unwrap_or(u64::MAX);
        graph
    }

    #[must_use]
    pub fn hardened() -> Self {
        Self::new(CompatibilityMode::Hardened)
    }

    #[must_use]
    pub fn mode(&self) -> CompatibilityMode {
        self.mode
    }

    #[must_use]
    pub fn node_count(&self) -> usize {
        self.nodes.len()
    }

    #[must_use]
    pub fn edge_count(&self) -> usize {
        self.edges.len()
    }

    #[must_use]
    pub fn revision(&self) -> u64 {
        self.revision
    }

    #[must_use]
    pub fn has_node(&self, node: &str) -> bool {
        self.nodes.contains_key(node)
    }

    /// br-r37-c1-d58s8 edges-map flip: resolve a String pair to the
    /// index-canonical (min, max) key. None if either node is absent.
    #[inline]
    fn edge_pair_key(&self, left: &str, right: &str) -> Option<(usize, usize)> {
        let l = self.nodes.get_index_of(left)?;
        let r = self.nodes.get_index_of(right)?;
        Some(if l <= r { (l, r) } else { (r, l) })
    }

    #[inline]
    fn canon_pair(l: usize, r: usize) -> (usize, usize) {
        if l <= r { (l, r) } else { (r, l) }
    }

    #[must_use]
    pub fn has_edge(&self, left: &str, right: &str) -> bool {
        self.edge_pair_key(left, right)
            .is_some_and(|k| self.edges.contains_key(&k))
    }

    /// cc-hasedgeintidx: true iff the node stored at `idx` IS the integer `idx`
    /// (its canonical string parses back to `idx`). Lets a caller VERIFY, per call
    /// and with no allocation, that an exact-int node lands at its own index before
    /// probing an edge by index — so any removal / re-add / remap that shifted
    /// indices simply returns false and the caller falls back to the string path.
    /// O(1) index access + a no-alloc `str::parse`.
    #[must_use]
    pub fn node_index_matches_int(&self, idx: usize) -> bool {
        self.nodes
            .get_index(idx)
            .is_some_and(|(k, _)| k.parse::<usize>() == Ok(idx))
    }

    /// cc-hasedgeintidx: undirected edge existence by node INDEX (canonical
    /// min/max pair). Caller must have validated both indices (e.g. via
    /// `node_index_matches_int`).
    #[must_use]
    pub fn has_edge_by_indices(&self, l: usize, r: usize) -> bool {
        self.edges.contains_key(&Self::canon_pair(l, r))
    }

    #[must_use]
    pub fn nodes_ordered(&self) -> Vec<&str> {
        self.nodes.keys().map(String::as_str).collect()
    }

    #[must_use]
    pub fn get_node_index(&self, node: &str) -> Option<usize> {
        self.nodes.get_index_of(node)
    }

    #[must_use]
    pub fn get_node_name(&self, index: usize) -> Option<&str> {
        self.nodes.get_index(index).map(|(k, _)| k.as_str())
    }

    #[must_use]
    pub fn neighbors(&self, node: &str) -> Option<Vec<&str>> {
        // br-r37-c1-d58s8 P2(a): serve from the integer rows + node-name
        // table — adj_indices is order-faithful through every mutator
        // (extends push in row order; remove_node repairs in place;
        // apply_row_orders and reorder_rows_for_nx_copy_walk both
        // resync). Migrating readers off the String rows is the
        // prerequisite for dropping their eager maintenance (P2(c)).
        let idx = self.nodes.get_index_of(node)?;
        Some(
            self.adj_indices[idx]
                .iter()
                .map(|&i| {
                    self.nodes
                        .get_index(i)
                        .expect("adj_indices entries are valid node indices")
                        .0
                        .as_str()
                })
                .collect::<Vec<&str>>(),
        )
    }

    #[must_use]
    pub fn neighbors_iter(&self, node: &str) -> Option<impl Iterator<Item = &str> + '_> {
        // br-r37-c1-d58s8 P2(a): index-backed (see neighbors()).
        let idx = self.nodes.get_index_of(node)?;
        Some(self.adj_indices[idx].iter().map(move |&i| {
            self.nodes
                .get_index(i)
                .expect("adj_indices entries are valid node indices")
                .0
                .as_str()
        }))
    }

    /// Return neighbor indices for O(1) traversal. Avoids string hashing
    /// during BFS/DFS. Returns None if node index is out of bounds.
    #[must_use]
    #[inline]
    pub fn neighbors_indices(&self, node_idx: usize) -> Option<&[usize]> {
        self.adj_indices.get(node_idx).map(Vec::as_slice)
    }

    /// br-r37-c1-7dpyg: structural clone with a FRESH RuntimePolicy —
    /// `Clone` deep-copies the unbounded decision ledger (copy() measured
    /// 2.3-2.8x slower on per-edge-ctor sources with identical structure);
    /// result graphs carry the MODE, not the history.
    #[must_use]
    pub fn clone_with_fresh_policy(&self) -> Self {
        Self {
            mode: self.mode,
            revision: self.revision,
            nodes: self.nodes.clone(),
            adj_indices: self.adj_indices.clone(),
            all_int_cache: std::sync::Arc::default(),
            edge_index_endpoints: self.edge_index_endpoints.clone(),
            edges: self.edges.clone(),
            runtime_policy: RuntimePolicy::new(self.mode),
        }
    }

    /// br-r37-c1-u3qyn: restore explicit adjacency row orders (pickle
    /// round-trip). Each entry is (node, neighbor order); rows are
    /// rebuilt in the given order with any unlisted survivors appended
    /// in their current order (robust to stale state). The integer
    /// `adj_indices` mirror is rebuilt to match.
    pub fn apply_row_orders(&mut self, orders: &[(String, Vec<String>)]) {
        // br-r37-c1-d58s8 P2(c) slice 2: reorder the integer rows directly.
        for (node, order) in orders {
            let Some(idx) = self.nodes.get_index_of(node.as_str()) else {
                continue;
            };
            let row = &self.adj_indices[idx];
            let row_set: std::collections::HashSet<usize> = row.iter().copied().collect();
            let mut new_row: Vec<usize> = Vec::with_capacity(row.len());
            let mut placed: std::collections::HashSet<usize> = std::collections::HashSet::new();
            for v in order {
                if let Some(v_idx) = self.nodes.get_index_of(v.as_str())
                    && row_set.contains(&v_idx)
                    && placed.insert(v_idx)
                {
                    new_row.push(v_idx);
                }
            }
            for &v_idx in row {
                if placed.insert(v_idx) {
                    new_row.push(v_idx);
                }
            }
            self.adj_indices[idx] = new_row;
        }
    }

    /// br-r37-c1-0ek49: reorder every adjacency row into NetworkX's
    /// `Graph.copy()` walk order. nx copy rebuilds via
    /// `add_edges_from((u, v, d) for u in _adj for v in _adj[u])`, so an
    /// unordered pair enters BOTH endpoint rows at its first touch —
    /// during the earlier endpoint's row scan. Row u therefore lists
    /// neighbors at a smaller node position first (ordered by that
    /// neighbor's scan time: `(pos(v), index of u within row v)`),
    /// followed by its remaining neighbors — self-loops included — in
    /// row u's original order. Call on a fresh clone inside copy-shaped
    /// constructors; graph content is unchanged, only row order moves.
    pub fn reorder_rows_for_nx_copy_walk(&mut self) {
        // br-r37-c1-predrebuild: rebuild rows in nx's copy-walk order in O(E),
        // replacing the per-early-neighbor linear search
        // `adj_indices[v].position(|w| w == pu)` (O(E * degree) — quadratic on
        // dense graphs; it erodes dense Graph.copy() wins 9.5x->5.9x as density
        // climbs). Early neighbors of pu (v < pu) sort by
        // (pos(v), index-of-pu-within-adj[v]); walking adj in (v, adj-index)
        // order and appending v to early[pu] when pu > v yields exactly that
        // order. Late neighbors (v >= pu) keep adj[pu]'s row order. Byte-
        // identical row order — no search, no sort.
        let n = self.adj_indices.len();
        let mut early: Vec<Vec<usize>> = vec![Vec::new(); n];
        for (v, row) in self.adj_indices.iter().enumerate() {
            for &pu in row {
                if pu > v {
                    early[pu].push(v);
                }
            }
        }
        let mut new_rows: Vec<Vec<usize>> = Vec::with_capacity(n);
        for (pu, row) in self.adj_indices.iter().enumerate() {
            let mut new_row = std::mem::take(&mut early[pu]);
            new_row.reserve(row.len());
            for &v in row {
                if v >= pu {
                    new_row.push(v);
                }
            }
            new_rows.push(new_row);
        }
        self.adj_indices = new_rows;
    }

    pub fn edges_storage_order_index_iter(
        &self,
    ) -> impl Iterator<Item = (usize, usize, &AttrMap)> + '_ {
        self.edge_index_endpoints
            .iter()
            .copied()
            .zip(self.edges.values())
            .map(|((left, right), attrs)| (left, right, attrs))
    }

    #[must_use]
    pub fn neighbor_count(&self, node: &str) -> usize {
        // br-r37-c1-d58s8 P2(a): index-backed.
        self.nodes
            .get_index_of(node)
            .map_or(0, |idx| self.adj_indices[idx].len())
    }

    /// Return the degree of a node.
    /// Self-loops contribute 2 to the degree (NetworkX convention).
    #[must_use]
    pub fn degree(&self, node: &str) -> usize {
        let count = self.neighbor_count(node);
        // If node has a self-loop, add 1 extra (self-loop contributes 2 total)
        if self.has_edge(node, node) {
            count + 1
        } else {
            count
        }
    }

    /// br-r37-c1-degidx: degree by node INDEX — O(1), zero String
    /// hashing (the &str path costs 2 hashes/node: neighbor_count's
    /// get_index_of + the self-loop has_edge). Used by the DegreeView
    /// iterator which already walks nodes in index order.
    #[must_use]
    pub fn degree_by_index(&self, idx: usize) -> usize {
        // br-r37-c1-degselfloopidx (cc): the self-loop check was `adj_indices[idx].contains(&idx)`
        // — an O(degree) linear rescan of the adjacency row (which for the common no-self-loop node
        // scans the WHOLE row to return false), making this hot per-node accessor O(degree) despite
        // the "O(1)" claim. `has_edge_by_indices(idx, idx)` = `self.edges.contains_key(canon(idx,idx))`
        // is an O(1) HashMap probe deciding the SAME fact (a self-loop edge exists IFF idx is in its
        // own adjacency row — the maintained adj_indices<=>self.edges invariant). Byte-identical.
        let mut count = self.adj_indices[idx].len();
        if self.has_edge_by_indices(idx, idx) {
            count += 1; // self-loop contributes 2 to total degree
        }
        count
    }

    #[must_use]
    pub fn node_attrs(&self, node: &str) -> Option<&AttrMap> {
        self.nodes.get(node)
    }

    #[must_use]
    pub fn edge_attrs(&self, left: &str, right: &str) -> Option<&AttrMap> {
        self.edges.get(&self.edge_pair_key(left, right)?)
    }

    /// br-r37-c1-d58s8: index-keyed attr access — a DIRECT map get for
    /// callers that already hold node indices (kernels, CSR weight
    /// builders, compose walks). Zero node-map probes.
    #[must_use]
    #[inline]
    pub fn edge_attrs_by_indices(&self, left_idx: usize, right_idx: usize) -> Option<&AttrMap> {
        self.edges.get(&Self::canon_pair(left_idx, right_idx))
    }

    /// br-r37-c1-hasattrlazyfix: does ANY edge carry the attribute `key` in the
    /// authoritative Rust storage? Unlike the `edge_py_attrs` Python mirror (which is
    /// LAZILY materialized — a batch-built graph leaves it empty), this scans the inner
    /// `edges` AttrMaps directly (no node-name resolution, no allocation), so a
    /// freshly-constructed weighted graph reports True. ~O(E) BTreeMap key checks.
    #[must_use]
    pub fn any_edge_has_attr(&self, key: &str) -> bool {
        self.edges.values().any(|attrs| attrs.contains_key(key))
    }

    /// True if EVERY inner edge attr value is a faithful scalar (Int/Float/Bool)
    /// — a String/Map value is a coerced non-scalar (repr/JSON) or genuine str,
    /// ambiguous for lossless cloning. Direct no-alloc scan over the edge store
    /// values (contrast `edges_ordered_borrowed`, which builds an O(E) dedup
    /// HashMap). Used by the compose store-read gate.
    #[must_use]
    pub fn all_edge_attr_values_scalar(&self) -> bool {
        self.edges.values().all(|attrs| {
            attrs.values().all(|v| {
                matches!(
                    v,
                    fnx_runtime::CgseValue::Int(_)
                        | fnx_runtime::CgseValue::Float(_)
                        | fnx_runtime::CgseValue::Bool(_)
                )
            })
        })
    }

    /// br-r37-c1-hasanyattrlazyfix: does ANY node carry a Python-visible attr, per the
    /// authoritative inner storage (not the lazy `node_py_attrs` mirror)?
    #[must_use]
    pub fn any_node_has_attrs(&self) -> bool {
        self.nodes.values().any(|attrs| !attrs.is_empty())
    }

    /// br-r37-c1-hasanyattrlazyfix: does ANY edge carry a Python-visible attr, per the
    /// authoritative inner storage (not the lazy `edge_py_attrs` mirror)?
    #[must_use]
    pub fn any_edge_has_attrs(&self) -> bool {
        self.edges.values().any(|attrs| !attrs.is_empty())
    }

    #[must_use]
    pub fn nodes_are_contiguous_int_prefix(&self) -> bool {
        self.nodes
            .keys()
            .enumerate()
            .all(|(index, key)| Self::decimal_key_matches_index(key, index))
    }

    fn decimal_key_matches_index(key: &str, index: usize) -> bool {
        let bytes = key.as_bytes();
        if bytes.is_empty() || (bytes.len() > 1 && bytes[0] == b'0') {
            return false;
        }

        let mut parsed = 0usize;
        for &byte in bytes {
            if !byte.is_ascii_digit() {
                return false;
            }
            let digit = usize::from(byte - b'0');
            let Some(next) = parsed
                .checked_mul(10)
                .and_then(|value| value.checked_add(digit))
            else {
                return false;
            };
            parsed = next;
        }
        parsed == index
    }

    #[must_use]
    pub fn evidence_ledger(&self) -> &EvidenceLedger {
        self.runtime_policy.decision_log()
    }

    #[must_use]
    pub fn runtime_policy(&self) -> &RuntimePolicy {
        &self.runtime_policy
    }

    pub fn set_runtime_policy(&mut self, runtime_policy: RuntimePolicy) {
        self.mode = runtime_policy.mode();
        self.runtime_policy = runtime_policy;
    }

    /// Type identity: always `false` for undirected Graph.
    #[must_use]
    pub fn is_directed(&self) -> bool {
        false
    }

    /// Type identity: always `false` for Graph (not a multigraph).
    #[must_use]
    pub fn is_multigraph(&self) -> bool {
        false
    }

    pub fn add_node(&mut self, node: impl Into<String>) -> bool {
        self.add_node_with_attrs(node, AttrMap::new())
    }

    pub fn add_node_with_attrs(&mut self, node: impl Into<String>, attrs: AttrMap) -> bool {
        let node = node.into();
        let existed = self.nodes.contains_key(&node);
        let mut changed = !existed;
        let attrs_count = {
            let bucket = self.nodes.entry(node.clone()).or_default();
            if !attrs.is_empty()
                && attrs
                    .iter()
                    .any(|(key, value)| bucket.get(key) != Some(value))
            {
                changed = true;
            }
            bucket.extend(attrs);
            bucket.len()
        };
        // Extend integer adjacency list for new nodes
        if !existed {
            self.adj_indices.push(Vec::new());
        }
        if changed {
            self.revision = self.revision.saturating_add(1);
        }
        self.record_decision(
            "add_node",
            0.0,
            false,
            vec![
                EvidenceTerm {
                    signal: "node_preexisting".to_owned(),
                    observed_value: existed.to_string(),
                    log_likelihood_ratio: -3.0,
                },
                EvidenceTerm {
                    signal: "attrs_count".to_owned(),
                    observed_value: attrs_count.to_string(),
                    log_likelihood_ratio: -1.0,
                },
            ],
        );
        changed
    }

    /// Bulk node insertion for generated/batched construction paths where
    /// per-node compatibility evidence would be pure constant-factor overhead.
    #[must_use]
    pub fn extend_nodes_unrecorded<I, N>(&mut self, nodes: I) -> usize
    where
        I: IntoIterator<Item = N>,
        N: Into<String>,
    {
        let iterator = nodes.into_iter();
        let (lower_bound, _) = iterator.size_hint();
        self.nodes.reserve(lower_bound);
        self.adj_indices.reserve(lower_bound);

        let mut inserted = 0usize;
        for node in iterator {
            let node = node.into();
            if self.nodes.contains_key(&node) {
                continue;
            }
            self.nodes.insert(node.clone(), AttrMap::new());
            self.adj_indices.push(Vec::new());
            inserted += 1;
        }
        if inserted > 0 {
            self.revision = self
                .revision
                .saturating_add(u64::try_from(inserted).unwrap_or(u64::MAX));
            self.record_decision(
                "extend_nodes_unrecorded",
                0.0,
                false,
                vec![EvidenceTerm {
                    signal: "batch_node_count".to_owned(),
                    observed_value: inserted.to_string(),
                    log_likelihood_ratio: -1.0,
                }],
            );
        }
        inserted
    }

    /// br-r37-c1-l5ve7: bulk node insert WITH attrs, one ledger record —
    /// mirror of DiGraph::extend_nodes_with_attrs_unrecorded. Existing
    /// nodes merge attrs (extend), matching add_node_with_attrs.
    pub fn extend_nodes_with_attrs_unrecorded<I>(&mut self, nodes: I) -> usize
    where
        I: IntoIterator<Item = (String, AttrMap)>,
    {
        let iterator = nodes.into_iter();
        let (lower_bound, _) = iterator.size_hint();
        self.nodes.reserve(lower_bound);
        self.adj_indices.reserve(lower_bound);

        let mut inserted = 0usize;
        for (node, attrs) in iterator {
            if let Some(existing) = self.nodes.get_mut(&node) {
                existing.extend(attrs);
                continue;
            }
            self.nodes.insert(node.clone(), attrs);
            self.adj_indices.push(Vec::new());
            inserted += 1;
        }
        if inserted > 0 {
            self.revision = self
                .revision
                .saturating_add(u64::try_from(inserted).unwrap_or(u64::MAX));
            self.record_decision(
                "extend_nodes_with_attrs_unrecorded",
                0.0,
                false,
                vec![EvidenceTerm {
                    signal: "batch_node_count".to_owned(),
                    observed_value: inserted.to_string(),
                    log_likelihood_ratio: -1.0,
                }],
            );
        }
        inserted
    }

    pub fn apply_node_defaults(&mut self, defaults: &AttrMap) -> bool {
        if defaults.is_empty() {
            return false;
        }
        let mut inserted = 0usize;
        for attrs in self.nodes.values_mut() {
            for (key, value) in defaults {
                if !attrs.contains_key(key) {
                    attrs.insert(key.clone(), value.clone());
                    inserted += 1;
                }
            }
        }
        if inserted > 0 {
            self.revision = self.revision.saturating_add(1);
            self.record_decision(
                "apply_node_defaults",
                0.0,
                false,
                vec![EvidenceTerm {
                    signal: "defaults_applied".to_owned(),
                    observed_value: inserted.to_string(),
                    log_likelihood_ratio: 0.0,
                }],
            );
            return true;
        }
        false
    }

    pub fn add_edge(
        &mut self,
        left: impl Into<String>,
        right: impl Into<String>,
    ) -> Result<(), GraphError> {
        self.add_edge_with_attrs(left, right, AttrMap::new())
    }

    /// Bulk-add a sequence of attribute-free edges. Bypasses the
    /// per-edge `runtime_policy.record_decision` call that
    /// [`add_edge_with_attrs`] makes. Instead, emit one summary record
    /// for the whole batch.
    ///
    /// Intended for fnx-internal callers that build a fresh graph
    /// from a known-good edge list (e.g., `complement`,
    /// `transitive_closure`, etc.) where the per-edge
    /// incompatibility-probability accounting would just add
    /// constant-factor overhead and is uninteresting for the policy
    /// log.
    ///
    /// Nodes referenced by edges are auto-created if absent
    /// (matching `add_edge` semantics). br-r37-c1-4jd8m.
    #[must_use]
    pub fn extend_edges_unrecorded<I, L, R>(&mut self, edges: I) -> usize
    where
        I: IntoIterator<Item = (L, R)>,
        L: Into<String>,
        R: Into<String>,
    {
        let iterator = edges.into_iter();
        let (lower_bound, _) = iterator.size_hint();
        self.nodes.reserve(lower_bound);
        self.adj_indices.reserve(lower_bound);
        self.edges.reserve(lower_bound);
        self.edge_index_endpoints.reserve(lower_bound);

        let mut inserted = 0usize;
        let mut nodes_added = false;
        for (left, right) in iterator {
            let left = left.into();
            let right = right.into();
            let left_idx = match self.nodes.get_index_of(&left) {
                Some(index) => index,
                None => {
                    let index = self.nodes.len();
                    self.nodes.insert(left.clone(), AttrMap::new());
                    self.adj_indices.push(Vec::new());
                    nodes_added = true;
                    index
                }
            };
            let right_idx = if left == right {
                left_idx
            } else {
                match self.nodes.get_index_of(&right) {
                    Some(index) => index,
                    None => {
                        let index = self.nodes.len();
                        self.nodes.insert(right.clone(), AttrMap::new());
                        self.adj_indices.push(Vec::new());
                        nodes_added = true;
                        index
                    }
                }
            };
            let edge_key = Self::canon_pair(left_idx, right_idx);
            if self.edges.contains_key(&edge_key) {
                continue;
            }
            if left <= right {
                self.edge_index_endpoints.push((left_idx, right_idx));
            } else {
                self.edge_index_endpoints.push((right_idx, left_idx));
            }
            self.edges.insert(edge_key, AttrMap::new());

            self.adj_indices[left_idx].push(right_idx);
            if left_idx != right_idx {
                self.adj_indices[right_idx].push(left_idx);
            }
            inserted += 1;
        }
        self.record_bulk_edge_summary(inserted, nodes_added);
        inserted
    }

    /// Bulk-add attribute-free edges whose endpoints have already been
    /// resolved to existing node indices. This is the index-space sibling of
    /// [`extend_edges_unrecorded`]: it preserves duplicate handling, adjacency
    /// row order, edge storage order, and string-canonical endpoint orientation
    /// without per-edge node-name allocation or map lookup.
    #[must_use]
    pub fn extend_existing_index_edges_unrecorded<I>(&mut self, edges: I) -> usize
    where
        I: IntoIterator<Item = (usize, usize)>,
    {
        let iterator = edges.into_iter();
        let (lower_bound, _) = iterator.size_hint();
        self.edges.reserve(lower_bound);
        self.edge_index_endpoints.reserve(lower_bound);

        let mut inserted = 0usize;
        for (left_idx, right_idx) in iterator {
            debug_assert!(left_idx < self.nodes.len());
            debug_assert!(right_idx < self.nodes.len());

            let edge_key = Self::canon_pair(left_idx, right_idx);
            if self.edges.contains_key(&edge_key) {
                continue;
            }

            let left_name = self
                .nodes
                .get_index(left_idx)
                .expect("validated left node index")
                .0
                .as_str();
            let right_name = self
                .nodes
                .get_index(right_idx)
                .expect("validated right node index")
                .0
                .as_str();
            if left_name <= right_name {
                self.edge_index_endpoints.push((left_idx, right_idx));
            } else {
                self.edge_index_endpoints.push((right_idx, left_idx));
            }
            self.edges.insert(edge_key, AttrMap::new());

            self.adj_indices[left_idx].push(right_idx);
            if left_idx != right_idx {
                self.adj_indices[right_idx].push(left_idx);
            }
            inserted += 1;
        }
        self.record_bulk_edge_summary(inserted, false);
        inserted
    }

    /// br-r37-c1-dodattrbatch: bulk-add ATTRIBUTED edges by EXISTING node index
    /// — the attributed sibling of [`extend_existing_index_edges_unrecorded`].
    /// All endpoints MUST already exist (callers gate on a contiguous-int node
    /// prefix). A new edge takes the given AttrMap; a duplicate edge MERGES
    /// (last-writer-wins per key) exactly like `add_edge_with_attrs`. Replaces
    /// the per-edge ledger with one batch summary; no String hashing for the
    /// endpoints (they arrive as integer indices).
    pub fn extend_existing_index_edges_with_attrs_unrecorded<I>(&mut self, edges: I) -> usize
    where
        I: IntoIterator<Item = (usize, usize, AttrMap)>,
    {
        let iterator = edges.into_iter();
        let (lower_bound, _) = iterator.size_hint();
        self.edges.reserve(lower_bound);
        self.edge_index_endpoints.reserve(lower_bound);

        let mut inserted = 0usize;
        for (left_idx, right_idx, attrs) in iterator {
            debug_assert!(left_idx < self.nodes.len());
            debug_assert!(right_idx < self.nodes.len());

            let edge_key = Self::canon_pair(left_idx, right_idx);
            if let Some(existing) = self.edges.get_mut(&edge_key) {
                // Duplicate edge within the batch: merge attrs (last wins).
                for (key, value) in attrs {
                    existing.insert(key, value);
                }
                continue;
            }

            let left_name = self
                .nodes
                .get_index(left_idx)
                .expect("validated left node index")
                .0
                .as_str();
            let right_name = self
                .nodes
                .get_index(right_idx)
                .expect("validated right node index")
                .0
                .as_str();
            if left_name <= right_name {
                self.edge_index_endpoints.push((left_idx, right_idx));
            } else {
                self.edge_index_endpoints.push((right_idx, left_idx));
            }
            self.edges.insert(edge_key, attrs);

            self.adj_indices[left_idx].push(right_idx);
            if left_idx != right_idx {
                self.adj_indices[right_idx].push(left_idx);
            }
            inserted += 1;
        }
        self.record_bulk_edge_summary(inserted, false);
        inserted
    }

    /// br-r37-c1-pr8q6: bulk-add ATTRIBUTED edges without per-edge ledger
    /// records — the attributed sibling of [`extend_edges_unrecorded`].
    ///
    /// Semantics match a sequence of `add_edge_with_attrs` calls exactly:
    /// nodes auto-created in first-appearance order, duplicate edges MERGE
    /// their attrs into the existing map (`extend`), adjacency /
    /// `adj_indices` / `edge_index_endpoints` maintained identically. Only
    /// the per-edge `record_decision` push (timestamp + String allocs per
    /// edge, the dominant cost of attributed bulk construction) is replaced
    /// by one batch summary record.
    ///
    /// Callers MUST pre-screen attr keys starting with
    /// `"__fnx_incompatible"` and route those edges through
    /// `add_edge_with_attrs`, which owns the FailClosed contract for them.
    pub fn extend_edges_with_attrs_unrecorded<I>(&mut self, edges: I) -> usize
    where
        I: IntoIterator<Item = (String, String, AttrMap)>,
    {
        let iterator = edges.into_iter();
        let (lower_bound, _) = iterator.size_hint();
        self.nodes.reserve(lower_bound);
        self.adj_indices.reserve(lower_bound);
        self.edges.reserve(lower_bound);
        self.edge_index_endpoints.reserve(lower_bound);

        let mut inserted = 0usize;
        let mut nodes_added = false;
        let mut merged_changed = false;
        for (left, right, attrs) in iterator {
            let left_idx = match self.nodes.get_index_of(&left) {
                Some(index) => index,
                None => {
                    let index = self.nodes.len();
                    self.nodes.insert(left.clone(), AttrMap::new());
                    self.adj_indices.push(Vec::new());
                    nodes_added = true;
                    index
                }
            };
            let right_idx = if left == right {
                left_idx
            } else {
                match self.nodes.get_index_of(&right) {
                    Some(index) => index,
                    None => {
                        let index = self.nodes.len();
                        self.nodes.insert(right.clone(), AttrMap::new());
                        self.adj_indices.push(Vec::new());
                        nodes_added = true;
                        index
                    }
                }
            };
            let edge_key = Self::canon_pair(left_idx, right_idx);
            if let Some(existing) = self.edges.get_mut(&edge_key) {
                // Duplicate edge (pre-existing or earlier in this batch):
                // merge attrs, matching add_edge_with_attrs' `extend`.
                if !attrs.is_empty()
                    && attrs
                        .iter()
                        .any(|(key, value)| existing.get(key) != Some(value))
                {
                    merged_changed = true;
                }
                existing.extend(attrs);
                continue;
            }
            if left <= right {
                self.edge_index_endpoints.push((left_idx, right_idx));
            } else {
                self.edge_index_endpoints.push((right_idx, left_idx));
            }
            self.edges.insert(edge_key, attrs);

            self.adj_indices[left_idx].push(right_idx);
            if left_idx != right_idx {
                self.adj_indices[right_idx].push(left_idx);
            }
            inserted += 1;
        }
        if merged_changed {
            // Attr-merge on an existing edge mutates observable state even
            // when no new edge was inserted — bump revision so caches
            // invalidate (over-invalidation is safe; staleness is not).
            self.revision = self.revision.saturating_add(1);
        }
        self.record_bulk_edge_summary(inserted, nodes_added || merged_changed);
        inserted
    }

    /// Bulk-add attributed undirected edges into a fresh graph when the caller
    /// has already assigned NetworkX-compatible node indices in first-seen
    /// order.
    ///
    /// This is the fresh/indexed sibling of
    /// [`extend_edges_with_attrs_unrecorded`]. It preserves duplicate
    /// insert-or-merge semantics, adjacency row order, self-loop handling, and
    /// the public `edges()` orientation rule used by the string-key path.
    #[must_use]
    pub fn extend_fresh_index_edges_with_attrs_unrecorded<I, N>(
        &mut self,
        nodes: N,
        edges: I,
    ) -> usize
    where
        I: IntoIterator<Item = (usize, usize, AttrMap)>,
        N: IntoIterator<Item = String>,
    {
        if !self.nodes.is_empty()
            || !self.adj_indices.is_empty()
            || !self.edges.is_empty()
            || !self.edge_index_endpoints.is_empty()
        {
            return 0;
        }

        let node_labels: Vec<String> = nodes.into_iter().collect();
        self.nodes.reserve(node_labels.len());
        self.adj_indices = vec![Vec::new(); node_labels.len()];
        for node in &node_labels {
            self.nodes.insert(node.clone(), AttrMap::new());
        }

        let iterator = edges.into_iter();
        let (lower_bound, _) = iterator.size_hint();
        self.edges.reserve(lower_bound);
        self.edge_index_endpoints.reserve(lower_bound);

        let node_count = node_labels.len();
        let mut inserted = 0usize;
        let mut merged_changed = false;
        for (left_idx, right_idx, attrs) in iterator {
            if left_idx >= node_count || right_idx >= node_count {
                continue;
            }

            let edge_key = Self::canon_pair(left_idx, right_idx);
            if let Some(existing) = self.edges.get_mut(&edge_key) {
                if !attrs.is_empty()
                    && attrs
                        .iter()
                        .any(|(key, value)| existing.get(key) != Some(value))
                {
                    merged_changed = true;
                }
                existing.extend(attrs);
                continue;
            }

            if node_labels[left_idx] <= node_labels[right_idx] {
                self.edge_index_endpoints.push((left_idx, right_idx));
            } else {
                self.edge_index_endpoints.push((right_idx, left_idx));
            }
            self.edges.insert(edge_key, attrs);
            self.adj_indices[left_idx].push(right_idx);
            if left_idx != right_idx {
                self.adj_indices[right_idx].push(left_idx);
            }
            inserted += 1;
        }

        self.record_bulk_edge_summary(inserted, node_count > 0 || merged_changed);
        inserted
    }

    fn record_bulk_edge_summary(&mut self, inserted: usize, nodes_added: bool) {
        if inserted == 0 && !nodes_added {
            return;
        }
        self.revision = self
            .revision
            .saturating_add(u64::try_from(inserted).unwrap_or(u64::MAX));
        // One summary record covers the whole batch and keeps the
        // policy ledger non-empty so existing diagnostics still
        // see the operation.
        self.record_decision(
            "extend_edges_unrecorded",
            0.0,
            false,
            vec![EvidenceTerm {
                signal: "batch_edge_count".to_owned(),
                observed_value: inserted.to_string(),
                log_likelihood_ratio: -1.0,
            }],
        );
    }

    pub fn add_edge_with_attrs(
        &mut self,
        left: impl Into<String>,
        right: impl Into<String>,
        attrs: AttrMap,
    ) -> Result<(), GraphError> {
        let left = left.into();
        let right = right.into();

        let unknown_feature = attrs
            .keys()
            .any(|key| key.starts_with("__fnx_incompatible"));
        let incompatibility_probability = if unknown_feature {
            1.0
        } else if left == right {
            0.22
        } else {
            0.08
        };

        let action = self.record_decision(
            "add_edge",
            incompatibility_probability,
            unknown_feature,
            vec![EvidenceTerm {
                signal: "unknown_incompatible_feature".to_owned(),
                observed_value: unknown_feature.to_string(),
                log_likelihood_ratio: 12.0,
            }],
        );

        if action == DecisionAction::FailClosed || action == DecisionAction::FullValidate {
            return Err(GraphError::FailClosed {
                operation: "add_edge",
                reason: "incompatible edge metadata".to_owned(),
            });
        }

        let mut left_autocreated = false;
        if !self.nodes.contains_key(&left) {
            let _ = self.add_node(left.clone());
            left_autocreated = true;
        }
        let mut right_autocreated = false;
        if left == right {
            right_autocreated = left_autocreated;
        } else if !self.nodes.contains_key(&right) {
            let _ = self.add_node(right.clone());
            right_autocreated = true;
        }

        let left_key_idx = self.nodes.get_index_of(&left).expect("autocreated above");
        let right_key_idx = self.nodes.get_index_of(&right).expect("autocreated above");
        let edge_key = Self::canon_pair(left_key_idx, right_key_idx);
        let self_loop = left == right;
        let new_edge = !self.edges.contains_key(&edge_key);
        let mut changed = new_edge;
        let edge_attr_count = {
            let edge_attrs = self.edges.entry(edge_key).or_default();
            if !attrs.is_empty()
                && attrs
                    .iter()
                    .any(|(key, value)| edge_attrs.get(key) != Some(value))
            {
                changed = true;
            }
            edge_attrs.extend(attrs);
            edge_attrs.len()
        };

        // Update integer adjacency (only for new edges, avoid duplicates)
        if changed {
            if let (Some(left_idx), Some(right_idx)) = (
                self.nodes.get_index_of(&left),
                self.nodes.get_index_of(&right),
            ) {
                if new_edge {
                    if left <= right {
                        self.edge_index_endpoints.push((left_idx, right_idx));
                    } else {
                        self.edge_index_endpoints.push((right_idx, left_idx));
                    }
                    // br-r37-c1-addedgenewedge (cc): adj_indices membership is EXACTLY edge
                    // existence, which `new_edge` (= !self.edges.contains_key(edge_key)) already
                    // decided in O(1). The old `!adj_indices[left_idx].contains(&right_idx)` guards
                    // were an O(degree) linear rescan of the adjacency row computing the SAME
                    // answer — O(n²) to build a star/hub via add_edge. Push only when new_edge
                    // (byte-identical: existing edge ⇒ new_edge false ⇒ both endpoints already in
                    // adj_indices ⇒ old guards were false too; self-loop ⇒ left_idx==right_idx ⇒
                    // single push in both).
                    self.adj_indices[left_idx].push(right_idx);
                    if left_idx != right_idx {
                        self.adj_indices[right_idx].push(left_idx);
                    }
                }
            }
            self.revision = self.revision.saturating_add(1);
        }

        self.record_decision(
            "add_edge",
            incompatibility_probability,
            unknown_feature,
            vec![
                EvidenceTerm {
                    signal: "self_loop".to_owned(),
                    observed_value: self_loop.to_string(),
                    log_likelihood_ratio: -0.5,
                },
                EvidenceTerm {
                    signal: "edge_attr_count".to_owned(),
                    observed_value: edge_attr_count.to_string(),
                    log_likelihood_ratio: -2.0,
                },
                EvidenceTerm {
                    signal: "left_autocreated".to_owned(),
                    observed_value: left_autocreated.to_string(),
                    log_likelihood_ratio: -1.25,
                },
                EvidenceTerm {
                    signal: "right_autocreated".to_owned(),
                    observed_value: right_autocreated.to_string(),
                    log_likelihood_ratio: -1.25,
                },
            ],
        );

        Ok(())
    }

    pub fn apply_edge_defaults(&mut self, defaults: &AttrMap) -> bool {
        if defaults.is_empty() {
            return false;
        }
        let mut inserted = 0usize;
        for attrs in self.edges.values_mut() {
            for (key, value) in defaults {
                if !attrs.contains_key(key) {
                    attrs.insert(key.clone(), value.clone());
                    inserted += 1;
                }
            }
        }
        if inserted > 0 {
            self.revision = self.revision.saturating_add(1);
            self.record_decision(
                "apply_edge_defaults",
                0.0,
                false,
                vec![EvidenceTerm {
                    signal: "defaults_applied".to_owned(),
                    observed_value: inserted.to_string(),
                    log_likelihood_ratio: 0.0,
                }],
            );
            return true;
        }
        false
    }

    /// br-r37-c1-sjf4t: overwrite the attribute map for an existing edge,
    /// matching post-creation Python-side mutations. Unlike
    /// `add_edge_with_attrs` which extends, this replaces. Returns
    /// `true` if the edge existed and was updated, `false` otherwise.
    pub fn replace_edge_attrs(&mut self, left: &str, right: &str, attrs: AttrMap) -> bool {
        let Some(edge_key) = self.edge_pair_key(left, right) else {
            return false;
        };
        if let Some(slot) = self.edges.get_mut(&edge_key) {
            if *slot != attrs {
                *slot = attrs;
                self.revision = self.revision.saturating_add(1);
            }
            true
        } else {
            false
        }
    }

    /// br-r37-c1-sjf4t: overwrite the attribute map for an existing node.
    pub fn replace_node_attrs(&mut self, node: &str, attrs: AttrMap) -> bool {
        if let Some(slot) = self.nodes.get_mut(node) {
            if *slot != attrs {
                *slot = attrs;
                self.revision = self.revision.saturating_add(1);
            }
            true
        } else {
            false
        }
    }

    pub fn remove_edge(&mut self, left: &str, right: &str) -> bool {
        // `shift_remove_full` returns the edge's index in `self.edges` *before*
        // removal so we can keep `edge_index_endpoints` (maintained strictly
        // parallel to `self.edges`: one entry per edge, same order — see
        // `add_edge_with_attrs` / `extend_edges_unrecorded`) in sync by dropping
        // the single corresponding entry, instead of the O(|E|) hashing
        // `rebuild_edge_index_endpoints()`. Bit-identical result (the parallel
        // vector ends up exactly as a full rebuild would leave it), but turns a
        // remove-heavy build like watts_strogatz from O(|E|^2) into O(|E|·shift).
        let Some(pair) = self.edge_pair_key(left, right) else {
            return false;
        };
        // br-r37-c1-vbwpl: swap_remove (O(1)) instead of shift_remove
        // (O(|E|)) — turns remove-heavy algos (double_edge_swap 188x,
        // watts) from O(k*|E|) into O(k). The edge's slot is filled by
        // the LAST edge; edge_index_endpoints does the SAME swap_remove
        // so the two vectors stay element-parallel. Output is unaffected:
        // edges_ordered() and all user-visible iteration order off
        // ADJACENCY (adj_indices), not edges-map storage order; the only
        // storage-order consumer is the COO matrix builder, where triple
        // order is irrelevant (scipy CSR canonicalises). Edge keys are
        // (node_idx,node_idx) so no key rekey is needed on edge removal.
        let removed = self.edges.swap_remove_full(&pair);
        if let Some((edge_pos, _, _)) = removed {
            // br-r37-c1-d58s8 P2(c) slice 2: integer rows are the single
            // row store — drop the pair entries there.
            if let (Some(left_idx), Some(right_idx)) = (
                self.nodes.get_index_of(left),
                self.nodes.get_index_of(right),
            ) {
                self.adj_indices[left_idx].retain(|&i| i != right_idx);
                if left_idx != right_idx {
                    self.adj_indices[right_idx].retain(|&i| i != left_idx);
                }
            }
            self.edge_index_endpoints.swap_remove(edge_pos);
            self.revision = self.revision.saturating_add(1);
            true
        } else {
            false
        }
    }

    pub fn remove_node(&mut self, node: &str) -> bool {
        let Some(idx) = self.nodes.get_index_of(node) else {
            return false;
        };

        // br-r37-c1-rmnode: incremental index maintenance. The previous version
        // called `rebuild_adj_indices()` + `rebuild_edge_index_endpoints()` —
        // two O(|E|) passes that do a `get_index_of` HashMap lookup for EVERY
        // neighbour of every node and every edge — on EVERY removal, so
        // `remove_node` was O(|V|+|E|)-with-hashing and `remove_nodes_from` was
        // O(k*(|V|+|E|)) (~50x slower than nx). Instead: drop all incident edges
        // in a single O(|E|) retain pass, then repair the integer caches in
        // place (drop dangling refs to the removed index, decrement indices that
        // shifted down) — no hashing, no full rebuild.

        // br-cc-rmnode-fuse: the previous version made ~9 separate O(|E|)
        // passes over the edge storage per removal (keep-mask, edges.retain,
        // endpoints.retain, adj retain, adj decrement, endpoint decrement,
        // full edges rekey). Since the removal ALWAYS rebuilds the edges map
        // (indices > idx shift down when `nodes.shift_remove` renumbers),
        // FUSE incident-drop + index-decrement + rekey into ONE order-
        // preserving rebuild pass, and FUSE the adjacency retain+decrement
        // into one pass per row. Survivor order is untouched (both the old
        // retain and the old rekey preserved insertion order), so
        // `edges_ordered()` — the only observed edge order, walked from the
        // adjacency rows — is byte-identical. Cuts the per-removal edge work
        // from ~9|E| to ~3|E| (the O(|V|+|E|) renumber floor stays; killing
        // it needs stable node ids, see docs/NEGATIVE_EVIDENCE.md).

        // 1. Drop the node's own adjacency-index vec (outer Vec shifts to stay
        //    aligned with `nodes` after the shift_remove below).
        self.adj_indices.remove(idx);
        // 2. Remove from the node map (renumbers positions > idx down by 1).
        self.nodes.shift_remove(node);
        // 3. Adjacency repair — ONE pass per row: drop any remaining reference
        //    to the removed index and decrement every index that shifted down.
        for nbrs in &mut self.adj_indices {
            let mut w = 0usize;
            for read in 0..nbrs.len() {
                let e = nbrs[read];
                if e == idx {
                    continue;
                }
                nbrs[w] = if e > idx { e - 1 } else { e };
                w += 1;
            }
            nbrs.truncate(w);
        }
        // 4. Edge storage — ONE fused pass over the element-parallel
        //    (edges, edge_index_endpoints): skip incident edges (either
        //    endpoint index == idx), decrement shifted indices, and rebuild
        //    both containers in the SAME survivor order they had before.
        let old_edges = std::mem::take(&mut self.edges);
        let old_endpoints = std::mem::take(&mut self.edge_index_endpoints);
        let mut new_edges =
            FxIndexMap::with_capacity_and_hasher(old_edges.len(), rustc_hash::FxBuildHasher);
        let mut new_endpoints = Vec::with_capacity(old_endpoints.len());
        for (((l, r), attrs), (le, re)) in old_edges.into_iter().zip(old_endpoints) {
            if le == idx || re == idx {
                continue;
            }
            new_edges.insert(
                (
                    if l > idx { l - 1 } else { l },
                    if r > idx { r - 1 } else { r },
                ),
                attrs,
            );
            new_endpoints.push((
                if le > idx { le - 1 } else { le },
                if re > idx { re - 1 } else { re },
            ));
        }
        self.edges = new_edges;
        self.edge_index_endpoints = new_endpoints;

        self.revision = self.revision.saturating_add(1);
        true
    }

    pub fn remove_nodes_from<'a, I>(&mut self, nodes: I) -> (usize, usize)
    where
        I: IntoIterator<Item = &'a str>,
    {
        let remove_set: HashSet<&str> = nodes
            .into_iter()
            .filter(|node| self.nodes.contains_key(*node))
            .collect();
        if remove_set.is_empty() {
            return (0, 0);
        }

        let old_node_count = self.nodes.len();
        let old_edge_count = self.edges.len();

        // br-r37-c1-d58s8 P2(c) slice 1: integer-side removal. Compute the
        // removed-index mask + old->new remap BEFORE any map shifts, then
        // filter edges via endpoint indices (no String hashing) and
        // rebuild adj_indices through the remap from the OLD integer rows
        // (the old rebuild_adj_indices re-hashed every neighbor String).
        let removed_mask: Vec<bool> = self
            .nodes
            .keys()
            .map(|k| remove_set.contains(k.as_str()))
            .collect();
        let mut remap: Vec<usize> = Vec::with_capacity(old_node_count);
        let mut next = 0usize;
        for &gone in &removed_mask {
            remap.push(next);
            if !gone {
                next += 1;
            }
        }
        let keep_edges: Vec<bool> = self
            .edge_index_endpoints
            .iter()
            .map(|&(l, r)| !removed_mask[l] && !removed_mask[r])
            .collect();

        self.nodes
            .retain(|node, _| !remove_set.contains(node.as_str()));
        let mut i = 0usize;
        self.edges.retain(|_, _| {
            let k = keep_edges[i];
            i += 1;
            k
        });
        let mut j = 0usize;
        self.edge_index_endpoints.retain(|_| {
            let k = keep_edges[j];
            j += 1;
            k
        });
        for endpoints in &mut self.edge_index_endpoints {
            endpoints.0 = remap[endpoints.0];
            endpoints.1 = remap[endpoints.1];
        }
        // br-r37-c1-d58s8 edges-map flip: rekey survivors through the remap.
        self.edges = std::mem::take(&mut self.edges)
            .into_iter()
            .map(|((l, r), attrs)| ((remap[l], remap[r]), attrs))
            .collect();
        let old_rows = std::mem::take(&mut self.adj_indices);
        self.adj_indices = old_rows
            .into_iter()
            .enumerate()
            .filter(|(old_idx, _)| !removed_mask[*old_idx])
            .map(|(_, row)| {
                row.into_iter()
                    .filter(|&nbr| !removed_mask[nbr])
                    .map(|nbr| remap[nbr])
                    .collect()
            })
            .collect();

        let removed_nodes = old_node_count - self.nodes.len();
        let removed_edges = old_edge_count - self.edges.len();
        self.revision = self
            .revision
            .saturating_add(u64::try_from(removed_nodes).unwrap_or(u64::MAX));
        (removed_nodes, removed_edges)
    }

    /// Rebuild integer adjacency from string adjacency. Called after node
    /// removal since indices shift.
    #[allow(dead_code)]
    /// br-r37-c1-d58s8: revision-keyed memo of "every edge's `attr`
    /// value is an integer (missing = default 1 = int)".
    #[must_use]
    pub fn edge_weights_all_int(&self, attr: &str) -> bool {
        if let Ok(guard) = self.all_int_cache.read()
            && let Some((rev, a, v)) = guard.as_ref()
            && *rev == self.revision
            && a == attr
        {
            return *v;
        }
        let v = self
            .edges
            .values()
            .all(|attrs| attrs.get(attr).is_none_or(fnx_runtime::CgseValue::is_int));
        if let Ok(mut guard) = self.all_int_cache.write() {
            *guard = Some((self.revision, attr.to_owned(), v));
        }
        v
    }

    pub fn edges_ordered(&self) -> Vec<EdgeSnapshot> {
        // br-r37-c1-d58s8 P2(b): index-native u-major walk — integer
        // pair dedup + an integer (min,max)->attr map built once from
        // edge_index_endpoints; zero String hashing in the loop. Walk
        // order (u-major over adj_indices rows) is identical to the
        // String-row walk (rows are order-faithful mirrors).
        let mut pair_attrs: std::collections::HashMap<(usize, usize), &AttrMap> =
            std::collections::HashMap::with_capacity(self.edges.len());
        for ((l, r), attrs) in self.edge_index_endpoints.iter().zip(self.edges.values()) {
            // endpoints are stored STRING-canonical; normalize to
            // index-canonical (min, max) for the walk's dedup pairs.
            let pair = if l <= r { (*l, *r) } else { (*r, *l) };
            pair_attrs.insert(pair, attrs);
        }
        let mut ordered = Vec::with_capacity(self.edges.len());
        let mut seen = HashSet::<(usize, usize)>::with_capacity(self.edges.len());
        for (u, row) in self.adj_indices.iter().enumerate() {
            for &v in row {
                let pair = if u <= v { (u, v) } else { (v, u) };
                if !seen.insert(pair) {
                    continue;
                }
                if let Some(attrs) = pair_attrs.get(&pair) {
                    ordered.push(EdgeSnapshot {
                        left: self.nodes.get_index(u).expect("valid node index").0.clone(),
                        right: self.nodes.get_index(v).expect("valid node index").0.clone(),
                        attrs: (*attrs).clone(),
                    });
                }
            }
        }

        ordered
    }

    #[must_use]
    pub fn edges_ordered_borrowed(&self) -> Vec<(&str, &str, &AttrMap)> {
        // br-r37-c1-d58s8 P2(b): index-native (see edges_ordered).
        let mut pair_attrs: std::collections::HashMap<(usize, usize), &AttrMap> =
            std::collections::HashMap::with_capacity(self.edges.len());
        for ((l, r), attrs) in self.edge_index_endpoints.iter().zip(self.edges.values()) {
            // endpoints are stored STRING-canonical; normalize to
            // index-canonical (min, max) for the walk's dedup pairs.
            let pair = if l <= r { (*l, *r) } else { (*r, *l) };
            pair_attrs.insert(pair, attrs);
        }
        let mut ordered = Vec::with_capacity(self.edges.len());
        let mut seen_pairs = HashSet::<(usize, usize)>::with_capacity(self.edges.len());
        for (u, row) in self.adj_indices.iter().enumerate() {
            for &v in row {
                let pair = if u <= v { (u, v) } else { (v, u) };
                if !seen_pairs.insert(pair) {
                    continue;
                }
                if let Some(attrs) = pair_attrs.get(&pair) {
                    let left = self.nodes.get_index(u).expect("valid node index").0;
                    let right = self.nodes.get_index(v).expect("valid node index").0;
                    ordered.push((left.as_str(), right.as_str(), *attrs));
                }
            }
        }

        if ordered.len() < self.edges.len() {
            for (&(l, r), attrs) in &self.edges {
                if seen_pairs.insert((l, r)) {
                    let left = self.nodes.get_index(l).expect("valid index").0;
                    let right = self.nodes.get_index(r).expect("valid index").0;
                    ordered.push((left.as_str(), right.as_str(), attrs));
                }
            }
        }

        ordered
    }

    /// br-r37-c1-wsize (cc): integer `size(weight)` straight from the CgseValue
    /// store. `size(weight)` is `sum(degree(weight))/2`; the `/2` exactly cancels
    /// the double-endpoint counting, so the weighted size equals each stored
    /// edge's weight summed ONCE (a self-loop is one stored edge → counted once,
    /// matching nx's degree-counts-it-twice-then-halves). Each edge appears once
    /// in `self.edges`, so a single store walk is the whole answer — no per-node
    /// PyObject degree materialization. Returns `None` (caller falls back to the
    /// exact float/PyObject degree path) on ANY non-integer weight value; a
    /// missing weight defaults to nx's int `1`. Integer addition is associative,
    /// so iteration order is irrelevant.
    #[must_use]
    pub fn weighted_size_int(&self, weight: &str) -> Option<i128> {
        let mut total: i128 = 0;
        for attrs in self.edges.values() {
            let value = match attrs.get(weight) {
                Some(CgseValue::Int(v)) => i128::from(*v),
                Some(_) => return None,
                None => 1,
            };
            total = total.checked_add(value)?;
        }
        Some(total)
    }

    /// br-r37-c1-2a00r: index-space twin of `edges_ordered_borrowed` — yields
    /// `(u, v)` node indices in the SAME node-major traversed order/orientation,
    /// without resolving endpoints to `&str`. Lets the EdgeView iterate edges and
    /// look up the per-index Python node-key object directly (O(1) incref) instead
    /// of hashing the canonical String per endpoint via `py_node_key`.
    #[must_use]
    pub fn edges_ordered_indices(&self) -> Vec<(usize, usize)> {
        // cc-edgesnodeded: nx's O(N) first-encounter edge dedup — yield (u, v) when
        // v has NOT yet been processed as a source (so each undirected edge emits
        // once, from its earlier-processed endpoint). Replaces the O(E)
        // `HashSet<(usize,usize)>` pair-dedup + `present` membership set that made
        // `list(G.edges())` ~0.57x nx on dense graphs (37k edges = ~150k pair
        // hashes). Same node-major adjacency order and same orientation, so
        // byte-identical. A `vec![bool]` node marker is O(1) per neighbour, no
        // hashing. Falls back to the exact present/seen_pairs rebuild only if the
        // adjacency walk does not reproduce the full edge set (degenerate /
        // inconsistent adjacency), preserving the original contract there.
        let node_count = self.adj_indices.len();
        let mut ordered = Vec::with_capacity(self.edges.len());
        let mut seen_source = vec![false; node_count];
        for (u, row) in self.adj_indices.iter().enumerate() {
            for &v in row {
                if !seen_source[v] {
                    ordered.push((u, v));
                }
            }
            seen_source[u] = true;
        }
        if ordered.len() == self.edges.len() {
            return ordered;
        }
        // Fallback (degenerate adjacency): the exact present/seen_pairs rebuild.
        let mut present: HashSet<(usize, usize)> = HashSet::with_capacity(self.edges.len());
        for &(l, r) in &self.edge_index_endpoints {
            present.insert(if l <= r { (l, r) } else { (r, l) });
        }
        let mut ordered = Vec::with_capacity(self.edges.len());
        let mut seen_pairs = HashSet::<(usize, usize)>::with_capacity(self.edges.len());
        for (u, row) in self.adj_indices.iter().enumerate() {
            for &v in row {
                let pair = if u <= v { (u, v) } else { (v, u) };
                if !seen_pairs.insert(pair) {
                    continue;
                }
                if present.contains(&pair) {
                    ordered.push((u, v));
                }
            }
        }
        if ordered.len() < self.edges.len() {
            // Mirror edges_ordered_borrowed's fallback EXACTLY: iterate
            // self.edges with the raw (l, r) key orientation and dedup on the
            // raw key (not (min,max)) so degenerate cases stay byte-identical.
            for &(l, r) in self.edges.keys() {
                if seen_pairs.insert((l, r)) {
                    ordered.push((l, r));
                }
            }
        }
        ordered
    }

    #[must_use]
    pub fn edges_storage_order_borrowed(&self) -> Vec<(&str, &str, &AttrMap)> {
        // orientation from edge_index_endpoints (string-canonical, kept
        // element-parallel with edges).
        self.edge_index_endpoints
            .iter()
            .zip(self.edges.values())
            .map(|(&(l, r), attrs)| {
                (
                    self.nodes.get_index(l).expect("valid index").0.as_str(),
                    self.nodes.get_index(r).expect("valid index").0.as_str(),
                    attrs,
                )
            })
            .collect()
    }

    pub fn edges_storage_order_iter(&self) -> impl Iterator<Item = (&str, &str, &AttrMap)> + '_ {
        self.edge_index_endpoints
            .iter()
            .zip(self.edges.values())
            .map(|(&(l, r), attrs)| {
                (
                    self.nodes.get_index(l).expect("valid index").0.as_str(),
                    self.nodes.get_index(r).expect("valid index").0.as_str(),
                    attrs,
                )
            })
    }

    #[must_use]
    pub fn snapshot(&self) -> GraphSnapshot {
        // br-snapnodeattrs: preserve per-node attributes alongside the
        // bare node name list so callers replaying a snapshot don't lose
        // ``add_node(n, attrs)`` data.
        let node_attrs: BTreeMap<String, AttrMap> = self
            .nodes
            .iter()
            .filter(|(_, attrs)| !attrs.is_empty())
            .map(|(name, attrs)| (name.clone(), attrs.clone()))
            .collect();
        GraphSnapshot {
            mode: self.mode,
            nodes: self.nodes.keys().cloned().collect(),
            node_attrs,
            edges: self.edges_ordered(),
        }
    }

    fn record_decision(
        &mut self,
        operation: &'static str,
        incompatibility_probability: f64,
        unknown_incompatible_feature: bool,
        evidence: Vec<EvidenceTerm>,
    ) -> DecisionAction {
        let action = self
            .runtime_policy
            .action_for(incompatibility_probability, unknown_incompatible_feature);
        self.runtime_policy.record(
            operation,
            action,
            incompatibility_probability,
            "argmin expected loss over {allow,full_validate,fail_closed}",
            evidence,
        );
        action
    }
}

/// br-r37-c1-thp6w slice 1: revision-keyed integer-adjacency memo for MultiGraph. Holds the
/// integer neighbor rows (`get_node_index` of each adjacency-row neighbor, in row order),
/// lazily built from the authoritative String `adjacency` and reused until the graph mutates.
/// Interior mutability (RwLock) so it can populate on a `&self` read while staying `Sync`,
/// matching `Graph::all_int_cache`. Clone yields a FRESH (empty) memo — never shared — so a
/// clone that mutates independently can never serve another graph's rows.
#[derive(Debug, Default)]
struct IntAdjCache(std::sync::RwLock<Option<(u64, Vec<Vec<usize>>)>>);

impl Clone for IntAdjCache {
    fn clone(&self) -> Self {
        Self::default()
    }
}

/// br-r37-c1-thp6w S4: the structural row delta of one single-edge MultiGraph
/// mutation, used by `advance_int_adj_memo` to keep a warm integer-adjacency
/// memo live across the mutation instead of invalidating it.
enum IntAdjEdgeDelta<'a> {
    Add {
        left: &'a str,
        right: &'a str,
        left_new: bool,
        right_new: bool,
        pair_new: bool,
    },
    Remove {
        left: &'a str,
        right: &'a str,
        pair_gone: bool,
    },
}

/// br-r37-c1-thp6w S5 (`feature = "mg-int-storage-proto"`): index-keyed
/// MultiGraph storage prototype — the d58s8-pattern layout the storage-flip
/// epoch targets. The String adjacency rows and String-pair edge keys are
/// replaced by node-index forms; the String node-name table remains the only
/// String storage (exactly as in the flipped simple `Graph`). This module is
/// parity-gated scaffolding, NOT production storage: the gates prove the
/// index layout derives byte-identical observable orderings (node order,
/// per-row distinct-neighbor order, per-pair key order) from the same insert
/// stream, and the paired A/B measures the pure storage-representation tax
/// the flip removes. Compiled under cfg(test) so the gates run in the normal
/// suite; the cargo feature exposes it to sibling crates for benches.
#[cfg(any(test, feature = "mg-int-storage-proto", feature = "mg-int-storage"))]
pub mod mg_int_storage_proto {
    use super::AttrMap;
    use indexmap::{IndexMap, IndexSet};

    /// Index-keyed analog of the MultiGraph storage core. Internal pair
    /// canonicalization is (min_idx, max_idx) — deliberately DIFFERENT from
    /// the String-lex `EdgeKey` canonical ("10" < "2" lex, 2 < 10 numeric) —
    /// because pair-key orientation is never observable: every public
    /// ordering derives from the rows walk + per-cell key sets, which the
    /// parity gates pin byte-for-byte.
    #[derive(Debug, Default)]
    pub struct MgIntStorageProto {
        /// Node names in insertion order (the surviving String table).
        pub node_names: Vec<String>,
        /// name -> index resolution (the `nodes` map analog).
        pub node_index: IndexMap<String, usize, rustc_hash::FxBuildHasher>,
        /// node idx -> distinct-neighbor idx -> parallel-edge key set,
        /// insertion-ordered exactly like the String rows.
        pub rows: Vec<IndexMap<usize, IndexSet<usize>>>,
        /// (min_idx, max_idx) -> key -> attrs.
        pub edges: IndexMap<(usize, usize), IndexMap<usize, AttrMap>, rustc_hash::FxBuildHasher>,
        pub edge_count: usize,
    }

    impl MgIntStorageProto {
        #[must_use]
        pub fn new() -> Self {
            Self::default()
        }

        fn ensure_node(&mut self, name: &str) -> usize {
            if let Some(&idx) = self.node_index.get(name) {
                return idx;
            }
            let idx = self.node_names.len();
            self.node_names.push(name.to_owned());
            self.node_index.insert(name.to_owned(), idx);
            self.rows.push(IndexMap::new());
            idx
        }

        /// Mirror of `MultiGraph::extend_keyed_edges_with_attrs_unrecorded`'s
        /// per-edge storage ops: endpoint nodes created on demand, an existing
        /// (pair, key) cell merges attrs, new cells count toward `edge_count`.
        pub fn add_keyed_edge(&mut self, left: &str, right: &str, key: usize, attrs: AttrMap) {
            let l = self.ensure_node(left);
            let r = if left == right {
                l
            } else {
                self.ensure_node(right)
            };
            let pair = (l.min(r), l.max(r));
            let bucket = self.edges.entry(pair).or_default();
            if !bucket.contains_key(&key) {
                self.edge_count += 1;
            }
            bucket.entry(key).or_default().extend(attrs);
            self.rows[l].entry(r).or_default().insert(key);
            if l != r {
                self.rows[r].entry(l).or_default().insert(key);
            }
        }

        /// Mirror of `MultiGraph::extend_fresh_int_prefix_keyed_edges_unrecorded`
        /// for the A/B: same node-name String table build (fairness — the name
        /// table survives the flip), then pure index-keyed edge inserts with no
        /// String clone/hash per edge.
        #[must_use]
        pub fn bulk_load_int_prefix<I>(node_count: usize, edges: I) -> Self
        where
            I: IntoIterator<Item = (usize, usize, usize)>,
        {
            let iterator = edges.into_iter();
            let (lower_bound, _) = iterator.size_hint();
            let mut proto = Self::new();
            proto.node_names.reserve(node_count);
            proto.node_index.reserve(node_count);
            proto.rows.reserve(node_count);
            proto.edges.reserve(lower_bound);
            for node in 0..node_count {
                let name = node.to_string();
                proto.node_names.push(name.clone());
                proto.node_index.insert(name, node);
                proto.rows.push(IndexMap::new());
            }
            for (left_idx, right_idx, key) in iterator {
                debug_assert!(left_idx < node_count);
                debug_assert!(right_idx < node_count);
                let pair = (left_idx.min(right_idx), left_idx.max(right_idx));
                proto
                    .edges
                    .entry(pair)
                    .or_default()
                    .insert(key, AttrMap::new());
                proto.rows[left_idx]
                    .entry(right_idx)
                    .or_default()
                    .insert(key);
                if left_idx != right_idx {
                    proto.rows[right_idx]
                        .entry(left_idx)
                        .or_default()
                        .insert(key);
                }
                proto.edge_count += 1;
            }
            proto
        }

        /// Distinct neighbors of node `i` as names, in row order.
        #[must_use]
        pub fn neighbor_names(&self, i: usize) -> Vec<&str> {
            self.rows[i]
                .keys()
                .map(|&j| self.node_names[j].as_str())
                .collect()
        }

        /// Parallel-edge key order for the (left, right) pair, `edge_keys_vec` analog.
        #[must_use]
        pub fn key_order(&self, left: &str, right: &str) -> Vec<usize> {
            let (Some(&l), Some(&r)) = (self.node_index.get(left), self.node_index.get(right))
            else {
                return Vec::new();
            };
            self.edges
                .get(&(l.min(r), l.max(r)))
                .map(|bucket| bucket.keys().copied().collect())
                .unwrap_or_default()
        }

        /// br-r37-c1-thp6w S7: mirror of `MultiGraph::remove_edge` on the
        /// index layout — `key=None` picks the LAST bucket key (`next_back`),
        /// the surviving bucket keeps its key order (shift semantics), an
        /// emptied pair drops from the outer edges map (order unobservable)
        /// and shift-removes the neighbor cell from both rows.
        pub fn remove_edge(&mut self, left: &str, right: &str, key: Option<usize>) -> bool {
            let (Some(&l), Some(&r)) = (self.node_index.get(left), self.node_index.get(right))
            else {
                return false;
            };
            let pair = (l.min(r), l.max(r));
            let Some(bucket) = self.edges.get_mut(&pair) else {
                return false;
            };
            let Some(removal_key) = key.or_else(|| bucket.keys().next_back().copied()) else {
                return false;
            };
            if bucket.shift_remove(&removal_key).is_none() {
                return false;
            }
            self.edge_count -= 1;
            let pair_gone = bucket.is_empty();
            if pair_gone {
                self.edges.swap_remove(&pair);
            }
            let mut drop_cell = |u: usize, v: usize| {
                let mut cell_empty = false;
                if let Some(keys) = self.rows[u].get_mut(&v) {
                    keys.shift_remove(&removal_key);
                    cell_empty = keys.is_empty();
                }
                if cell_empty {
                    self.rows[u].shift_remove(&v);
                }
            };
            drop_cell(l, r);
            if l != r {
                drop_cell(r, l);
            }
            true
        }

        /// br-r37-c1-thp6w S7: mirror of `MultiGraph::remove_node` under the
        /// index layout — the d58s8-pattern fused renumber (Graph::remove_node
        /// template): drop the node's row, decrement every surviving index
        /// above it in one order-preserving pass per row, rebuild the edges
        /// map order-preserving with incident pairs skipped and both pair
        /// members decremented (order within the pair is preserved by a
        /// uniform decrement, so the index-canonical invariant survives).
        pub fn remove_node(&mut self, name: &str) -> bool {
            let Some(&idx) = self.node_index.get(name) else {
                return false;
            };
            self.node_names.remove(idx);
            self.node_index.shift_remove(name);
            for stored in self.node_index.values_mut() {
                if *stored > idx {
                    *stored -= 1;
                }
            }
            self.rows.remove(idx);
            for row in &mut self.rows {
                let old = std::mem::take(row);
                for (j, keys) in old {
                    if j == idx {
                        continue;
                    }
                    row.insert(if j > idx { j - 1 } else { j }, keys);
                }
            }
            let old_edges = std::mem::take(&mut self.edges);
            let mut removed_cells = 0usize;
            for ((a, b), bucket) in old_edges {
                if a == idx || b == idx {
                    removed_cells += bucket.len();
                    continue;
                }
                self.edges.insert(
                    (
                        if a > idx { a - 1 } else { a },
                        if b > idx { b - 1 } else { b },
                    ),
                    bucket,
                );
            }
            self.edge_count -= removed_cells;
            true
        }
    }

    /// br-r37-c1-thp6w S6: singleton-optimized parallel-key cell. The
    /// insertion-ordered set semantics of `IndexSet<usize>` are preserved
    /// exactly (dedup on insert, One -> Many promotion appends), but the
    /// singleton case — the overwhelmingly common one in real multigraphs —
    /// allocates NOTHING.
    #[derive(Debug, Clone)]
    pub enum CompactKeys {
        One(usize),
        Many(IndexSet<usize>),
    }

    impl CompactKeys {
        /// Set-insert preserving insertion order; returns true if newly added.
        pub fn insert(&mut self, key: usize) -> bool {
            match self {
                Self::One(existing) => {
                    if *existing == key {
                        return false;
                    }
                    let mut set = IndexSet::with_capacity(2);
                    set.insert(*existing);
                    set.insert(key);
                    *self = Self::Many(set);
                    true
                }
                Self::Many(set) => set.insert(key),
            }
        }

        #[must_use]
        pub fn order(&self) -> Vec<usize> {
            match self {
                Self::One(key) => vec![*key],
                Self::Many(set) => set.iter().copied().collect(),
            }
        }

        /// br-r37-c1-thp6w S9: order-preserving key removal; returns
        /// (removed, cell_now_empty). A `Many` that shrinks to one entry stays
        /// `Many` — only iteration order is observable, not the variant.
        pub fn shift_remove(&mut self, key: usize) -> (bool, bool) {
            match self {
                Self::One(existing) => {
                    let removed = *existing == key;
                    (removed, removed)
                }
                Self::Many(set) => {
                    let removed = set.shift_remove(&key);
                    (removed, set.is_empty())
                }
            }
        }
    }

    /// br-r37-c1-thp6w S6: singleton-optimized (pair -> key -> attrs) bucket,
    /// insertion-key-ordered like `IndexMap<usize, AttrMap>`; the singleton
    /// case stores the key + attrs inline with no map allocation (an empty
    /// `AttrMap`/BTreeMap does not allocate).
    #[derive(Debug, Clone)]
    pub enum CompactBucket {
        One(usize, AttrMap),
        Many(IndexMap<usize, AttrMap>),
    }

    impl CompactBucket {
        /// `entry(key).or_default().extend(attrs)` analog; returns true if the
        /// (key) cell is new.
        pub fn merge(&mut self, key: usize, attrs: AttrMap) -> bool {
            match self {
                Self::One(existing, existing_attrs) => {
                    if *existing == key {
                        existing_attrs.extend(attrs);
                        return false;
                    }
                    let mut map = IndexMap::with_capacity(2);
                    map.insert(*existing, std::mem::take(existing_attrs));
                    map.insert(key, attrs);
                    *self = Self::Many(map);
                    true
                }
                Self::Many(map) => {
                    let is_new = !map.contains_key(&key);
                    map.entry(key).or_default().extend(attrs);
                    is_new
                }
            }
        }

        #[must_use]
        pub fn key_order(&self) -> Vec<usize> {
            match self {
                Self::One(key, _) => vec![*key],
                Self::Many(map) => map.keys().copied().collect(),
            }
        }

        #[must_use]
        pub fn attrs_for(&self, key: usize) -> Option<&AttrMap> {
            match self {
                Self::One(existing, attrs) => (*existing == key).then_some(attrs),
                Self::Many(map) => map.get(&key),
            }
        }

        /// br-r37-c1-thp6w S9: number of parallel keys in the bucket.
        #[must_use]
        pub fn len(&self) -> usize {
            match self {
                Self::One(..) => 1,
                Self::Many(map) => map.len(),
            }
        }

        #[must_use]
        pub fn is_empty(&self) -> bool {
            self.len() == 0
        }

        /// br-r37-c1-thp6w S9: the LAST key in insertion order (the real
        /// `remove_edge(key=None)` default via `next_back`).
        #[must_use]
        pub fn last_key(&self) -> Option<usize> {
            match self {
                Self::One(key, _) => Some(*key),
                Self::Many(map) => map.keys().next_back().copied(),
            }
        }

        /// br-r37-c1-thp6w S9: order-preserving key removal; returns
        /// (removed, bucket_now_empty).
        pub fn shift_remove(&mut self, key: usize) -> (bool, bool) {
            match self {
                Self::One(existing, _) => {
                    let removed = *existing == key;
                    (removed, removed)
                }
                Self::Many(map) => {
                    let removed = map.shift_remove(&key).is_some();
                    (removed, map.is_empty())
                }
            }
        }

        /// br-r37-c1-thp6w S12: key-ordered (key, attrs) iteration without a
        /// per-bucket allocation (read-path hot loop).
        pub fn iter(&self) -> CompactBucketIter<'_> {
            match self {
                Self::One(key, attrs) => CompactBucketIter::One(std::iter::once((*key, attrs))),
                Self::Many(map) => CompactBucketIter::Many(map.iter()),
            }
        }
    }

    /// br-r37-c1-thp6w S12: enum iterator for `CompactBucket::iter` (no Box,
    /// no per-bucket allocation).
    pub enum CompactBucketIter<'a> {
        One(std::iter::Once<(usize, &'a AttrMap)>),
        Many(indexmap::map::Iter<'a, usize, AttrMap>),
    }

    impl<'a> Iterator for CompactBucketIter<'a> {
        type Item = (usize, &'a AttrMap);

        fn next(&mut self) -> Option<Self::Item> {
            match self {
                Self::One(it) => it.next(),
                Self::Many(it) => it.next().map(|(key, attrs)| (*key, attrs)),
            }
        }
    }

    /// br-r37-c1-thp6w S6: the compact-bucket variant of the index-keyed
    /// layout — identical structure to `MgIntStorageProto` except both nested
    /// bucket levels use the singleton-optimized enums, so a simple-graph-like
    /// multigraph (no parallel edges) performs ZERO per-pair bucket
    /// allocations.
    #[derive(Debug, Default)]
    pub struct MgIntStorageProtoCompact {
        pub node_names: Vec<String>,
        pub node_index: IndexMap<String, usize, rustc_hash::FxBuildHasher>,
        pub rows: Vec<IndexMap<usize, CompactKeys>>,
        pub edges: IndexMap<(usize, usize), CompactBucket, rustc_hash::FxBuildHasher>,
        pub edge_count: usize,
    }

    impl MgIntStorageProtoCompact {
        #[must_use]
        pub fn new() -> Self {
            Self::default()
        }

        fn ensure_node(&mut self, name: &str) -> usize {
            if let Some(&idx) = self.node_index.get(name) {
                return idx;
            }
            let idx = self.node_names.len();
            self.node_names.push(name.to_owned());
            self.node_index.insert(name.to_owned(), idx);
            self.rows.push(IndexMap::new());
            idx
        }

        /// Mirror of `MgIntStorageProto::add_keyed_edge` on compact buckets.
        pub fn add_keyed_edge(&mut self, left: &str, right: &str, key: usize, attrs: AttrMap) {
            let l = self.ensure_node(left);
            let r = if left == right {
                l
            } else {
                self.ensure_node(right)
            };
            let pair = (l.min(r), l.max(r));
            match self.edges.entry(pair) {
                indexmap::map::Entry::Occupied(mut bucket) => {
                    if bucket.get_mut().merge(key, attrs) {
                        self.edge_count += 1;
                    }
                }
                indexmap::map::Entry::Vacant(slot) => {
                    slot.insert(CompactBucket::One(key, attrs));
                    self.edge_count += 1;
                }
            }
            match self.rows[l].entry(r) {
                indexmap::map::Entry::Occupied(mut cell) => {
                    let _ = cell.get_mut().insert(key);
                }
                indexmap::map::Entry::Vacant(slot) => {
                    slot.insert(CompactKeys::One(key));
                }
            }
            if l != r {
                match self.rows[r].entry(l) {
                    indexmap::map::Entry::Occupied(mut cell) => {
                        let _ = cell.get_mut().insert(key);
                    }
                    indexmap::map::Entry::Vacant(slot) => {
                        slot.insert(CompactKeys::One(key));
                    }
                }
            }
        }

        /// Mirror of `MgIntStorageProto::bulk_load_int_prefix` on compact buckets.
        #[must_use]
        pub fn bulk_load_int_prefix<I>(node_count: usize, edges: I) -> Self
        where
            I: IntoIterator<Item = (usize, usize, usize)>,
        {
            let iterator = edges.into_iter();
            let (lower_bound, _) = iterator.size_hint();
            let mut proto = Self::new();
            proto.node_names.reserve(node_count);
            proto.node_index.reserve(node_count);
            proto.rows.reserve(node_count);
            proto.edges.reserve(lower_bound);
            for node in 0..node_count {
                let name = node.to_string();
                proto.node_names.push(name.clone());
                proto.node_index.insert(name, node);
                proto.rows.push(IndexMap::new());
            }
            for (left_idx, right_idx, key) in iterator {
                debug_assert!(left_idx < node_count);
                debug_assert!(right_idx < node_count);
                let pair = (left_idx.min(right_idx), left_idx.max(right_idx));
                match proto.edges.entry(pair) {
                    indexmap::map::Entry::Occupied(mut bucket) => {
                        let _ = bucket.get_mut().merge(key, AttrMap::new());
                    }
                    indexmap::map::Entry::Vacant(slot) => {
                        slot.insert(CompactBucket::One(key, AttrMap::new()));
                    }
                }
                match proto.rows[left_idx].entry(right_idx) {
                    indexmap::map::Entry::Occupied(mut cell) => {
                        let _ = cell.get_mut().insert(key);
                    }
                    indexmap::map::Entry::Vacant(slot) => {
                        slot.insert(CompactKeys::One(key));
                    }
                }
                if left_idx != right_idx {
                    match proto.rows[right_idx].entry(left_idx) {
                        indexmap::map::Entry::Occupied(mut cell) => {
                            let _ = cell.get_mut().insert(key);
                        }
                        indexmap::map::Entry::Vacant(slot) => {
                            slot.insert(CompactKeys::One(key));
                        }
                    }
                }
                proto.edge_count += 1;
            }
            proto
        }

        /// Distinct neighbors of node `i` as names, in row order.
        #[must_use]
        pub fn neighbor_names(&self, i: usize) -> Vec<&str> {
            self.rows[i]
                .keys()
                .map(|&j| self.node_names[j].as_str())
                .collect()
        }

        /// Parallel-edge key order for the (left, right) pair.
        #[must_use]
        pub fn key_order(&self, left: &str, right: &str) -> Vec<usize> {
            let (Some(&l), Some(&r)) = (self.node_index.get(left), self.node_index.get(right))
            else {
                return Vec::new();
            };
            self.edges
                .get(&(l.min(r), l.max(r)))
                .map(CompactBucket::key_order)
                .unwrap_or_default()
        }
    }

    /// br-r37-c1-thp6w S9: the slab/stable-slot layout MANDATED by the S8
    /// removal A/B (positional renumber measured 190-203x slower than the
    /// String store). Node identity = a STABLE SLOT that never renumbers;
    /// removal tombstones the slot (free-list reuse) and shift-removes only
    /// the order entry, so rows and edge pair-keys stay valid with ZERO
    /// rekeying. nx-observable insertion order lives entirely in `node_order`
    /// (name -> slot, insertion-ordered IndexMap — the same structure and
    /// O(V) shift_remove the production String store already pays). Buckets
    /// are the S6 compact enums (the winning construction layout).
    #[derive(Debug, Clone, Default)]
    pub struct MgSlabStorageProto {
        /// name -> stable slot, iteration = nx node insertion order.
        pub node_order: IndexMap<String, usize, rustc_hash::FxBuildHasher>,
        /// slot -> name (None = tombstone awaiting reuse/compaction).
        pub slot_names: Vec<Option<String>>,
        /// LIFO free-list of tombstoned slots.
        pub free_slots: Vec<usize>,
        /// slot -> neighbor slot -> parallel-key cell (row insertion order).
        pub rows: Vec<IndexMap<usize, CompactKeys>>,
        /// slot-canonical (min, max) pair -> compact bucket. Slots are stable,
        /// so pair keys survive any removal without rekeying.
        pub edges: IndexMap<(usize, usize), CompactBucket, rustc_hash::FxBuildHasher>,
        pub edge_count: usize,
    }

    impl MgSlabStorageProto {
        #[must_use]
        pub fn new() -> Self {
            Self::default()
        }

        fn ensure_node(&mut self, name: &str) -> usize {
            if let Some(&slot) = self.node_order.get(name) {
                return slot;
            }
            let slot = if let Some(reused) = self.free_slots.pop() {
                debug_assert!(self.slot_names[reused].is_none());
                debug_assert!(self.rows[reused].is_empty());
                self.slot_names[reused] = Some(name.to_owned());
                reused
            } else {
                self.slot_names.push(Some(name.to_owned()));
                self.rows.push(IndexMap::new());
                self.slot_names.len() - 1
            };
            self.node_order.insert(name.to_owned(), slot);
            slot
        }

        /// Same insert semantics as the S5/S6 variants, slot-keyed.
        pub fn add_keyed_edge(&mut self, left: &str, right: &str, key: usize, attrs: AttrMap) {
            let l = self.ensure_node(left);
            let r = if left == right {
                l
            } else {
                self.ensure_node(right)
            };
            let pair = (l.min(r), l.max(r));
            match self.edges.entry(pair) {
                indexmap::map::Entry::Occupied(mut bucket) => {
                    if bucket.get_mut().merge(key, attrs) {
                        self.edge_count += 1;
                    }
                }
                indexmap::map::Entry::Vacant(slot) => {
                    slot.insert(CompactBucket::One(key, attrs));
                    self.edge_count += 1;
                }
            }
            match self.rows[l].entry(r) {
                indexmap::map::Entry::Occupied(mut cell) => {
                    let _ = cell.get_mut().insert(key);
                }
                indexmap::map::Entry::Vacant(slot) => {
                    slot.insert(CompactKeys::One(key));
                }
            }
            if l != r {
                match self.rows[r].entry(l) {
                    indexmap::map::Entry::Occupied(mut cell) => {
                        let _ = cell.get_mut().insert(key);
                    }
                    indexmap::map::Entry::Vacant(slot) => {
                        slot.insert(CompactKeys::One(key));
                    }
                }
            }
        }

        /// Bulk loader mirroring the S5/S6 int-prefix arms (fresh graph, slots
        /// == 0..n, no tombstones).
        #[must_use]
        pub fn bulk_load_int_prefix<I>(node_count: usize, edges: I) -> Self
        where
            I: IntoIterator<Item = (usize, usize, usize)>,
        {
            let iterator = edges.into_iter();
            let (lower_bound, _) = iterator.size_hint();
            let mut proto = Self::new();
            proto.node_order.reserve(node_count);
            proto.slot_names.reserve(node_count);
            proto.rows.reserve(node_count);
            proto.edges.reserve(lower_bound);
            for node in 0..node_count {
                let name = node.to_string();
                proto.node_order.insert(name.clone(), node);
                proto.slot_names.push(Some(name));
                proto.rows.push(IndexMap::new());
            }
            for (left_slot, right_slot, key) in iterator {
                debug_assert!(left_slot < node_count);
                debug_assert!(right_slot < node_count);
                let pair = (left_slot.min(right_slot), left_slot.max(right_slot));
                match proto.edges.entry(pair) {
                    indexmap::map::Entry::Occupied(mut bucket) => {
                        let _ = bucket.get_mut().merge(key, AttrMap::new());
                    }
                    indexmap::map::Entry::Vacant(slot) => {
                        slot.insert(CompactBucket::One(key, AttrMap::new()));
                    }
                }
                match proto.rows[left_slot].entry(right_slot) {
                    indexmap::map::Entry::Occupied(mut cell) => {
                        let _ = cell.get_mut().insert(key);
                    }
                    indexmap::map::Entry::Vacant(slot) => {
                        slot.insert(CompactKeys::One(key));
                    }
                }
                if left_slot != right_slot {
                    match proto.rows[right_slot].entry(left_slot) {
                        indexmap::map::Entry::Occupied(mut cell) => {
                            let _ = cell.get_mut().insert(key);
                        }
                        indexmap::map::Entry::Vacant(slot) => {
                            slot.insert(CompactKeys::One(key));
                        }
                    }
                }
                proto.edge_count += 1;
            }
            proto
        }

        /// Mirror of `MultiGraph::remove_edge` (key=None -> LAST bucket key).
        pub fn remove_edge(&mut self, left: &str, right: &str, key: Option<usize>) -> bool {
            let (Some(&l), Some(&r)) = (self.node_order.get(left), self.node_order.get(right))
            else {
                return false;
            };
            let pair = (l.min(r), l.max(r));
            let Some(bucket) = self.edges.get_mut(&pair) else {
                return false;
            };
            let Some(removal_key) = key.or_else(|| bucket.last_key()) else {
                return false;
            };
            let (removed, bucket_empty) = bucket.shift_remove(removal_key);
            if !removed {
                return false;
            }
            self.edge_count -= 1;
            if bucket_empty {
                self.edges.swap_remove(&pair);
            }
            let mut drop_cell = |u: usize, v: usize| {
                let mut cell_empty = false;
                if let Some(keys) = self.rows[u].get_mut(&v) {
                    let (cell_removed, now_empty) = keys.shift_remove(removal_key);
                    debug_assert!(cell_removed);
                    cell_empty = now_empty;
                }
                if cell_empty {
                    self.rows[u].shift_remove(&v);
                }
            };
            drop_cell(l, r);
            if l != r {
                drop_cell(r, l);
            }
            true
        }

        /// Slab removal: O(V) order-entry shift + O(degree) row/bucket drops.
        /// NO renumber, NO edges rekey — the S8-mandated shape.
        pub fn remove_node(&mut self, name: &str) -> bool {
            let Some(&slot) = self.node_order.get(name) else {
                return false;
            };
            let neighbors: Vec<usize> = self.rows[slot].keys().copied().collect();
            for nbr in neighbors {
                if nbr != slot {
                    self.rows[nbr].shift_remove(&slot);
                }
                if let Some(bucket) = self.edges.swap_remove(&(slot.min(nbr), slot.max(nbr))) {
                    self.edge_count -= bucket.len();
                }
            }
            self.rows[slot] = IndexMap::new();
            self.node_order.shift_remove(name);
            self.slot_names[slot] = None;
            self.free_slots.push(slot);
            true
        }

        /// Distinct neighbors (names, row order) of the node at insertion-order
        /// position `pos`.
        #[must_use]
        pub fn neighbor_names(&self, pos: usize) -> Vec<&str> {
            let Some((_, &slot)) = self.node_order.get_index(pos) else {
                return Vec::new();
            };
            self.rows[slot]
                .keys()
                .map(|&s| {
                    self.slot_names[s]
                        .as_deref()
                        .expect("row references a live slot")
                })
                .collect()
        }

        /// Parallel-edge key order for the (left, right) pair.
        #[must_use]
        pub fn key_order(&self, left: &str, right: &str) -> Vec<usize> {
            let (Some(&l), Some(&r)) = (self.node_order.get(left), self.node_order.get(right))
            else {
                return Vec::new();
            };
            self.edges
                .get(&(l.min(r), l.max(r)))
                .map(CompactBucket::key_order)
                .unwrap_or_default()
        }

        /// br-r37-c1-thp6w S11: build a slab store from a live String-keyed
        /// MultiGraph, reproducing EVERY observed order directly (node order,
        /// each row's cell order, each bucket's key order, attrs) — valid for
        /// ANY reachable state including post-`apply_row_orders` row orders
        /// that no insert stream could reproduce. Fresh slots = positions
        /// (no tombstones).
        #[must_use]
        pub fn from_string_state(g: &super::MultiGraph) -> Self {
            let n = g.nodes.len();
            let mut slab = Self::new();
            slab.node_order.reserve(n);
            slab.slot_names.reserve(n);
            slab.rows.reserve(n);
            for (slot, name) in g.nodes.keys().enumerate() {
                slab.node_order.insert(name.clone(), slot);
                slab.slot_names.push(Some(name.clone()));
                slab.rows.push(IndexMap::new());
            }
            for (u_name, row) in &g.adjacency {
                let u = *slab
                    .node_order
                    .get(u_name.as_str())
                    .expect("adjacency key must be a live node");
                for (v_name, keys) in row {
                    let v = *slab
                        .node_order
                        .get(v_name.as_str())
                        .expect("row neighbor must be a live node");
                    let mut cell: Option<CompactKeys> = None;
                    for &key in keys {
                        match &mut cell {
                            None => cell = Some(CompactKeys::One(key)),
                            Some(c) => {
                                let _ = c.insert(key);
                            }
                        }
                    }
                    if let Some(c) = cell {
                        slab.rows[u].insert(v, c);
                    }
                }
            }
            slab.edges.reserve(g.edges.len());
            for (edge_key, bucket) in &g.edges {
                let l = *slab
                    .node_order
                    .get(edge_key.left.as_str())
                    .expect("edge endpoint must be a live node");
                let r = *slab
                    .node_order
                    .get(edge_key.right.as_str())
                    .expect("edge endpoint must be a live node");
                let pair = (l.min(r), l.max(r));
                let mut compact: Option<CompactBucket> = None;
                for (&key, attrs) in bucket {
                    match &mut compact {
                        None => compact = Some(CompactBucket::One(key, attrs.clone())),
                        Some(b) => {
                            let _ = b.merge(key, attrs.clone());
                        }
                    }
                }
                if let Some(b) = compact {
                    slab.edges.insert(pair, b);
                }
            }
            slab.edge_count = g.edge_count;
            slab
        }

        /// br-r37-c1-thp6w S10: slot -> insertion-order position (usize::MAX
        /// for tombstones), rebuilt on demand in O(V).
        fn slot_positions(&self) -> Vec<usize> {
            let mut pos = vec![usize::MAX; self.slot_names.len()];
            for (p, (_, &slot)) in self.node_order.iter().enumerate() {
                pos[slot] = p;
            }
            pos
        }

        /// br-r37-c1-thp6w S12: full `edges_ordered_borrowed` analog with
        /// attrs — the production read candidate. Same walk contract as
        /// `edges_ordered_names` (node order x row order x bucket key order,
        /// first-touch dedup, String-lex canonical emission orientation) but
        /// hashing only usizes where the String store hashes `EdgeKeyRef`
        /// String pairs per cell and per seen-set probe.
        #[must_use]
        pub fn edges_ordered_borrowed(&self) -> Vec<(&str, &str, usize, &AttrMap)> {
            let mut ordered = Vec::with_capacity(self.edge_count);
            let mut seen: std::collections::HashSet<(usize, usize, usize)> =
                std::collections::HashSet::with_capacity(self.edge_count);
            for (u_name, &u_slot) in &self.node_order {
                for &v_slot in self.rows[u_slot].keys() {
                    let pair = (u_slot.min(v_slot), u_slot.max(v_slot));
                    let Some(bucket) = self.edges.get(&pair) else {
                        continue;
                    };
                    for (key, attrs) in bucket.iter() {
                        if !seen.insert((pair.0, pair.1, key)) {
                            continue;
                        }
                        let v_name = self.slot_names[v_slot]
                            .as_deref()
                            .expect("row references a live slot");
                        let (left, right) = if u_name.as_str() <= v_name {
                            (u_name.as_str(), v_name)
                        } else {
                            (v_name, u_name.as_str())
                        };
                        ordered.push((left, right, key, attrs));
                    }
                }
            }
            ordered
        }

        /// br-r37-c1-thp6w S13: index-space analog of `edges_ordered_borrowed`
        /// — the same walk/order/orientation, but each endpoint emitted as its
        /// POSITION (node_order iteration index = nx node position), not its
        /// name. A `slot -> position` array is built once up front (O(n),
        /// hash-free — positions come straight from `node_order` iteration, so
        /// this is correct under any slot recycling, where slot != position),
        /// then the walk resolves both endpoints by O(1) array index. The only
        /// per-edge string op is the lex compare for the canonical orientation
        /// (production `edges_ordered_indices_borrowed` pays a `get_index_of`
        /// String hash per endpoint plus an `EdgeKey` pair hash instead).
        #[must_use]
        pub fn edges_ordered_indices_borrowed(&self) -> Vec<(usize, usize, usize, &AttrMap)> {
            let mut slot_to_pos = vec![0usize; self.slot_names.len()];
            for (pos, (_name, &slot)) in self.node_order.iter().enumerate() {
                slot_to_pos[slot] = pos;
            }
            let mut ordered = Vec::with_capacity(self.edge_count);
            let mut seen: std::collections::HashSet<(usize, usize, usize)> =
                std::collections::HashSet::with_capacity(self.edge_count);
            for (u_name, &u_slot) in &self.node_order {
                for &v_slot in self.rows[u_slot].keys() {
                    let pair = (u_slot.min(v_slot), u_slot.max(v_slot));
                    let Some(bucket) = self.edges.get(&pair) else {
                        continue;
                    };
                    for (key, attrs) in bucket.iter() {
                        if !seen.insert((pair.0, pair.1, key)) {
                            continue;
                        }
                        let v_name = self.slot_names[v_slot]
                            .as_deref()
                            .expect("row references a live slot");
                        let (left_pos, right_pos) = if u_name.as_str() <= v_name {
                            (slot_to_pos[u_slot], slot_to_pos[v_slot])
                        } else {
                            (slot_to_pos[v_slot], slot_to_pos[u_slot])
                        };
                        ordered.push((left_pos, right_pos, key, attrs));
                    }
                }
            }
            ordered
        }

        /// br-r37-c1-thp6w S10: `edges_ordered_borrowed` analog — the ONLY
        /// observed edge order. Walk = node insertion order, row order, bucket
        /// key order; each (pair, key) emitted once (first touch); emitted
        /// orientation = STRING-LEX canonical (`EdgeKey` semantics), derived
        /// from the names at emission since the internal pair key is
        /// slot-canonical. This is the snapshot/pickle orientation gate.
        #[must_use]
        pub fn edges_ordered_names(&self) -> Vec<(&str, &str, usize)> {
            let mut ordered = Vec::with_capacity(self.edge_count);
            let mut seen: std::collections::HashSet<(usize, usize, usize)> =
                std::collections::HashSet::with_capacity(self.edge_count);
            for (u_name, &u_slot) in &self.node_order {
                for &v_slot in self.rows[u_slot].keys() {
                    let pair = (u_slot.min(v_slot), u_slot.max(v_slot));
                    let Some(bucket) = self.edges.get(&pair) else {
                        continue;
                    };
                    for key in bucket.key_order() {
                        if !seen.insert((pair.0, pair.1, key)) {
                            continue;
                        }
                        let v_name = self.slot_names[v_slot]
                            .as_deref()
                            .expect("row references a live slot");
                        let (left, right) = if u_name.as_str() <= v_name {
                            (u_name.as_str(), v_name)
                        } else {
                            (v_name, u_name.as_str())
                        };
                        ordered.push((left, right, key));
                    }
                }
            }
            ordered
        }

        /// br-r37-c1-thp6w S10: `MultiGraph::reorder_rows_for_nx_copy_walk`
        /// under slot storage. Two-phase exactly like the real one: ALL new
        /// row orders are computed against the PRE-reorder rows (early =
        /// earlier-position neighbors sorted by (pos(v), index of u within
        /// row v), then late in original order), then applied. Sort key
        /// (pos, idx, slot) is equivalent to the real (pos, idx, name)
        /// because pos is unique per neighbor.
        pub fn reorder_rows_for_nx_copy_walk(&mut self) {
            let pos = self.slot_positions();
            let order_slots: Vec<usize> = self.node_order.values().copied().collect();
            let mut new_orders: Vec<(usize, Vec<usize>)> = Vec::with_capacity(order_slots.len());
            for &u_slot in &order_slots {
                let pu = pos[u_slot];
                let mut early: Vec<(usize, usize, usize)> = Vec::new();
                let mut late: Vec<usize> = Vec::new();
                for &v_slot in self.rows[u_slot].keys() {
                    let pv = pos[v_slot];
                    if pv < pu {
                        let idx = self.rows[v_slot]
                            .get_index_of(&u_slot)
                            .unwrap_or(usize::MAX);
                        early.push((pv, idx, v_slot));
                    } else {
                        late.push(v_slot);
                    }
                }
                early.sort_unstable();
                let mut order: Vec<usize> = early.into_iter().map(|(_, _, v)| v).collect();
                order.extend(late);
                new_orders.push((u_slot, order));
            }
            for (u_slot, order) in new_orders {
                let mut old = std::mem::take(&mut self.rows[u_slot]);
                let mut rebuilt = IndexMap::with_capacity(old.len());
                for v_slot in order {
                    if let Some(cell) = old.shift_remove(&v_slot) {
                        rebuilt.insert(v_slot, cell);
                    }
                }
                debug_assert!(old.is_empty(), "copy-walk reorder dropped a cell");
                self.rows[u_slot] = rebuilt;
            }
        }
    }
}

#[derive(Debug, Clone)]
pub struct MultiGraph {
    mode: CompatibilityMode,
    revision: u64,
    nodes: FxIndexMap<String, AttrMap>,
    adjacency: FxIndexMap<String, IndexMap<String, IndexSet<usize>>>,
    edges: FxIndexMap<EdgeKey, IndexMap<usize, AttrMap>>,
    runtime_policy: RuntimePolicy,
    edge_count: usize,
    /// br-r37-c1-thp6w slice 1: lazy revision-keyed integer adjacency (see `IntAdjCache`).
    int_adj_cache: IntAdjCache,
    /// br-r37-c1-thp6w S11: revision-keyed slab shadow store (production
    /// strangler stage 1). `Some((rev, slab))` is valid iff `rev == revision`;
    /// instrumented mutations advance it in place, everything else leaves it
    /// stale (dropped lazily). Inert without the `mg-int-storage` feature.
    #[cfg(feature = "mg-int-storage")]
    slab_shadow: Option<Box<(u64, mg_int_storage_proto::MgSlabStorageProto)>>,
}

impl MultiGraph {
    /// br-r37-c1-7dpyg: structural clone with a FRESH RuntimePolicy —
    /// see Graph::clone_with_fresh_policy.
    #[must_use]
    pub fn clone_with_fresh_policy(&self) -> Self {
        Self {
            mode: self.mode,
            revision: self.revision,
            nodes: self.nodes.clone(),
            adjacency: self.adjacency.clone(),
            edges: self.edges.clone(),
            runtime_policy: RuntimePolicy::new(self.mode),
            edge_count: self.edge_count,
            int_adj_cache: IntAdjCache::default(),
            #[cfg(feature = "mg-int-storage")]
            slab_shadow: None,
        }
    }

    /// br-r37-c1-s0d4x: reorder every adjacency row into NetworkX's
    /// `MultiGraph.copy()` walk order — the multigraph counterpart of
    /// Graph::reorder_rows_for_nx_copy_walk (cells move wholesale). A
    /// pair's cells enter both rows at the first u-major touch: row u =
    /// earlier-position neighbors sorted by (pos(v), index of u within
    /// row v), then the rest (self-loops included) in original order.
    pub fn reorder_rows_for_nx_copy_walk(&mut self) {
        // br-r37-c1-predrebuild NOTE: a 2-pass early[]-rebuild (like the directed
        // MultiDiGraph variant) was tried here and REVERTED — it was a regression
        // (dense MultiGraph.copy 0.60x -> 0.44x). Unlike the directed succ-walk
        // (1 pass, no lookups), the undirected early/late split needs pos(u) AND
        // pos(v), so the rebuild does 2 adjacency passes + 2 get_index_of/edge,
        // outweighing the (cheap integer-keyed) sort it removed. The sort-based
        // form below is faster for the String-keyed multigraph adjacency.
        let n = self.adjacency.len();
        let mut new_orders: Vec<Vec<String>> = Vec::with_capacity(n);
        for (pu, (u, row)) in self.adjacency.iter().enumerate() {
            let mut early: Vec<(usize, usize, String)> = Vec::new();
            let mut late: Vec<String> = Vec::new();
            for v in row.keys() {
                let pv = self
                    .adjacency
                    .get_index_of(v.as_str())
                    .unwrap_or(usize::MAX);
                if pv < pu {
                    let idx = self
                        .adjacency
                        .get(v.as_str())
                        .and_then(|r| r.get_index_of(u.as_str()))
                        .unwrap_or(usize::MAX);
                    early.push((pv, idx, v.clone()));
                } else {
                    late.push(v.clone());
                }
            }
            early.sort_unstable();
            let mut order: Vec<String> = early.into_iter().map(|(_, _, v)| v).collect();
            order.extend(late);
            new_orders.push(order);
        }
        let keys: Vec<String> = self.adjacency.keys().cloned().collect();
        let orders: Vec<(String, Vec<String>)> = keys.into_iter().zip(new_orders).collect();
        self.apply_row_orders(&orders);
    }

    /// br-r37-c1-u3qyn: restore explicit adjacency row orders (pickle
    /// round-trip) — see Graph::apply_row_orders. Multigraph rows are
    /// keyed cells (neighbor -> key set); the cells move wholesale.
    pub fn apply_row_orders(&mut self, orders: &[(String, Vec<String>)]) {
        for (node, order) in orders {
            let Some(row) = self.adjacency.get_mut(node.as_str()) else {
                continue;
            };
            let mut old = std::mem::take(row);
            let mut new_row = IndexMap::with_capacity(old.len());
            for v in order {
                if let Some((k, val)) = old.shift_remove_entry(v.as_str()) {
                    new_row.insert(k, val);
                }
            }
            for (k, val) in old {
                new_row.insert(k, val);
            }
            *row = new_row;
        }
        // br-r37-c1-thp6w slice 1: a pure ROW-ORDER change (MultiGraph.copy walk order,
        // pickle round-trip) does NOT bump `revision`, so the revision-keyed int-adjacency
        // memo would otherwise serve stale row order. Drop it explicitly here — this is the
        // only adjacency mutator that changes order without a content (revision) bump.
        *self
            .int_adj_cache
            .0
            .get_mut()
            .expect("int_adj_cache poisoned") = None;
        // br-r37-c1-thp6w S11: same reasoning for the slab shadow — arbitrary
        // row orders are not mirrored in slice 1; drop and let a later
        // `sync_slab_shadow` rebuild from the (order-faithful) String state.
        #[cfg(feature = "mg-int-storage")]
        {
            self.slab_shadow = None;
        }
    }

    #[must_use]
    pub fn new(mode: CompatibilityMode) -> Self {
        Self {
            mode,
            revision: 0,
            nodes: FxIndexMap::default(),
            adjacency: FxIndexMap::default(),
            edges: FxIndexMap::default(),
            runtime_policy: RuntimePolicy::new(mode),
            edge_count: 0,
            int_adj_cache: IntAdjCache::default(),
            #[cfg(feature = "mg-int-storage")]
            slab_shadow: None,
        }
    }

    #[must_use]
    pub fn with_runtime_policy(runtime_policy: RuntimePolicy) -> Self {
        let mode = runtime_policy.mode();
        Self {
            mode,
            revision: 0,
            nodes: FxIndexMap::default(),
            adjacency: FxIndexMap::default(),
            edges: FxIndexMap::default(),
            runtime_policy,
            edge_count: 0,
            int_adj_cache: IntAdjCache::default(),
            #[cfg(feature = "mg-int-storage")]
            slab_shadow: None,
        }
    }

    #[must_use]
    pub fn strict() -> Self {
        Self::new(CompatibilityMode::Strict)
    }

    #[must_use]
    pub fn hardened() -> Self {
        Self::new(CompatibilityMode::Hardened)
    }

    #[must_use]
    pub fn mode(&self) -> CompatibilityMode {
        self.mode
    }

    #[must_use]
    pub fn node_count(&self) -> usize {
        self.nodes.len()
    }

    #[must_use]
    pub fn edge_count(&self) -> usize {
        self.edge_count
    }

    #[must_use]
    pub fn number_of_selfloops(&self) -> usize {
        self.edges
            .iter()
            .filter(|(edge_key, _)| edge_key.left == edge_key.right)
            .map(|(_, edge_bucket)| edge_bucket.len())
            .sum()
    }

    /// Return edge keys as Vec (needed by Python bindings).
    #[must_use]
    pub fn edge_keys(&self, left: &str, right: &str) -> Option<Vec<usize>> {
        self.adjacency
            .get(left)?
            .get(right)
            .map(|keys| keys.iter().copied().collect())
    }

    /// Return an iterator over keys for edges between left and right.
    pub fn edge_keys_iter(&self, left: &str, right: &str) -> Option<impl Iterator<Item = &usize>> {
        self.adjacency.get(left)?.get(right).map(|keys| keys.iter())
    }

    #[must_use]
    pub fn revision(&self) -> u64 {
        self.revision
    }

    #[must_use]
    pub fn has_node(&self, node: &str) -> bool {
        self.nodes.contains_key(node)
    }

    #[must_use]
    pub fn has_edge(&self, left: &str, right: &str) -> bool {
        self.edges
            .get(&EdgeKeyRef::new(left, right))
            .is_some_and(|edge_bucket| !edge_bucket.is_empty())
    }

    /// br-r37-c1-04z53 (cc): resolve `has_edge` straight from insertion-order
    /// indices, skipping the `i.to_string()` heap alloc the Python binding pays
    /// for int nodes. The names come from the node table by index (borrowed, no
    /// alloc); the caller (`PyMultiGraph::has_edge`) guards each index with
    /// `node_index_matches_int` so the identity `index == int-value` holds
    /// (any removal / remap that broke it fails the guard and falls through to
    /// the String path). Mirror of `Graph::has_edge_by_indices`.
    #[must_use]
    pub fn has_edge_by_indices(&self, li: usize, ri: usize) -> bool {
        match (self.get_node_name(li), self.get_node_name(ri)) {
            (Some(left), Some(right)) => self.has_edge(left, right),
            _ => false,
        }
    }

    #[must_use]
    pub fn nodes_ordered(&self) -> Vec<&str> {
        self.nodes.keys().map(String::as_str).collect()
    }

    /// Resolve a node through the insertion-ordered node table without
    /// rebuilding a query-local name-to-index map.
    #[must_use]
    #[inline]
    pub fn get_node_index(&self, node: &str) -> Option<usize> {
        self.nodes.get_index_of(node)
    }

    /// Resolve the current node name for an insertion-order index.
    #[must_use]
    #[inline]
    pub fn get_node_name(&self, index: usize) -> Option<&str> {
        self.nodes.get_index(index).map(|(name, _)| name.as_str())
    }

    /// br-cc-nbunchbulk: int membership fast path for `_nbunch_present` — see the
    /// simple-Graph accessor.
    #[must_use]
    pub fn node_index_matches_int(&self, idx: usize) -> bool {
        self.nodes
            .get_index(idx)
            .is_some_and(|(k, _)| k.parse::<usize>() == Ok(idx))
    }

    #[must_use]
    pub fn neighbors(&self, node: &str) -> Option<Vec<&str>> {
        self.adjacency
            .get(node)
            .map(|neighbors| neighbors.keys().map(String::as_str).collect::<Vec<&str>>())
    }

    pub fn neighbors_iter(&self, node: &str) -> Option<impl Iterator<Item = &str> + '_> {
        self.adjacency
            .get(node)
            .map(|neighbors| neighbors.keys().map(String::as_str))
    }

    /// br-r37-c1-thp6w slice 1: build the integer adjacency from the authoritative String
    /// `adjacency`. Row `i` (node at insertion-index `i`) lists the node indices of that
    /// node's neighbors in adjacency-row order — i.e. exactly
    /// `[get_node_index(v) for v in neighbors_iter(node_i)]`. Distinct neighbors only
    /// (the parallel-edge multiplicity lives in `edges`), matching the String rows.
    fn build_int_adjacency(&self) -> Vec<Vec<usize>> {
        self.nodes
            .keys()
            .map(|name| {
                self.adjacency
                    .get(name.as_str())
                    .map_or_else(Vec::new, |row| {
                        row.keys()
                            .map(|v| {
                                self.nodes
                                    .get_index_of(v.as_str())
                                    .expect("adjacency neighbor must be a live node")
                            })
                            .collect()
                    })
            })
            .collect()
    }

    /// br-r37-c1-thp6w slice 1: run `f` with the integer adjacency (hash-free neighbor rows),
    /// built lazily from the String `adjacency` and memoized until the next mutation. The
    /// memo is keyed on `revision` (bumped by every content mutation) and cleared by
    /// `apply_row_orders` (the one order-only mutator), so the rows always match the current
    /// `adjacency` byte-for-byte. The closure form lets a whole traversal borrow the rows
    /// under one read lock without a per-node allocation. Foundation for the epoch's
    /// `neighbors_indices` traversal; no caller yet (infrastructure).
    pub fn with_int_adjacency<R>(&self, f: impl FnOnce(&[Vec<usize>]) -> R) -> R {
        {
            let guard = self.int_adj_cache.0.read().expect("int_adj_cache poisoned");
            if let Some((rev, adj)) = guard.as_ref()
                && *rev == self.revision
            {
                return f(adj);
            }
        }
        let adj = self.build_int_adjacency();
        let result = f(&adj);
        *self
            .int_adj_cache
            .0
            .write()
            .expect("int_adj_cache poisoned") = Some((self.revision, adj));
        result
    }

    /// br-r37-c1-thp6w S4: advance a warm integer-adjacency memo across one
    /// single-edge mutation instead of invalidating it. The memo must still be
    /// keyed at `prev_revision` (the revision on entry to the mutating call);
    /// the delta mirrors the String-row edit exactly (new distinct neighbors
    /// append, emptied pairs shift-remove, new nodes push fresh rows), then the
    /// memo re-keys to the post-mutation revision. Every mutation path that
    /// does NOT call this leaves the memo keyed at a stale revision, so
    /// `with_int_adjacency` lazily rebuilds — unhandled sites stay exactly as
    /// safe as the invalidate-only scheme.
    fn advance_int_adj_memo(&mut self, prev_revision: u64, delta: IntAdjEdgeDelta<'_>) {
        let needs_indices = matches!(
            delta,
            IntAdjEdgeDelta::Add { pair_new: true, .. }
                | IntAdjEdgeDelta::Remove {
                    pair_gone: true,
                    ..
                }
        );
        let indices = if needs_indices {
            let (left, right) = match &delta {
                IntAdjEdgeDelta::Add { left, right, .. }
                | IntAdjEdgeDelta::Remove { left, right, .. } => (*left, *right),
            };
            match (
                self.nodes.get_index_of(left),
                self.nodes.get_index_of(right),
            ) {
                (Some(u), Some(v)) => Some((u, v)),
                _ => None,
            }
        } else {
            None
        };
        let Ok(slot) = self.int_adj_cache.0.get_mut() else {
            return;
        };
        if needs_indices && indices.is_none() {
            // Endpoint missing from the node table (should be unreachable for a
            // live edge): the delta cannot be mirrored, so drop the memo.
            *slot = None;
            return;
        }
        let Some((rev, rows)) = slot.as_mut() else {
            return;
        };
        if *rev != prev_revision {
            return;
        }
        let mut advanced = true;
        match delta {
            IntAdjEdgeDelta::Add {
                left,
                right,
                left_new,
                right_new,
                pair_new,
            } => {
                if left_new {
                    rows.push(Vec::new());
                }
                if right_new && left != right {
                    rows.push(Vec::new());
                }
                if pair_new && let Some((u, v)) = indices {
                    rows[u].push(v);
                    if u != v {
                        rows[v].push(u);
                    }
                }
            }
            IntAdjEdgeDelta::Remove { pair_gone, .. } => {
                if pair_gone && let Some((u, v)) = indices {
                    // Mirror `IndexMap::shift_remove` on the String row:
                    // order-preserving removal of the emptied neighbor cell.
                    if let Some(pu) = rows[u].iter().position(|&x| x == v) {
                        rows[u].remove(pu);
                        if u != v {
                            if let Some(pv) = rows[v].iter().position(|&x| x == u) {
                                rows[v].remove(pv);
                            } else {
                                advanced = false;
                            }
                        }
                    } else {
                        advanced = false;
                    }
                }
            }
        }
        if advanced {
            *rev = self.revision;
        } else {
            *slot = None;
        }
    }

    /// br-r37-c1-thp6w S11: (re)build the slab shadow from the current String
    /// state and key it at the current revision. The from-state builder
    /// reproduces every observed order directly, so this is valid in ANY
    /// reachable state (including post-`apply_row_orders`).
    #[cfg(feature = "mg-int-storage")]
    pub fn sync_slab_shadow(&mut self) {
        let slab = mg_int_storage_proto::MgSlabStorageProto::from_string_state(self);
        self.slab_shadow = Some(Box::new((self.revision, slab)));
    }

    /// br-r37-c1-thp6w S11: true iff the shadow exists and is keyed at the
    /// CURRENT revision (i.e. advanced across every mutation since its sync).
    #[cfg(feature = "mg-int-storage")]
    #[must_use]
    pub fn slab_shadow_is_warm(&self) -> bool {
        self.slab_shadow
            .as_deref()
            .is_some_and(|(rev, _)| *rev == self.revision)
    }

    #[must_use]
    pub fn edge_keys_vec(&self, left: &str, right: &str) -> Vec<usize> {
        self.edges
            .get(&EdgeKeyRef::new(left, right))
            .map(|edge_bucket| edge_bucket.keys().copied().collect::<Vec<usize>>())
            .unwrap_or_default()
    }

    #[must_use]
    pub fn node_attrs(&self, node: &str) -> Option<&AttrMap> {
        self.nodes.get(node)
    }

    #[must_use]
    pub fn edge_attrs(&self, left: &str, right: &str, key: usize) -> Option<&AttrMap> {
        self.edges
            .get(&EdgeKeyRef::new(left, right))
            .and_then(|edge_bucket| edge_bucket.get(&key))
    }

    /// Iterator over the `AttrMap`s of every parallel edge between `left` and
    /// `right` (undirected: the single canonical bucket), yielded in the SAME
    /// order as `edge_keys` / `edge_keys_iter`. The adjacency `IndexSet<usize>`
    /// and this `edges` `IndexMap<usize, AttrMap>` are appended together on add
    /// and both `shift_remove`d on per-key remove (whole bucket dropped on
    /// node/endpoint removal), so their key order stays identical — callers that
    /// need adjacency-order iteration (e.g. the order-sensitive Neumaier weighted
    /// degree) may consume this directly instead of re-looking-up each key.
    /// Undirected sibling of `MultiDiGraph::edge_attr_values`.
    pub fn edge_attr_values(
        &self,
        left: &str,
        right: &str,
    ) -> Option<impl Iterator<Item = &AttrMap> + '_> {
        self.edges
            .get(&EdgeKeyRef::new(left, right))
            .map(|edge_bucket| edge_bucket.values())
    }

    #[must_use]
    pub fn evidence_ledger(&self) -> &EvidenceLedger {
        self.runtime_policy.decision_log()
    }

    #[must_use]
    pub fn runtime_policy(&self) -> &RuntimePolicy {
        &self.runtime_policy
    }

    pub fn set_runtime_policy(&mut self, runtime_policy: RuntimePolicy) {
        self.mode = runtime_policy.mode();
        self.runtime_policy = runtime_policy;
    }

    #[must_use]
    pub fn is_directed(&self) -> bool {
        false
    }

    #[must_use]
    pub fn is_multigraph(&self) -> bool {
        true
    }

    /// Return the degree of a node (total number of parallel edges incident).
    /// Self-loops contribute 2 to the degree each (NetworkX convention).
    #[must_use]
    pub fn degree(&self, node: &str) -> usize {
        self.adjacency.get(node).map_or(0, |neighbors| {
            let mut deg = 0;
            for (neighbor, keys) in neighbors {
                let count = keys.len();
                if neighbor == node {
                    // Self-loops count double (NetworkX convention)
                    deg += count * 2;
                } else {
                    deg += count;
                }
            }
            deg
        })
    }

    /// br-r37-c1-mgisol (cc): native isolate detection for MultiGraph. A node
    /// is isolated iff it has no incident edges (empty/absent adjacency row);
    /// a self-loop keeps a node non-isolated (the loop records the node in its
    /// own row, matching nx's degree-2 self-loop convention). Yields nodes in
    /// insertion order — identical to the `G.degree()`-driven nx generator and
    /// to the old `multigraph_to_simple_graph` projection path, but WITHOUT the
    /// per-call O(V+E) simple-graph rebuild that dominated the binding.
    #[must_use]
    pub fn isolates(&self) -> Vec<String> {
        self.nodes
            .keys()
            .filter(|node| {
                self.adjacency
                    .get(node.as_str())
                    .is_none_or(IndexMap::is_empty)
            })
            .cloned()
            .collect()
    }

    /// br-r37-c1-mgisol (cc): isolate count without the simple-graph projection.
    #[must_use]
    pub fn number_of_isolates(&self) -> usize {
        self.nodes
            .keys()
            .filter(|node| {
                self.adjacency
                    .get(node.as_str())
                    .is_none_or(IndexMap::is_empty)
            })
            .count()
    }

    /// br-r37-c1-mgisol (cc): O(1) isolate predicate. Absent node -> false
    /// (mirrors `is_isolate(&Graph)`); the binding validates presence first.
    #[must_use]
    pub fn is_isolate(&self, node: &str) -> bool {
        self.nodes.contains_key(node) && self.adjacency.get(node).is_none_or(IndexMap::is_empty)
    }

    pub fn add_node(&mut self, node: impl Into<String>) -> bool {
        self.add_node_with_attrs(node, AttrMap::new())
    }

    pub fn add_node_with_attrs(&mut self, node: impl Into<String>, attrs: AttrMap) -> bool {
        let node = node.into();
        let existed = self.nodes.contains_key(&node);
        let mut changed = !existed;
        let attrs_count = {
            let bucket = self.nodes.entry(node.clone()).or_default();
            if !attrs.is_empty()
                && attrs
                    .iter()
                    .any(|(key, value)| bucket.get(key) != Some(value))
            {
                changed = true;
            }
            bucket.extend(attrs);
            bucket.len()
        };
        self.adjacency.entry(node.clone()).or_default();
        if changed {
            self.revision = self.revision.saturating_add(1);
        }
        self.record_decision(
            "add_node",
            0.0,
            false,
            vec![
                EvidenceTerm {
                    signal: "node_preexisting".to_owned(),
                    observed_value: existed.to_string(),
                    log_likelihood_ratio: -3.0,
                },
                EvidenceTerm {
                    signal: "attrs_count".to_owned(),
                    observed_value: attrs_count.to_string(),
                    log_likelihood_ratio: -1.0,
                },
            ],
        );
        changed
    }

    pub fn add_edge(
        &mut self,
        left: impl Into<String>,
        right: impl Into<String>,
    ) -> Result<usize, GraphError> {
        self.add_edge_impl(left, right, None, AttrMap::new())
    }

    pub fn add_edge_with_attrs(
        &mut self,
        left: impl Into<String>,
        right: impl Into<String>,
        attrs: AttrMap,
    ) -> Result<usize, GraphError> {
        self.add_edge_impl(left, right, None, attrs)
    }

    pub fn add_edge_with_key_and_attrs(
        &mut self,
        left: impl Into<String>,
        right: impl Into<String>,
        key: usize,
        attrs: AttrMap,
    ) -> Result<usize, GraphError> {
        self.add_edge_impl(left, right, Some(key), attrs)
    }

    /// Insert one attribute-free edge for a pair known to have no existing
    /// parallel edge bucket. Returns `None` if the pair already exists.
    #[must_use]
    pub fn add_fresh_edge_unrecorded(
        &mut self,
        left: impl Into<String>,
        right: impl Into<String>,
    ) -> Option<usize> {
        self.add_fresh_edge_with_key_unrecorded(left, right, 0)
    }

    /// Insert one attribute-free edge with an explicit key for a pair known to
    /// have no existing parallel edge bucket. Returns `None` if the pair
    /// already exists.
    #[must_use]
    pub fn add_fresh_edge_with_key_unrecorded(
        &mut self,
        left: impl Into<String>,
        right: impl Into<String>,
        key: usize,
    ) -> Option<usize> {
        let left = left.into();
        let right = right.into();
        let edge_key = EdgeKey::new(&left, &right);
        if !self.nodes.contains_key(&left) {
            self.nodes.insert(left.clone(), AttrMap::new());
            self.adjacency.entry(left.clone()).or_default();
        }
        if left != right && !self.nodes.contains_key(&right) {
            self.nodes.insert(right.clone(), AttrMap::new());
            self.adjacency.entry(right.clone()).or_default();
        }

        match self.edges.entry(edge_key) {
            indexmap::map::Entry::Occupied(mut edge_bucket) => {
                if !edge_bucket.get().is_empty() {
                    return None;
                }
                edge_bucket.get_mut().insert(key, AttrMap::new());
            }
            indexmap::map::Entry::Vacant(edge_bucket) => {
                let mut bucket = IndexMap::new();
                bucket.insert(key, AttrMap::new());
                edge_bucket.insert(bucket);
            }
        }
        self.edge_count += 1;
        self.adjacency
            .entry(left.clone())
            .or_default()
            .entry(right.clone())
            .or_default()
            .insert(key);
        if left != right {
            self.adjacency
                .entry(right)
                .or_default()
                .entry(left)
                .or_default()
                .insert(key);
        }
        self.revision = self.revision.saturating_add(1);
        Some(key)
    }

    /// br-r37-c1-l5ve7: bulk node insert WITH attrs, one ledger record —
    /// MultiGraph mirror of MultiDiGraph::extend_nodes_with_attrs_unrecorded.
    /// Existing nodes merge attrs (extend).
    pub fn extend_nodes_with_attrs_unrecorded<I>(&mut self, nodes: I) -> usize
    where
        I: IntoIterator<Item = (String, AttrMap)>,
    {
        let mut inserted = 0usize;
        for (node, attrs) in nodes {
            if let Some(existing) = self.nodes.get_mut(&node) {
                existing.extend(attrs);
                continue;
            }
            self.nodes.insert(node.clone(), attrs);
            inserted += 1;
        }
        if inserted > 0 {
            self.revision = self
                .revision
                .saturating_add(u64::try_from(inserted).unwrap_or(u64::MAX));
            self.record_decision(
                "extend_nodes_with_attrs_unrecorded",
                0.0,
                false,
                vec![EvidenceTerm {
                    signal: "batch_node_count".to_owned(),
                    observed_value: inserted.to_string(),
                    log_likelihood_ratio: -1.0,
                }],
            );
        }
        inserted
    }

    /// br-r37-c1-l5ve7: bulk KEYED edge insert WITH attrs, one ledger
    /// record — MultiGraph mirror of
    /// MultiDiGraph::extend_keyed_edges_with_attrs_unrecorded
    /// (add_edge_impl pays TWO record_decision calls per edge). Endpoint
    /// nodes are created on demand; an existing (u, v, key) cell merges
    /// attrs (extend), matching add_edge_with_key_and_attrs.
    pub fn extend_keyed_edges_with_attrs_unrecorded<I>(&mut self, edges: I) -> usize
    where
        I: IntoIterator<Item = (String, String, usize, AttrMap)>,
    {
        // br-r37-c1-thp6w S11: write the batch through a warm slab shadow.
        // Taken out of `self` for the loop (the store mutations below need
        // `&mut self` fields), re-keyed and restored at the end.
        #[cfg(feature = "mg-int-storage")]
        let mut warm_shadow = match self.slab_shadow.take() {
            Some(shadow) if shadow.0 == self.revision => Some(shadow),
            other => {
                self.slab_shadow = other;
                None
            }
        };
        let mut inserted = 0usize;
        for (left, right, key, attrs) in edges {
            #[cfg(feature = "mg-int-storage")]
            if let Some(shadow) = warm_shadow.as_deref_mut() {
                shadow.1.add_keyed_edge(&left, &right, key, attrs.clone());
            }
            if !self.nodes.contains_key(&left) {
                self.nodes.insert(left.clone(), AttrMap::new());
                self.adjacency.entry(left.clone()).or_default();
            }
            if left != right && !self.nodes.contains_key(&right) {
                self.nodes.insert(right.clone(), AttrMap::new());
                self.adjacency.entry(right.clone()).or_default();
            }
            let edge_key = EdgeKey::new(&left, &right);
            let bucket = self.edges.entry(edge_key).or_default();
            if !bucket.contains_key(&key) {
                self.edge_count += 1;
                inserted += 1;
            }
            bucket.entry(key).or_default().extend(attrs);
            self.adjacency
                .entry(left.clone())
                .or_default()
                .entry(right.clone())
                .or_default()
                .insert(key);
            if left != right {
                self.adjacency
                    .entry(right)
                    .or_default()
                    .entry(left)
                    .or_default()
                    .insert(key);
            }
        }
        if inserted > 0 {
            self.revision = self
                .revision
                .saturating_add(u64::try_from(inserted).unwrap_or(u64::MAX));
            self.record_decision(
                "extend_keyed_edges_with_attrs_unrecorded",
                0.0,
                false,
                vec![EvidenceTerm {
                    signal: "batch_edge_count".to_owned(),
                    observed_value: inserted.to_string(),
                    log_likelihood_ratio: -1.0,
                }],
            );
        }
        // br-r37-c1-thp6w S11: re-key the written-through shadow to the
        // post-batch revision and put it back.
        #[cfg(feature = "mg-int-storage")]
        if let Some(mut shadow) = warm_shadow {
            shadow.0 = self.revision;
            self.slab_shadow = Some(shadow);
        }
        inserted
    }

    /// Bulk-load attribute-free keyed edges for a freshly-created integer
    /// prefix graph. The caller has already validated that node first-seen
    /// order is exactly `0..node_count` and that internal keys are sequential
    /// per undirected pair, so this builds the string-keyed MultiGraph state
    /// directly from indices instead of canonicalizing both endpoints for every
    /// edge in the Python boundary layer.
    #[must_use]
    pub fn extend_fresh_int_prefix_keyed_edges_unrecorded<I>(
        &mut self,
        node_count: usize,
        edges: I,
    ) -> usize
    where
        I: IntoIterator<Item = (usize, usize, usize)>,
    {
        debug_assert_eq!(self.node_count(), 0);
        debug_assert_eq!(self.edge_count(), 0);

        let iterator = edges.into_iter();
        let (lower_bound, _) = iterator.size_hint();
        self.nodes.reserve(node_count);
        self.adjacency.reserve(node_count);
        self.edges.reserve(lower_bound);

        let node_names = (0..node_count)
            .map(|node| node.to_string())
            .collect::<Vec<_>>();
        for node in &node_names {
            self.nodes.insert(node.clone(), AttrMap::new());
            self.adjacency.insert(node.clone(), IndexMap::new());
        }
        // br-r37-c1-thp6w S14: fresh graphs are born with a WARM slab shadow —
        // the slab build is ~3.5x cheaper than the String build it rides
        // along, and every routed read then serves the slab from birth.
        #[cfg(feature = "mg-int-storage")]
        let mut fresh_slab = {
            use mg_int_storage_proto::MgSlabStorageProto;
            let mut slab = MgSlabStorageProto::new();
            slab.node_order.reserve(node_count);
            slab.slot_names.reserve(node_count);
            slab.rows.reserve(node_count);
            slab.edges.reserve(lower_bound);
            for (slot, name) in node_names.iter().enumerate() {
                slab.node_order.insert(name.clone(), slot);
                slab.slot_names.push(Some(name.clone()));
                slab.rows.push(IndexMap::new());
            }
            slab
        };

        let mut inserted = 0usize;
        for (left_idx, right_idx, key) in iterator {
            debug_assert!(left_idx < node_names.len());
            debug_assert!(right_idx < node_names.len());
            #[cfg(feature = "mg-int-storage")]
            {
                use mg_int_storage_proto::{CompactBucket, CompactKeys};
                let pair = (left_idx.min(right_idx), left_idx.max(right_idx));
                match fresh_slab.edges.entry(pair) {
                    indexmap::map::Entry::Occupied(mut bucket) => {
                        let _ = bucket.get_mut().merge(key, AttrMap::new());
                    }
                    indexmap::map::Entry::Vacant(slot) => {
                        slot.insert(CompactBucket::One(key, AttrMap::new()));
                    }
                }
                match fresh_slab.rows[left_idx].entry(right_idx) {
                    indexmap::map::Entry::Occupied(mut cell) => {
                        let _ = cell.get_mut().insert(key);
                    }
                    indexmap::map::Entry::Vacant(slot) => {
                        slot.insert(CompactKeys::One(key));
                    }
                }
                if left_idx != right_idx {
                    match fresh_slab.rows[right_idx].entry(left_idx) {
                        indexmap::map::Entry::Occupied(mut cell) => {
                            let _ = cell.get_mut().insert(key);
                        }
                        indexmap::map::Entry::Vacant(slot) => {
                            slot.insert(CompactKeys::One(key));
                        }
                    }
                }
                fresh_slab.edge_count += 1;
            }

            let left = &node_names[left_idx];
            let right = &node_names[right_idx];
            let edge_key = EdgeKey::new(left, right);
            self.edges
                .entry(edge_key)
                .or_default()
                .insert(key, AttrMap::new());
            self.adjacency
                .get_mut(left.as_str())
                .expect("integer-prefix left node should exist")
                .entry(right.clone())
                .or_default()
                .insert(key);
            if left_idx != right_idx {
                self.adjacency
                    .get_mut(right.as_str())
                    .expect("integer-prefix right node should exist")
                    .entry(left.clone())
                    .or_default()
                    .insert(key);
            }
            self.edge_count += 1;
            inserted += 1;
        }
        if inserted > 0 || node_count > 0 {
            self.revision = self.revision.saturating_add(
                u64::try_from(inserted.saturating_add(node_count)).unwrap_or(u64::MAX),
            );
            self.record_decision(
                "extend_fresh_int_prefix_keyed_edges_unrecorded",
                0.0,
                false,
                vec![EvidenceTerm {
                    signal: "batch_edge_count".to_owned(),
                    observed_value: inserted.to_string(),
                    log_likelihood_ratio: -1.0,
                }],
            );
        }
        // br-r37-c1-thp6w S14: install the co-built slab, keyed at the final
        // revision — the fresh graph is warm from birth.
        #[cfg(feature = "mg-int-storage")]
        {
            debug_assert_eq!(fresh_slab.edge_count, self.edge_count);
            self.slab_shadow = Some(Box::new((self.revision, fresh_slab)));
        }
        inserted
    }

    /// Bulk-load attributed keyed edges for a freshly-created integer-indexed
    /// graph. The caller has already assigned NetworkX-compatible node labels
    /// and per-undirected-pair keys, so this avoids endpoint string hashing in
    /// the Python boundary layer while preserving the normal MultiGraph storage
    /// layout.
    #[must_use]
    pub fn extend_fresh_index_keyed_edges_with_attrs_unrecorded<I, N>(
        &mut self,
        nodes: N,
        edges: I,
    ) -> usize
    where
        I: IntoIterator<Item = (usize, usize, usize, AttrMap)>,
        N: IntoIterator<Item = String>,
    {
        if !self.nodes.is_empty() || !self.adjacency.is_empty() || !self.edges.is_empty() {
            return 0;
        }

        let node_labels: Vec<String> = nodes.into_iter().collect();
        for node in &node_labels {
            self.nodes.insert(node.clone(), AttrMap::new());
            self.adjacency.insert(node.clone(), IndexMap::new());
        }
        // br-r37-c1-thp6w S15: the attributed fresh path co-builds the slab
        // too (S14 pattern) — arbitrary labels, out-of-bounds skips, and
        // attr-merge semantics mirrored exactly.
        #[cfg(feature = "mg-int-storage")]
        let mut fresh_slab = {
            use mg_int_storage_proto::MgSlabStorageProto;
            let mut slab = MgSlabStorageProto::new();
            slab.node_order.reserve(node_labels.len());
            slab.slot_names.reserve(node_labels.len());
            slab.rows.reserve(node_labels.len());
            for (slot, name) in node_labels.iter().enumerate() {
                slab.node_order.insert(name.clone(), slot);
                slab.slot_names.push(Some(name.clone()));
                slab.rows.push(IndexMap::new());
            }
            slab
        };

        let node_count = node_labels.len();
        let mut inserted = 0usize;
        let mut merged_changed = false;
        for (left_idx, right_idx, key, attrs) in edges {
            let Some(left) = node_labels.get(left_idx) else {
                continue;
            };
            let Some(right) = node_labels.get(right_idx) else {
                continue;
            };
            #[cfg(feature = "mg-int-storage")]
            {
                use mg_int_storage_proto::{CompactBucket, CompactKeys};
                let pair = (left_idx.min(right_idx), left_idx.max(right_idx));
                match fresh_slab.edges.entry(pair) {
                    indexmap::map::Entry::Occupied(mut bucket) => {
                        if bucket.get_mut().merge(key, attrs.clone()) {
                            fresh_slab.edge_count += 1;
                        }
                    }
                    indexmap::map::Entry::Vacant(slot) => {
                        slot.insert(CompactBucket::One(key, attrs.clone()));
                        fresh_slab.edge_count += 1;
                    }
                }
                match fresh_slab.rows[left_idx].entry(right_idx) {
                    indexmap::map::Entry::Occupied(mut cell) => {
                        let _ = cell.get_mut().insert(key);
                    }
                    indexmap::map::Entry::Vacant(slot) => {
                        slot.insert(CompactKeys::One(key));
                    }
                }
                if left_idx != right_idx {
                    match fresh_slab.rows[right_idx].entry(left_idx) {
                        indexmap::map::Entry::Occupied(mut cell) => {
                            let _ = cell.get_mut().insert(key);
                        }
                        indexmap::map::Entry::Vacant(slot) => {
                            slot.insert(CompactKeys::One(key));
                        }
                    }
                }
            }

            let edge_key = EdgeKey::new(left, right);
            let bucket = self.edges.entry(edge_key).or_default();
            if !bucket.contains_key(&key) {
                self.edge_count += 1;
                inserted += 1;
            }
            let edge_attrs = bucket.entry(key).or_default();
            if !attrs.is_empty()
                && attrs
                    .iter()
                    .any(|(attr_key, value)| edge_attrs.get(attr_key) != Some(value))
            {
                merged_changed = true;
            }
            edge_attrs.extend(attrs);

            self.adjacency
                .get_mut(left.as_str())
                .expect("fresh left node row exists")
                .entry(right.clone())
                .or_default()
                .insert(key);
            if left_idx != right_idx {
                self.adjacency
                    .get_mut(right.as_str())
                    .expect("fresh right node row exists")
                    .entry(left.clone())
                    .or_default()
                    .insert(key);
            }
        }

        if node_count > 0 || inserted > 0 || merged_changed {
            self.revision = self.revision.saturating_add(
                u64::try_from(node_count.saturating_add(inserted)).unwrap_or(u64::MAX),
            );
            self.record_decision(
                "extend_fresh_index_keyed_edges_with_attrs_unrecorded",
                0.0,
                false,
                vec![
                    EvidenceTerm {
                        signal: "batch_node_count".to_owned(),
                        observed_value: node_count.to_string(),
                        log_likelihood_ratio: -1.0,
                    },
                    EvidenceTerm {
                        signal: "batch_edge_count".to_owned(),
                        observed_value: inserted.to_string(),
                        log_likelihood_ratio: -1.0,
                    },
                ],
            );
        }
        // br-r37-c1-thp6w S15: install the co-built slab keyed at the final
        // revision — attributed fresh graphs are warm from birth too.
        #[cfg(feature = "mg-int-storage")]
        {
            debug_assert_eq!(fresh_slab.edge_count, self.edge_count);
            self.slab_shadow = Some(Box::new((self.revision, fresh_slab)));
        }

        inserted
    }

    fn add_edge_impl(
        &mut self,
        left: impl Into<String>,
        right: impl Into<String>,
        explicit_key: Option<usize>,
        attrs: AttrMap,
    ) -> Result<usize, GraphError> {
        let left = left.into();
        let right = right.into();
        // br-r37-c1-thp6w S4: revision on entry — a warm int-adjacency memo
        // keyed here is advanced across this mutation instead of invalidated.
        let prev_revision = self.revision;
        // br-r37-c1-thp6w S11: the slab shadow needs the attrs too; capture a
        // copy only when the shadow is warm (they are consumed by the store).
        #[cfg(feature = "mg-int-storage")]
        let shadow_attrs = self
            .slab_shadow
            .as_deref()
            .is_some_and(|(rev, _)| *rev == prev_revision)
            .then(|| attrs.clone());

        let unknown_feature = attrs
            .keys()
            .any(|key| key.starts_with("__fnx_incompatible"));
        let incompatibility_probability = if unknown_feature {
            1.0
        } else if left == right {
            0.22
        } else {
            0.08
        };

        let action = self.record_decision(
            "add_edge",
            incompatibility_probability,
            unknown_feature,
            vec![EvidenceTerm {
                signal: "unknown_incompatible_feature".to_owned(),
                observed_value: unknown_feature.to_string(),
                log_likelihood_ratio: 12.0,
            }],
        );

        if action == DecisionAction::FailClosed || action == DecisionAction::FullValidate {
            return Err(GraphError::FailClosed {
                operation: "add_edge",
                reason: "incompatible edge metadata".to_owned(),
            });
        }

        let mut left_autocreated = false;
        if !self.nodes.contains_key(&left) {
            let _ = self.add_node(left.clone());
            left_autocreated = true;
        }
        let mut right_autocreated = false;
        if left == right {
            right_autocreated = left_autocreated;
        } else if !self.nodes.contains_key(&right) {
            let _ = self.add_node(right.clone());
            right_autocreated = true;
        }

        let edge_key = EdgeKey::new(&left, &right);
        let key = explicit_key.unwrap_or_else(|| {
            let edge_bucket = self.edges.get(&edge_key);
            let mut k = edge_bucket.map_or(0, |b| b.len());
            if let Some(b) = edge_bucket {
                while b.contains_key(&k) {
                    k += 1;
                }
            }
            k
        });
        let mut changed;
        let edge_attr_count = {
            let edge_bucket = self.edges.entry(edge_key.clone()).or_default();
            let is_new = !edge_bucket.contains_key(&key);
            if is_new {
                self.edge_count += 1;
            }
            changed = is_new;
            let edge_attrs = edge_bucket.entry(key).or_default();
            if !attrs.is_empty()
                && attrs
                    .iter()
                    .any(|(attr_key, value)| edge_attrs.get(attr_key) != Some(value))
            {
                changed = true;
            }
            edge_attrs.extend(attrs);
            edge_bucket.len()
        };

        let pair_was_present = self
            .adjacency
            .get(left.as_str())
            .is_some_and(|row| row.contains_key(right.as_str()));
        self.adjacency
            .entry(left.clone())
            .or_default()
            .entry(right.clone())
            .or_default()
            .insert(key);
        if left != right {
            self.adjacency
                .entry(right.clone())
                .or_default()
                .entry(left.clone())
                .or_default()
                .insert(key);
        }
        if changed {
            self.revision = self.revision.saturating_add(1);
        }
        if self.revision != prev_revision {
            self.advance_int_adj_memo(
                prev_revision,
                IntAdjEdgeDelta::Add {
                    left: &left,
                    right: &right,
                    left_new: left_autocreated,
                    right_new: right_autocreated,
                    pair_new: !pair_was_present,
                },
            );
        }
        // br-r37-c1-thp6w S11: advance the warm slab shadow across this add.
        #[cfg(feature = "mg-int-storage")]
        if self.revision != prev_revision
            && let Some(shadow_attrs) = shadow_attrs
        {
            let revision = self.revision;
            if let Some(shadow) = self.slab_shadow.as_deref_mut()
                && shadow.0 == prev_revision
            {
                shadow.1.add_keyed_edge(&left, &right, key, shadow_attrs);
                shadow.0 = revision;
            }
        }

        self.record_decision(
            "add_edge",
            incompatibility_probability,
            unknown_feature,
            vec![
                EvidenceTerm {
                    signal: "edge_key".to_owned(),
                    observed_value: key.to_string(),
                    log_likelihood_ratio: -2.0,
                },
                EvidenceTerm {
                    signal: "edge_attr_count".to_owned(),
                    observed_value: edge_attr_count.to_string(),
                    log_likelihood_ratio: -2.0,
                },
                EvidenceTerm {
                    signal: "left_autocreated".to_owned(),
                    observed_value: left_autocreated.to_string(),
                    log_likelihood_ratio: -1.25,
                },
                EvidenceTerm {
                    signal: "right_autocreated".to_owned(),
                    observed_value: right_autocreated.to_string(),
                    log_likelihood_ratio: -1.25,
                },
            ],
        );

        Ok(key)
    }

    /// br-r37-c1-sjf4t: overwrite the attribute map for an existing
    /// (u, v, key) edge. Returns whether the edge existed.
    pub fn replace_edge_attrs(
        &mut self,
        left: &str,
        right: &str,
        key: usize,
        attrs: AttrMap,
    ) -> bool {
        let edge_key = EdgeKey::new(left, right);
        if let Some(bucket) = self.edges.get_mut(&edge_key)
            && let Some(slot) = bucket.get_mut(&key)
        {
            if *slot != attrs {
                *slot = attrs;
                self.revision = self.revision.saturating_add(1);
            }
            return true;
        }
        false
    }

    /// br-r37-c1-sjf4t: overwrite the attribute map for an existing node.
    pub fn replace_node_attrs(&mut self, node: &str, attrs: AttrMap) -> bool {
        if let Some(slot) = self.nodes.get_mut(node) {
            if *slot != attrs {
                *slot = attrs;
                self.revision = self.revision.saturating_add(1);
            }
            true
        } else {
            false
        }
    }

    pub fn remove_edge(&mut self, left: &str, right: &str, key: Option<usize>) -> bool {
        // br-r37-c1-thp6w S4: revision on entry — a warm int-adjacency memo
        // keyed here is advanced across this mutation instead of invalidated.
        let prev_revision = self.revision;
        let edge_key = EdgeKeyRef::new(left, right);
        let removal_key = key.or_else(|| {
            self.edges
                .get(&edge_key)
                .and_then(|edge_bucket| edge_bucket.keys().next_back().copied())
        });

        let Some(removal_key) = removal_key else {
            return false;
        };

        let mut pair_gone = false;
        let removed = if let Some(edge_bucket) = self.edges.get_mut(&edge_key) {
            // Inner bucket keeps shift_remove: per-pair KEY order IS observed
            // (edges(keys=True) yields the bucket's key order; nx preserves
            // insertion order of surviving keys after a dict-key deletion).
            let was_removed = edge_bucket.shift_remove(&removal_key).is_some();
            if was_removed {
                self.edge_count -= 1;
                if edge_bucket.is_empty() {
                    // br-r37-c1-vbwpl (cc): swap_remove (O(1)) on the OUTER
                    // node-pair map — its storage order is never observed
                    // (edges_ordered walks adjacency and looks pairs up by key;
                    // remove_node already swap_removes this same map). Turns
                    // remove_edges_from from O(k*pairs) into O(k).
                    self.edges.swap_remove(&edge_key);
                    pair_gone = true;
                }
            }
            was_removed
        } else {
            false
        };

        if !removed {
            return false;
        }
        self.remove_adjacency_key(left, right, removal_key);
        if left != right {
            self.remove_adjacency_key(right, left, removal_key);
        }
        self.revision = self.revision.saturating_add(1);
        self.advance_int_adj_memo(
            prev_revision,
            IntAdjEdgeDelta::Remove {
                left,
                right,
                pair_gone,
            },
        );
        // br-r37-c1-thp6w S11: advance the warm slab shadow across this
        // removal, with the store-resolved key (never the None default).
        #[cfg(feature = "mg-int-storage")]
        {
            let revision = self.revision;
            if let Some(shadow) = self.slab_shadow.as_deref_mut()
                && shadow.0 == prev_revision
            {
                let shadow_removed = shadow.1.remove_edge(left, right, Some(removal_key));
                debug_assert!(shadow_removed, "shadow desync on remove_edge");
                shadow.0 = revision;
            }
        }
        true
    }

    pub fn clear_edges(&mut self) {
        if self.edge_count == 0 {
            return;
        }

        self.edges.clear();
        for row in self.adjacency.values_mut() {
            row.clear();
        }
        self.edge_count = 0;
        self.revision = self.revision.saturating_add(1);
    }

    pub fn remove_node(&mut self, node: &str) -> bool {
        if !self.nodes.contains_key(node) {
            return false;
        }
        // br-r37-c1-thp6w S11: revision on entry for the slab-shadow advance.
        #[cfg(feature = "mg-int-storage")]
        let prev_revision = self.revision;

        // br-r37-c1-p6bxu: drop each incident edge bucket with O(1) `swap_remove`
        // (the `edges` IndexMap order is never observed externally — every public
        // consumer reads via `edges_ordered`, which walks node->neighbor order;
        // no internal consumer iterates the map order). The incident pairs are
        // known exactly from this node's adjacency (each distinct neighbor maps
        // to one canonical bucket, self-loops included), so removal is O(degree)
        // instead of the O(|distinct pairs|) `retain` scan — matching nx.
        let mut removed_count = 0usize;
        if let Some(neighbors) = self.adjacency.get(node) {
            let neighbor_names: Vec<String> = neighbors.keys().cloned().collect();
            for neighbor in neighbor_names {
                if neighbor != node
                    && let Some(remote_neighbors) = self.adjacency.get_mut(&neighbor)
                {
                    remote_neighbors.shift_remove(node);
                }
                if let Some(bucket) = self.edges.swap_remove(&EdgeKeyRef::new(node, &neighbor)) {
                    removed_count += bucket.len();
                }
            }
        }
        self.edge_count -= removed_count;

        // Remove node from adjacency and nodes maps.
        self.adjacency.shift_remove(node);
        self.nodes.shift_remove(node);
        self.revision = self.revision.saturating_add(1);
        // br-r37-c1-thp6w S11: advance the warm slab shadow (slab removal is
        // O(V + degree): tombstone + order shift, no rekey).
        #[cfg(feature = "mg-int-storage")]
        {
            let revision = self.revision;
            if let Some(shadow) = self.slab_shadow.as_deref_mut()
                && shadow.0 == prev_revision
            {
                let shadow_removed = shadow.1.remove_node(node);
                debug_assert!(shadow_removed, "shadow desync on remove_node");
                shadow.0 = revision;
            }
        }
        true
    }

    /// br-r37-c1-mgrnf: batch node removal — the amortised analogue of
    /// `remove_node`. `MultiGraph::remove_node` pays two O(|V|) `shift_remove`s
    /// (the `adjacency` and `nodes` IndexMaps preserve insertion order), so a
    /// caller loop of `k` removals was O(k·|V|). This does each pass ONCE via
    /// `retain` — O(|V|+|E|) total, matching the simple-`Graph` batch
    /// (`Graph::remove_nodes_from`) that the directed types already carry.
    /// Returns `(removed_node_count, removed_edge_instance_count)`.
    pub fn remove_nodes_from<'a, I>(&mut self, nodes: I) -> (usize, usize)
    where
        I: IntoIterator<Item = &'a str>,
    {
        // FxHashSet (not std SipHash): `remove_set` is probed once per adjacency
        // entry (O(|E|) lookups) in the retains below — SipHash on those string
        // keys dominated wall time, so use the fast hasher the rest of the store
        // already uses.
        let remove_set: rustc_hash::FxHashSet<&str> = nodes
            .into_iter()
            .filter(|node| self.nodes.contains_key(*node))
            .collect();
        if remove_set.is_empty() {
            return (0, 0);
        }

        let old_node_count = self.nodes.len();
        let old_edge_count = self.edge_count;

        // br-r37-c1-mgrnf-incident: when removing a SMALL fraction of nodes, the
        // whole-graph retain scans (O(|V|+|E|)) dwarf the actual incident work —
        // removing 10 nodes from a 2000/10000 graph was ~100x slower than nx (which
        // touches only incident edges). Fast path: walk ONLY the removed nodes'
        // adjacency (like `remove_node`), dropping incident edge buckets O(1) and
        // pruning the removed node from each SURVIVING neighbour's row, then compact
        // the two outer maps ONCE. O(|V| + sum_removed_degrees) instead of O(|V|+|E|).
        // Gate on node fraction: for large removals the per-neighbour `shift_remove`
        // can repeat on hub survivors, so fall through to the whole-graph retain.
        let mut removed_instances = 0usize;
        if remove_set.len().saturating_mul(4) <= old_node_count {
            for &rn in &remove_set {
                let neighbor_names: Vec<String> = match self.adjacency.get(rn) {
                    Some(row) => row.keys().cloned().collect(),
                    None => continue,
                };
                for nb in &neighbor_names {
                    // Prune `rn` from a surviving neighbour's row (removed
                    // neighbours' rows are dropped wholesale below). Self-loop
                    // (nb == rn) also skips — the row is being removed.
                    if nb.as_str() != rn
                        && !remove_set.contains(nb.as_str())
                        && let Some(remote) = self.adjacency.get_mut(nb)
                    {
                        remote.shift_remove(rn);
                    }
                    // Drop the shared edge bucket exactly once: swap_remove returns
                    // it only on the first endpoint that reaches it (an (a,b) pair
                    // with both removed is visited twice; the second is a no-op).
                    if let Some(bucket) = self.edges.swap_remove(&EdgeKeyRef::new(rn, nb)) {
                        removed_instances += bucket.len();
                    }
                }
            }
            self.edge_count -= removed_instances;
            self.adjacency
                .retain(|node, _| !remove_set.contains(node.as_str()));
            self.nodes
                .retain(|node, _| !remove_set.contains(node.as_str()));
            let removed_nodes = old_node_count - self.nodes.len();
            let removed_edges = old_edge_count - self.edge_count;
            self.revision = self
                .revision
                .saturating_add(u64::try_from(removed_nodes).unwrap_or(u64::MAX));
            return (removed_nodes, removed_edges);
        }

        // Drop every edge bucket incident to a removed node (either endpoint in
        // `remove_set`) in one pass, tallying the parallel-edge instances so
        // `edge_count` stays exact. The `edges` map order is never observed
        // externally (every consumer walks `edges_ordered`, i.e. adjacency
        // order), so `retain` is order-safe — same rationale as `remove_node`.
        self.edges.retain(|key, bucket| {
            let keep =
                !remove_set.contains(key.left.as_str()) && !remove_set.contains(key.right.as_str());
            if !keep {
                removed_instances += bucket.len();
            }
            keep
        });
        self.edge_count -= removed_instances;

        // Adjacency: drop the removed nodes' own rows, then prune references to
        // removed nodes from every surviving row. Both `retain`s preserve
        // insertion order (IndexMap), so the surviving adjacency is byte-identical
        // to repeated `remove_node`.
        self.adjacency
            .retain(|node, _| !remove_set.contains(node.as_str()));
        for row in self.adjacency.values_mut() {
            row.retain(|neighbor, _| !remove_set.contains(neighbor.as_str()));
        }
        self.nodes
            .retain(|node, _| !remove_set.contains(node.as_str()));

        let removed_nodes = old_node_count - self.nodes.len();
        let removed_edges = old_edge_count - self.edge_count;
        self.revision = self
            .revision
            .saturating_add(u64::try_from(removed_nodes).unwrap_or(u64::MAX));
        (removed_nodes, removed_edges)
    }

    #[must_use]
    pub fn edges_ordered(&self) -> Vec<MultiEdgeSnapshot> {
        // br-r37-c1-thp6w S13: a warm slab shadow serves the identical owned
        // walk — the same S10/S12 emission gates (order, orientation, keys,
        // attrs) that back `edges_ordered_borrowed`, materialized into owned
        // `MultiEdgeSnapshot`s. Stale/absent shadow falls through to the
        // String walk unchanged.
        #[cfg(feature = "mg-int-storage")]
        if let Some(shadow) = self.slab_shadow.as_deref()
            && shadow.0 == self.revision
        {
            return shadow
                .1
                .edges_ordered_borrowed()
                .into_iter()
                .map(|(left, right, key, attrs)| MultiEdgeSnapshot {
                    left: left.to_owned(),
                    right: right.to_owned(),
                    key,
                    attrs: attrs.clone(),
                })
                .collect();
        }
        let mut ordered = Vec::with_capacity(self.edge_count());
        let mut seen = HashSet::<(String, String, usize)>::with_capacity(self.edge_count());

        for node in self.nodes.keys() {
            if let Some(neighbors) = self.adjacency.get(node) {
                for neighbor in neighbors.keys() {
                    let pair = EdgeKeyRef::new(node, neighbor);
                    if let Some(edge_bucket) = self.edges.get(&pair) {
                        for (key, attrs) in edge_bucket {
                            // Track using the canonical sorted pair to deduplicate correctly
                            let canonical_instance =
                                (pair.left.to_owned(), pair.right.to_owned(), *key);
                            if !seen.insert(canonical_instance) {
                                continue;
                            }
                            ordered.push(MultiEdgeSnapshot {
                                left: pair.left.to_owned(),
                                right: pair.right.to_owned(),
                                key: *key,
                                attrs: attrs.clone(),
                            });
                        }
                    }
                }
            }
        }

        ordered
    }

    #[must_use]
    pub fn edges_ordered_borrowed(&self) -> Vec<(&str, &str, usize, &AttrMap)> {
        // br-r37-c1-thp6w S13: a warm slab shadow serves the identical walk
        // (S10/S12 gates: same emission order, orientation, keys, attrs) with
        // usize hashing instead of per-cell String-pair hashing — measured
        // 2.56-2.76x on n=20k m=80k. Stale/absent shadow falls through to the
        // String walk unchanged.
        #[cfg(feature = "mg-int-storage")]
        if let Some(shadow) = self.slab_shadow.as_deref()
            && shadow.0 == self.revision
        {
            return shadow.1.edges_ordered_borrowed();
        }
        let mut ordered = Vec::with_capacity(self.edge_count());
        let mut seen = HashSet::<(EdgeKeyRef, usize)>::with_capacity(self.edge_count());

        for node in self.nodes.keys() {
            if let Some(neighbors) = self.adjacency.get(node) {
                for neighbor in neighbors.keys() {
                    let pair = EdgeKeyRef::new(node, neighbor);
                    if let Some(edge_bucket) = self.edges.get(&pair) {
                        for (key, attrs) in edge_bucket {
                            if !seen.insert((pair, *key)) {
                                continue;
                            }
                            ordered.push((pair.left, pair.right, *key, attrs));
                        }
                    }
                }
            }
        }

        ordered
    }

    /// br-r37-c1-wsize (cc): integer `size(weight)` from the store — the
    /// multigraph twin of `Graph::weighted_size_int`. Each parallel edge is one
    /// bucket entry in `self.edges` and contributes its weight once (size halves
    /// degree's double count); a self-loop key is one stored edge counted once.
    /// Returns `None` on any non-integer weight (caller uses the exact
    /// float/PyObject degree path); missing weight defaults to nx's int `1`.
    #[must_use]
    pub fn weighted_size_int(&self, weight: &str) -> Option<i128> {
        let mut total: i128 = 0;
        for bucket in self.edges.values() {
            for attrs in bucket.values() {
                let value = match attrs.get(weight) {
                    Some(CgseValue::Int(v)) => i128::from(*v),
                    Some(_) => return None,
                    None => 1,
                };
                total = total.checked_add(value)?;
            }
        }
        Some(total)
    }

    #[must_use]
    pub fn edges_ordered_indices_borrowed(&self) -> Vec<(usize, usize, usize, &AttrMap)> {
        // br-r37-c1-thp6w S13: NOT routed through the slab. The slab analog
        // (`MgSlabStorageProto::edges_ordered_indices_borrowed`) is byte-
        // identical but must rebuild an O(n) `slot->position` array per call
        // (positions != slots under recycling, and a sound "slots==positions"
        // check is itself O(n)); that build offsets the String-hash savings to
        // ~parity (measured 0.98-1.02x, ledger 2026-07-24). Retry only with a
        // slab-maintained never-recycled flag that lets the fresh/pristine
        // case emit `slot` directly as `position` and skip the build.
        let mut ordered = Vec::with_capacity(self.edge_count());
        let mut seen = HashSet::<(EdgeKeyRef, usize)>::with_capacity(self.edge_count());

        for (node_idx, node) in self.nodes.keys().enumerate() {
            if let Some(neighbors) = self.adjacency.get(node) {
                for neighbor in neighbors.keys() {
                    let Some(neighbor_idx) = self.nodes.get_index_of(neighbor.as_str()) else {
                        continue;
                    };
                    let pair = EdgeKeyRef::new(node, neighbor);
                    let (left_idx, right_idx) = if pair.left == node.as_str() {
                        (node_idx, neighbor_idx)
                    } else {
                        (neighbor_idx, node_idx)
                    };
                    if let Some(edge_bucket) = self.edges.get(&pair) {
                        for (key, attrs) in edge_bucket {
                            if !seen.insert((pair, *key)) {
                                continue;
                            }
                            ordered.push((left_idx, right_idx, *key, attrs));
                        }
                    }
                }
            }
        }

        ordered
    }

    #[must_use]
    pub fn snapshot(&self) -> MultiGraphSnapshot {
        // br-snapnodeattrs: see Graph::snapshot — same fix for MultiGraph.
        let node_attrs: BTreeMap<String, AttrMap> = self
            .nodes
            .iter()
            .filter(|(_, attrs)| !attrs.is_empty())
            .map(|(name, attrs)| (name.clone(), attrs.clone()))
            .collect();
        MultiGraphSnapshot {
            mode: self.mode,
            nodes: self.nodes.keys().cloned().collect(),
            node_attrs,
            edges: self.edges_ordered(),
        }
    }

    fn remove_adjacency_key(&mut self, source: &str, target: &str, key: usize) {
        let mut drop_neighbor = false;
        if let Some(neighbors) = self.adjacency.get_mut(source)
            && let Some(keys) = neighbors.get_mut(target)
        {
            keys.shift_remove(&key);
            drop_neighbor = keys.is_empty();
        }
        if drop_neighbor && let Some(neighbors) = self.adjacency.get_mut(source) {
            neighbors.shift_remove(target);
        }
    }

    fn record_decision(
        &mut self,
        operation: &'static str,
        incompatibility_probability: f64,
        unknown_incompatible_feature: bool,
        evidence: Vec<EvidenceTerm>,
    ) -> DecisionAction {
        let action = self
            .runtime_policy
            .action_for(incompatibility_probability, unknown_incompatible_feature);
        self.runtime_policy.record(
            operation,
            action,
            incompatibility_probability,
            "argmin expected loss over {allow,full_validate,fail_closed}",
            evidence,
        );
        action
    }
}

#[cfg(test)]
mod tests {
    use super::{AttrMap, Graph, GraphError, MultiGraph};
    use fnx_runtime::{CgseValue, CompatibilityMode, DecisionAction, DecisionRecord};
    use proptest::prelude::*;
    use std::collections::BTreeSet;

    /// br-r37-c1-addedgenewedge parity: the new_edge-gated adjacency push must never create a
    /// duplicate adjacency entry, even under duplicate edges / self-loops / edges added in both
    /// orientations. (The old `!adj_indices[..].contains(..)` guard prevented dups; the O(1)
    /// `new_edge` flag must too, since adj-membership ⟺ edge existence.)
    #[test]
    fn add_edge_newedge_no_duplicate_adjacency() {
        let mut g = Graph::strict();
        let _ = g.add_edge("h", "a");
        let _ = g.add_edge("h", "b");
        let _ = g.add_edge("h", "a"); // exact duplicate
        let _ = g.add_edge("a", "h"); // reversed duplicate
        let _ = g.add_edge("s", "s"); // self-loop
        let _ = g.add_edge("s", "s"); // duplicate self-loop
        let n = g.node_count();
        for i in 0..n {
            if let Some(row) = g.neighbors_indices(i) {
                let uniq: BTreeSet<usize> = row.iter().copied().collect();
                assert_eq!(
                    uniq.len(),
                    row.len(),
                    "node {i} has duplicate adjacency entries"
                );
            }
        }
        // Unique edges: h-a, h-b, s-s.
        assert_eq!(
            g.edge_count(),
            3,
            "duplicate/reversed adds must not create new edges"
        );
    }

    /// br-r37-c1-addedgenewedge: paired-interleaved median A/B for the exact change — building a
    /// high-degree hub's adjacency row. The OLD code guarded each push with
    /// `adj_indices[hub].contains(&x)` (an O(row.len) linear rescan → O(n²) to build a star via
    /// add_edge); the NEW code pushes on the O(1) `new_edge` flag → O(n). This isolates the two
    /// changed lines; the rest of add_edge is O(1)/edge in both arms (so the full-function win is
    /// this, diluted by that per-edge overhead). `#[ignore]`; run with
    /// `cargo test --release -p fnx-classes --lib add_edge_newedge_ab -- --ignored --nocapture`.
    #[test]
    #[ignore = "measurement; run with --release --ignored --nocapture"]
    fn add_edge_newedge_ab() {
        use std::hint::black_box;
        use std::time::Instant;

        let n = 40000usize;
        let time = |use_new: bool| -> f64 {
            let t0 = Instant::now();
            let mut row: Vec<usize> = Vec::with_capacity(n);
            for i in 0..n {
                if use_new {
                    row.push(i);
                } else if !row.contains(&i) {
                    row.push(i);
                }
            }
            black_box(&row);
            t0.elapsed().as_secs_f64()
        };
        for _ in 0..2 {
            black_box(time(true));
            black_box(time(false));
        }
        let median = |v: &[f64]| {
            let mut s = v.to_vec();
            s.sort_by(|a, b| a.partial_cmp(b).unwrap());
            s[s.len() / 2]
        };
        let rounds = 41usize;
        let paired = |cand: bool, base: bool| -> Vec<f64> {
            let mut v = Vec::with_capacity(rounds);
            for r in 0..rounds {
                let (tb, tc) = if r % 2 == 0 {
                    let b = time(base);
                    let c = time(cand);
                    (b, c)
                } else {
                    let c = time(cand);
                    let b = time(base);
                    (b, c)
                };
                v.push(tb / tc);
            }
            v
        };
        let report = |name: &str, ratios: &[f64]| {
            let wins = ratios.iter().filter(|&&r| r > 1.0).count();
            let mut sorted = ratios.to_vec();
            sorted.sort_by(|a, b| a.partial_cmp(b).unwrap());
            println!(
                "ADDEDGE_AB {name}: median={:.4}x win_rate={wins}/{rounds} p5_p95=[{:.4},{:.4}]",
                median(ratios),
                sorted[rounds * 5 / 100],
                sorted[rounds * 95 / 100],
            );
        };
        println!("ADDEDGE_AB adj-row push n={n} rounds={rounds} (>1 = new_edge-flag faster)");
        report("NEWEDGE_vs_contains", &paired(true, false));
        report("NULL_new_vs_new", &paired(true, true));
    }

    /// br-r37-c1-degselfloopidx: parity + paired-interleaved A/B for `degree_by_index` — the O(1)
    /// `has_edge_by_indices(idx,idx)` self-loop check vs the pre-lever O(degree)
    /// `adj_indices[idx].contains(&idx)` rescan, over a degree histogram of a dense graph. Byte-exact
    /// parity (also vs the `&str` `degree`). `#[ignore]`; run with
    /// `cargo test --release -p fnx-classes --lib degree_by_index_selfloop_ab -- --ignored --nocapture`.
    #[test]
    #[ignore = "measurement; run with --release --ignored --nocapture"]
    fn degree_by_index_selfloop_ab() {
        use std::hint::black_box;
        use std::time::Instant;

        let n = 20000usize;
        let deg = 20usize;
        let mut g = Graph::strict();
        for i in 0..n {
            let _ = g.add_node(format!("n{i}"));
        }
        for i in 0..n {
            for step in 1..=deg {
                let _ = g.add_edge(format!("n{i}"), format!("n{}", (i + step) % n));
            }
        }
        for i in (0..n).step_by(1000) {
            let _ = g.add_edge(format!("n{i}"), format!("n{i}"));
        }

        // Byte-exact parity: new == old (row.contains) == the &str degree, incl. self-loop nodes.
        for idx in 0..g.node_count() {
            let new = g.degree_by_index(idx);
            let old = g.adj_indices[idx].len() + usize::from(g.adj_indices[idx].contains(&idx));
            assert_eq!(new, old, "degree_by_index parity vs row.contains at {idx}");
            assert_eq!(
                new,
                g.degree(&format!("n{idx}")),
                "degree_by_index parity vs &str degree at {idx}"
            );
        }

        let time = |use_new: bool| -> f64 {
            let t0 = Instant::now();
            let mut sum = 0usize;
            for idx in 0..g.node_count() {
                sum += if use_new {
                    g.degree_by_index(idx)
                } else {
                    g.adj_indices[idx].len() + usize::from(g.adj_indices[idx].contains(&idx))
                };
            }
            black_box(sum);
            t0.elapsed().as_secs_f64()
        };
        for _ in 0..3 {
            black_box(time(true));
            black_box(time(false));
        }
        let median = |v: &[f64]| {
            let mut s = v.to_vec();
            s.sort_by(|a, b| a.partial_cmp(b).unwrap());
            s[s.len() / 2]
        };
        let rounds = 41usize;
        let paired = |cand: bool, base: bool| -> Vec<f64> {
            let mut v = Vec::with_capacity(rounds);
            for r in 0..rounds {
                let (tb, tc) = if r % 2 == 0 {
                    let b = time(base);
                    let c = time(cand);
                    (b, c)
                } else {
                    let c = time(cand);
                    let b = time(base);
                    (b, c)
                };
                v.push(tb / tc);
            }
            v
        };
        let report = |name: &str, ratios: &[f64]| {
            let wins = ratios.iter().filter(|&&r| r > 1.0).count();
            let mut sorted = ratios.to_vec();
            sorted.sort_by(|a, b| a.partial_cmp(b).unwrap());
            println!(
                "DEGIDX_AB {name}: median={:.4}x win_rate={wins}/{rounds} p5_p95=[{:.4},{:.4}]",
                median(ratios),
                sorted[rounds * 5 / 100],
                sorted[rounds * 95 / 100],
            );
        };
        println!(
            "DEGIDX_AB degree histogram n={n} deg={deg} rounds={rounds} (>1 = O(1) has_edge faster)"
        );
        report("HASEDGE_vs_contains", &paired(true, false));
        report("NULL_new_vs_new", &paired(true, true));
    }

    /// br-r37-c1-isoedgecount: paired-interleaved A/B for the graph-isomorphism early-out edge
    /// count check. `undirected_isomorphism_mappings` / `directed_isomorphism_mappings` (fnx-python,
    /// reached by public `is_isomorphic`) compared edge COUNTS via `edges_ordered().len()`, which
    /// materialises a full `Vec<EdgeSnapshot>` (two owned Strings per edge) only to read its length;
    /// the O(1) `edge_count()` (== `self.edges.len()`) is byte-identical. This times the exact
    /// early-out compare on the non-isomorphic same-node / different-edge case (where the check is
    /// the dominant cost). Byte-exact parity asserted (`edge_count() == edges_ordered().len()`).
    /// `#[ignore]`; run with
    /// `cargo test --release -p fnx-classes --lib iso_edge_count_ab -- --ignored --nocapture`.
    #[test]
    #[ignore = "measurement; run with --release --ignored --nocapture"]
    fn iso_edge_count_ab() {
        use std::hint::black_box;
        use std::time::Instant;

        let n = 4000usize;
        let deg = 25usize;
        let build = |steps: usize| -> Graph {
            let mut g = Graph::strict();
            for i in 0..n {
                let _ = g.add_node(format!("n{i}"));
            }
            for i in 0..n {
                for step in 1..=steps {
                    let _ = g.add_edge(format!("n{i}"), format!("n{}", (i + step) % n));
                }
            }
            g
        };
        // Same node count, DIFFERENT edge count → the early-out returns at the edge-count compare.
        let g1 = build(deg);
        let g2 = build(deg - 1);

        // Byte-exact parity: edge_count() must equal edges_ordered().len() for both graphs.
        assert_eq!(
            g1.edge_count(),
            g1.edges_ordered().len(),
            "edge_count parity g1"
        );
        assert_eq!(
            g2.edge_count(),
            g2.edges_ordered().len(),
            "edge_count parity g2"
        );
        assert_ne!(
            g1.edge_count(),
            g2.edge_count(),
            "workload must exercise the differing-count early-out"
        );

        let time = |use_new: bool| -> f64 {
            let t0 = Instant::now();
            let mut acc = 0usize;
            for _ in 0..8 {
                let differ = if use_new {
                    g1.edge_count() != g2.edge_count()
                } else {
                    g1.edges_ordered().len() != g2.edges_ordered().len()
                };
                acc += usize::from(differ);
            }
            black_box(acc);
            t0.elapsed().as_secs_f64()
        };
        for _ in 0..3 {
            black_box(time(true));
            black_box(time(false));
        }
        let median = |v: &[f64]| {
            let mut s = v.to_vec();
            s.sort_by(|a, b| a.partial_cmp(b).unwrap());
            s[s.len() / 2]
        };
        let rounds = 41usize;
        let paired = |cand: bool, base: bool| -> Vec<f64> {
            let mut v = Vec::with_capacity(rounds);
            for r in 0..rounds {
                let (tb, tc) = if r % 2 == 0 {
                    let b = time(base);
                    let c = time(cand);
                    (b, c)
                } else {
                    let c = time(cand);
                    let b = time(base);
                    (b, c)
                };
                v.push(tb / tc);
            }
            v
        };
        let report = |name: &str, ratios: &[f64]| {
            let wins = ratios.iter().filter(|&&r| r > 1.0).count();
            let mut sorted = ratios.to_vec();
            sorted.sort_by(|a, b| a.partial_cmp(b).unwrap());
            println!(
                "ISOEDGE_AB {name}: median={:.4}x win_rate={wins}/{rounds} p5_p95=[{:.4},{:.4}]",
                median(ratios),
                sorted[rounds * 5 / 100],
                sorted[rounds * 95 / 100],
            );
        };
        println!(
            "ISOEDGE_AB same-node/different-edge early-out n={n} deg={deg} rounds={rounds} (>1 = edge_count faster)"
        );
        report("EDGECOUNT_vs_edgesordered", &paired(true, false));
        report("NULL_new_vs_new", &paired(true, true));
    }

    /// br-r37-c1-selfloopidx: paired-interleaved A/B for the `nodes_with_selfloops` per-node self-loop
    /// probe (feeds `number_of_selfloops` / `selfloop_edges` / `nodes_with_selfloops`, many callers).
    /// The kernel checked `has_edge(node, node)` — resolving BOTH `&str` endpoints via
    /// `edge_pair_key` (two String-hash lookups per node) — vs the index probe
    /// `has_edge_by_indices(i, i)` (a direct integer `canon_pair` + `contains_key`, no String
    /// resolution). Byte-exact parity asserted (same self-loop node set). `#[ignore]`; run with
    /// `cargo test --release -p fnx-classes --lib nodes_selfloop_idx_ab -- --ignored --nocapture`.
    #[test]
    #[ignore = "measurement; run with --release --ignored --nocapture"]
    fn nodes_selfloop_idx_ab() {
        use std::hint::black_box;
        use std::time::Instant;

        // 40k nodes, ring-of-chords, NO self-loops (the common case: every node is probed and misses).
        let n = 40_000usize;
        let deg = 10usize;
        let mut g = Graph::strict();
        for i in 0..n {
            let _ = g.add_node(i.to_string());
        }
        for i in 0..n {
            for step in 1..=deg {
                let _ = g.add_edge(i.to_string(), ((i + step) % n).to_string());
            }
        }

        let names = g.nodes_ordered();
        let old_scan =
            |g: &Graph| -> usize { names.iter().filter(|&&node| g.has_edge(node, node)).count() };
        let new_scan = |g: &Graph| -> usize {
            (0..names.len())
                .filter(|&i| g.has_edge_by_indices(i, i))
                .count()
        };
        assert_eq!(
            old_scan(&g),
            new_scan(&g),
            "nodes_with_selfloops parity (self-loop count)"
        );

        let time = |cand: bool| -> f64 {
            let t0 = Instant::now();
            let c = if cand { new_scan(&g) } else { old_scan(&g) };
            black_box(c);
            t0.elapsed().as_secs_f64()
        };
        for _ in 0..3 {
            black_box(time(true));
            black_box(time(false));
        }
        let median = |v: &[f64]| {
            let mut s = v.to_vec();
            s.sort_by(|a, b| a.partial_cmp(b).unwrap());
            s[s.len() / 2]
        };
        let rounds = 61usize;
        let paired = |cand: bool, base: bool| -> Vec<f64> {
            let mut v = Vec::with_capacity(rounds);
            for r in 0..rounds {
                let (tb, tc) = if r % 2 == 0 {
                    let b = time(base);
                    let c = time(cand);
                    (b, c)
                } else {
                    let c = time(cand);
                    let b = time(base);
                    (b, c)
                };
                v.push(tb / tc);
            }
            v
        };
        let report = |name: &str, ratios: &[f64]| {
            let wins = ratios.iter().filter(|&&r| r > 1.0).count();
            let mut sorted = ratios.to_vec();
            sorted.sort_by(|a, b| a.partial_cmp(b).unwrap());
            println!(
                "SELFLOOPIDX_AB {name}: median={:.4}x win_rate={wins}/{rounds} p5_p95=[{:.4},{:.4}]",
                median(ratios),
                sorted[rounds * 5 / 100],
                sorted[rounds * 95 / 100],
            );
        };
        println!(
            "SELFLOOPIDX_AB nodes_with_selfloops n={n} deg={deg} rounds={rounds} (>1 = index probe faster)"
        );
        report("HASEDGEIDX_vs_hasedge", &paired(true, false));
        report("NULL_new_vs_new", &paired(true, true));
    }

    /// br-r37-c1-numselfidx: paired-interleaved A/B for `number_of_selfloops` (feeds the is_planar
    /// dense-graph `planarity_euler_reject` fast path). The kernel counted self-loops with
    /// `edges_ordered().filter(|e| e.left == e.right).count()` — materialising a full
    /// `Vec<EdgeSnapshot>` (two owned Strings + an attr clone PER edge) — vs the integer per-node
    /// probe `(0..n).filter(|i| has_edge_by_indices(i, i)).count()` (no allocation). Byte-exact parity
    /// asserted (same self-loop count). `#[ignore]`; run with
    /// `cargo test --release -p fnx-classes --lib number_of_selfloops_idx_ab -- --ignored --nocapture`.
    #[test]
    #[ignore = "measurement; run with --release --ignored --nocapture"]
    fn number_of_selfloops_idx_ab() {
        use std::hint::black_box;
        use std::time::Instant;

        // Dense-ish ring-of-chords, ~20k nodes * 20 = ~200k edges, no self-loops (the count is 0 and
        // the old arm materialises the whole edge Vec anyway).
        let n = 20_000usize;
        let deg = 20usize;
        let mut g = Graph::strict();
        for i in 0..n {
            let _ = g.add_node(i.to_string());
        }
        for i in 0..n {
            for step in 1..=deg {
                let _ = g.add_edge(i.to_string(), ((i + step) % n).to_string());
            }
        }

        let old_count = |g: &Graph| -> usize {
            g.edges_ordered()
                .iter()
                .filter(|e| e.left == e.right)
                .count()
        };
        let new_count = |g: &Graph| -> usize {
            (0..g.node_count())
                .filter(|&i| g.has_edge_by_indices(i, i))
                .count()
        };
        assert_eq!(old_count(&g), new_count(&g), "number_of_selfloops parity");

        let time = |cand: bool| -> f64 {
            let t0 = Instant::now();
            let c = if cand { new_count(&g) } else { old_count(&g) };
            black_box(c);
            t0.elapsed().as_secs_f64()
        };
        for _ in 0..3 {
            black_box(time(true));
            black_box(time(false));
        }
        let median = |v: &[f64]| {
            let mut s = v.to_vec();
            s.sort_by(|a, b| a.partial_cmp(b).unwrap());
            s[s.len() / 2]
        };
        let rounds = 61usize;
        let paired = |cand: bool, base: bool| -> Vec<f64> {
            let mut v = Vec::with_capacity(rounds);
            for r in 0..rounds {
                let (tb, tc) = if r % 2 == 0 {
                    let b = time(base);
                    let c = time(cand);
                    (b, c)
                } else {
                    let c = time(cand);
                    let b = time(base);
                    (b, c)
                };
                v.push(tb / tc);
            }
            v
        };
        let report = |name: &str, ratios: &[f64]| {
            let wins = ratios.iter().filter(|&&r| r > 1.0).count();
            let mut sorted = ratios.to_vec();
            sorted.sort_by(|a, b| a.partial_cmp(b).unwrap());
            println!(
                "NUMSELFIDX_AB {name}: median={:.4}x win_rate={wins}/{rounds} p5_p95=[{:.4},{:.4}]",
                median(ratios),
                sorted[rounds * 5 / 100],
                sorted[rounds * 95 / 100],
            );
        };
        println!(
            "NUMSELFIDX_AB number_of_selfloops n={n} deg={deg} rounds={rounds} (>1 = index count faster)"
        );
        report("INDEXCOUNT_vs_edgesordered", &paired(true, false));
        report("NULL_new_vs_new", &paired(true, true));
    }

    /// br-r37-c1-kneserpush parity: removing the redundant `adj_indices.contains` guards under the
    /// `seen.insert(pair)` new-pair guard must keep the Kneser build byte-identical — correct
    /// node/edge counts and NO duplicate adjacency entries. (Same lever + adj_indices.push operation
    /// as br-r37-c1-addedgenewedge, whose A/B measured the O(degree)→O(1) win.)
    #[test]
    fn kneser_push_no_duplicate_adjacency() {
        // Kneser(10,3): C(10,3)=120 nodes, degree C(7,3)=35, edges = 120*35/2 = 2100.
        let g = Graph::kneser(CompatibilityMode::Strict, 10, 3);
        assert_eq!(g.node_count(), 120, "C(10,3) nodes");
        assert_eq!(g.edge_count(), 2100, "120*35/2 Kneser edges");
        let mut total_deg = 0usize;
        for i in 0..g.node_count() {
            let row = &g.adj_indices[i];
            let uniq: BTreeSet<usize> = row.iter().copied().collect();
            assert_eq!(
                uniq.len(),
                row.len(),
                "node {i} has duplicate adjacency entries"
            );
            assert_eq!(row.len(), 35, "Kneser(10,3) is 35-regular");
            total_deg += row.len();
        }
        assert_eq!(total_deg, 2 * 2100, "handshake: sum of degrees == 2|E|");
    }

    fn node_name(id: u8) -> String {
        format!("n{}", id % 8)
    }

    fn canonical_edge(left: &str, right: &str) -> (String, String) {
        if left <= right {
            (left.to_owned(), right.to_owned())
        } else {
            (right.to_owned(), left.to_owned())
        }
    }

    /// br-r37-c1-thp6w slice 1 INVARIANT: the cached integer adjacency
    /// (`with_int_adjacency`) must equal, byte-for-byte, a fresh derivation from the
    /// authoritative String `adjacency` — row `i` == `[get_node_index(v) for v in
    /// neighbors_iter(node_i)]` — for the CURRENT graph state. Because the memo is keyed on
    /// `revision` + explicitly cleared by `apply_row_orders`, calling this after a mutation
    /// (with a prior populating read) catches any mutation path that fails to invalidate.
    fn assert_int_adjacency_matches(g: &MultiGraph) {
        let expected: Vec<Vec<usize>> = g
            .nodes_ordered()
            .iter()
            .map(|name| {
                g.neighbors_iter(name).map_or_else(Vec::new, |it| {
                    it.map(|v| g.get_node_index(v).unwrap()).collect()
                })
            })
            .collect();
        g.with_int_adjacency(|adj| {
            assert_eq!(
                adj,
                expected.as_slice(),
                "int adjacency must mirror the String adjacency exactly"
            );
        });
    }

    #[test]
    fn thp6w_int_adjacency_invariant_across_mutations() {
        let mut g = MultiGraph::strict();
        for i in 0..8 {
            g.add_node(format!("n{i}"));
        }
        // Edges incl. parallels and a self-loop.
        let _ = g.add_edge("n0", "n1");
        let _ = g.add_edge("n0", "n1"); // parallel
        let _ = g.add_edge("n1", "n2");
        let _ = g.add_edge("n2", "n3");
        let _ = g.add_edge("n3", "n0");
        let _ = g.add_edge("n4", "n4"); // self-loop
        let _ = g.add_edge("n5", "n6");
        // Populate the memo, then verify.
        assert_int_adjacency_matches(&g);

        // read-mutate-read for EACH mutation kind: a stale memo would fail the re-check.
        // add_node
        assert_int_adjacency_matches(&g);
        g.add_node("n9");
        assert_int_adjacency_matches(&g);
        // add_edge (new neighbor -> row grows)
        assert_int_adjacency_matches(&g);
        let _ = g.add_edge("n9", "n0");
        assert_int_adjacency_matches(&g);
        // parallel add_edge (row unchanged, content bumps revision)
        assert_int_adjacency_matches(&g);
        let _ = g.add_edge("n9", "n0");
        assert_int_adjacency_matches(&g);
        // remove one parallel edge (row must stay; neighbor still present)
        assert_int_adjacency_matches(&g);
        assert!(g.remove_edge("n0", "n1", None));
        assert_int_adjacency_matches(&g);
        // remove last edge of a pair (neighbor drops from both rows)
        assert_int_adjacency_matches(&g);
        assert!(g.remove_edge("n5", "n6", None));
        assert_int_adjacency_matches(&g);
        // remove_node (renumber: indices shift down)
        assert_int_adjacency_matches(&g);
        assert!(g.remove_node("n2"));
        assert_int_adjacency_matches(&g);
        // ORDER-ONLY change via the copy walk reorder (does NOT bump revision — the
        // apply_row_orders cache-clear is what keeps this correct).
        assert_int_adjacency_matches(&g);
        g.reorder_rows_for_nx_copy_walk();
        assert_int_adjacency_matches(&g);
        // clear_edges
        assert_int_adjacency_matches(&g);
        g.clear_edges();
        assert_int_adjacency_matches(&g);
    }

    /// br-r37-c1-thp6w S4: the memo is keyed at the CURRENT revision without any
    /// intervening read — i.e. the mutation advanced it in place rather than
    /// leaving it stale for the next `with_int_adjacency` rebuild.
    fn int_adj_memo_is_warm(g: &MultiGraph) -> bool {
        g.int_adj_cache
            .0
            .read()
            .expect("int_adj_cache poisoned")
            .as_ref()
            .is_some_and(|(rev, _)| *rev == g.revision)
    }

    /// br-r37-c1-thp6w S4 INVARIANT: single-edge `add_edge`/`remove_edge` must
    /// ADVANCE a warm integer-adjacency memo across the mutation (no rebuild),
    /// and the advanced rows must equal a fresh derivation from the String
    /// adjacency after every step. Unhandled mutation kinds (`remove_node`)
    /// must still leave the memo stale so the lazy rebuild path takes over.
    #[test]
    fn thp6w_s4_single_edge_mutations_advance_warm_memo() {
        let mut g = MultiGraph::strict();
        let _ = g.add_edge("a", "b");
        assert_int_adjacency_matches(&g); // populate the memo

        // new neighbor with an auto-created right endpoint
        let _ = g.add_edge("b", "c");
        assert!(
            int_adj_memo_is_warm(&g),
            "add_edge must advance, not invalidate"
        );
        assert_int_adjacency_matches(&g);
        // both endpoints auto-created
        let _ = g.add_edge("d", "e");
        assert!(int_adj_memo_is_warm(&g));
        assert_int_adjacency_matches(&g);
        // self-loop on an auto-created node
        let _ = g.add_edge("f", "f");
        assert!(int_adj_memo_is_warm(&g));
        assert_int_adjacency_matches(&g);
        // parallel edge: rows unchanged, revision bumps -> re-key only
        let _ = g.add_edge("a", "b");
        assert!(int_adj_memo_is_warm(&g));
        assert_int_adjacency_matches(&g);
        // attr-only change on an existing key: rows unchanged, revision bumps
        let mut attrs = AttrMap::new();
        attrs.insert("w".to_owned(), fnx_runtime::CgseValue::Int(2));
        let _ = g.add_edge_with_key_and_attrs("a", "b", 0, attrs);
        assert!(int_adj_memo_is_warm(&g));
        assert_int_adjacency_matches(&g);
        // remove one parallel key (pair survives -> rows unchanged)
        assert!(g.remove_edge("a", "b", None));
        assert!(int_adj_memo_is_warm(&g));
        assert_int_adjacency_matches(&g);
        // remove the last key (pair gone -> shift-remove mirrored in the rows)
        assert!(g.remove_edge("a", "b", None));
        assert!(int_adj_memo_is_warm(&g));
        assert_int_adjacency_matches(&g);
        // order-sensitive middle-of-row removal: row b = [a-gone..., c, ...]; build
        // b->x, b->y then drop (b,c) so the survivors must keep String-row order.
        let _ = g.add_edge("b", "x");
        let _ = g.add_edge("b", "y");
        assert!(g.remove_edge("b", "c", None));
        assert!(int_adj_memo_is_warm(&g));
        assert_int_adjacency_matches(&g);
        // self-loop removal
        assert!(g.remove_edge("f", "f", None));
        assert!(int_adj_memo_is_warm(&g));
        assert_int_adjacency_matches(&g);
        // unhandled mutation kind: remove_node renumbers -> memo must go stale
        assert!(g.remove_node("x"));
        assert!(
            !int_adj_memo_is_warm(&g),
            "remove_node stays invalidate-only; a warm memo here would serve stale indices"
        );
        assert_int_adjacency_matches(&g);
    }

    /// br-r37-c1-thp6w S5 PARITY GATES: the index-keyed prototype must derive
    /// byte-identical observable orderings (node order, per-row distinct-
    /// neighbor order, per-pair parallel-key order) and identical edge count +
    /// merged attrs from the same insert stream as the real String-keyed
    /// MultiGraph batch path. The stream deliberately includes names where
    /// String-lex and index canonicalization DIVERGE ("10" < "2" lex, 2 < 10
    /// numeric), reversed re-adds, self-loops, sparse explicit keys, dup
    /// (pair, key) attr merges, and late out-of-order node introduction.
    #[test]
    fn thp6w_s5_int_storage_proto_parity_gates() {
        use super::mg_int_storage_proto::MgIntStorageProto;

        let stream: Vec<(&str, &str, usize)> = vec![
            ("2", "10", 0),
            ("10", "2", 1), // reversed orientation, same pair, next key
            ("1", "1", 0),  // self-loop on a fresh node
            ("2", "3", 0),
            ("3", "2", 0), // dup (pair, key) from the reverse orientation -> attr merge
            ("10", "1", 5), // sparse explicit key
            ("0", "2", 0), // node "0" introduced late (insertion order != numeric)
            ("2", "10", 1), // dup (pair, key) again -> attr merge
            ("4", "5", 2),
            ("5", "4", 0), // parallel keys, both orientations
            ("1", "1", 1), // parallel self-loop key
        ];
        let attrs_for = |i: usize| {
            let mut attrs = AttrMap::new();
            attrs.insert(
                format!("a{}", i % 3),
                fnx_runtime::CgseValue::Int(i64::try_from(i).unwrap()),
            );
            attrs
        };

        let mut mg = MultiGraph::strict();
        let _ = mg.extend_keyed_edges_with_attrs_unrecorded(
            stream
                .iter()
                .enumerate()
                .map(|(i, (l, r, k))| ((*l).to_owned(), (*r).to_owned(), *k, attrs_for(i))),
        );
        let mut proto = MgIntStorageProto::new();
        for (i, (l, r, k)) in stream.iter().enumerate() {
            proto.add_keyed_edge(l, r, *k, attrs_for(i));
        }
        // br-r37-c1-thp6w S6: the compact-bucket variant must pass the same gates.
        let mut compact = super::mg_int_storage_proto::MgIntStorageProtoCompact::new();
        for (i, (l, r, k)) in stream.iter().enumerate() {
            compact.add_keyed_edge(l, r, *k, attrs_for(i));
        }

        // Gate 1: node insertion order.
        assert_eq!(
            proto
                .node_names
                .iter()
                .map(String::as_str)
                .collect::<Vec<_>>(),
            mg.nodes_ordered(),
            "node order must match"
        );
        assert_eq!(
            compact
                .node_names
                .iter()
                .map(String::as_str)
                .collect::<Vec<_>>(),
            mg.nodes_ordered(),
            "compact node order must match"
        );
        // Gate 2 + 3: per-row distinct-neighbor order and per-pair key order.
        for (i, name) in mg.nodes_ordered().iter().enumerate() {
            let mg_row: Vec<&str> = mg
                .neighbors_iter(name)
                .map_or_else(Vec::new, Iterator::collect);
            assert_eq!(proto.neighbor_names(i), mg_row, "row order for node {name}");
            assert_eq!(
                compact.neighbor_names(i),
                mg_row,
                "compact row order for node {name}"
            );
            for v in &mg_row {
                assert_eq!(
                    proto.key_order(name, v),
                    mg.edge_keys_vec(name, v),
                    "key order for pair ({name}, {v})"
                );
                assert_eq!(
                    compact.key_order(name, v),
                    mg.edge_keys_vec(name, v),
                    "compact key order for pair ({name}, {v})"
                );
            }
        }
        // Gate 4: edge count.
        assert_eq!(proto.edge_count, mg.edge_count(), "edge_count must match");
        assert_eq!(
            compact.edge_count,
            mg.edge_count(),
            "compact edge_count must match"
        );
        // Gate 5: merged attrs on a dup-inserted cell ((2,10) key 1 saw inserts
        // at stream positions 1 and 7 -> extend semantics on both sides).
        let (Some(&l), Some(&r)) = (proto.node_index.get("2"), proto.node_index.get("10")) else {
            panic!("proto lost nodes");
        };
        let proto_attrs = proto.edges[&(l.min(r), l.max(r))]
            .get(&1)
            .expect("proto (2,10,1) cell");
        assert_eq!(
            Some(proto_attrs),
            mg.edge_attrs("2", "10", 1),
            "merged attrs on the dup (pair, key) cell must match"
        );
        assert_eq!(
            compact.edges[&(l.min(r), l.max(r))].attrs_for(1),
            mg.edge_attrs("2", "10", 1),
            "compact merged attrs on the dup (pair, key) cell must match"
        );
    }

    /// br-r37-c1-thp6w S7 helper: full observable-order parity between the
    /// real MultiGraph and the index-keyed prototype, plus the prototype's own
    /// name->index consistency (the renumber invariant).
    fn assert_proto_matches_mg(
        mg: &MultiGraph,
        proto: &super::mg_int_storage_proto::MgIntStorageProto,
    ) {
        assert_eq!(
            proto
                .node_names
                .iter()
                .map(String::as_str)
                .collect::<Vec<_>>(),
            mg.nodes_ordered(),
            "node order"
        );
        for (i, name) in proto.node_names.iter().enumerate() {
            assert_eq!(
                proto.node_index.get(name),
                Some(&i),
                "node_index desync for {name}"
            );
        }
        for (i, name) in mg.nodes_ordered().iter().enumerate() {
            let mg_row: Vec<&str> = mg
                .neighbors_iter(name)
                .map_or_else(Vec::new, Iterator::collect);
            assert_eq!(proto.neighbor_names(i), mg_row, "row order for {name}");
            for v in &mg_row {
                assert_eq!(
                    proto.key_order(name, v),
                    mg.edge_keys_vec(name, v),
                    "key order for ({name}, {v})"
                );
            }
        }
        assert_eq!(proto.edge_count, mg.edge_count(), "edge_count");
    }

    /// br-r37-c1-thp6w S7 PARITY GAUNTLET (removal + renumber): the epoch's
    /// riskiest semantics — `remove_edge` shift/`next_back` behavior and the
    /// `remove_node` index renumber — must keep every observable ordering
    /// byte-identical to the real String-keyed MultiGraph after EVERY step,
    /// including re-adds AFTER a renumber (stale-index detection).
    #[test]
    fn thp6w_s7_removal_renumber_parity_gauntlet() {
        use super::mg_int_storage_proto::MgIntStorageProto;

        let stream: Vec<(&str, &str, usize)> = vec![
            ("2", "10", 0),
            ("10", "2", 1),
            ("1", "1", 0),
            ("2", "3", 0),
            ("3", "2", 0),
            ("10", "1", 5),
            ("0", "2", 0),
            ("2", "10", 1),
            ("4", "5", 2),
            ("5", "4", 0),
            ("1", "1", 1),
        ];
        let mut mg = MultiGraph::strict();
        let _ = mg.extend_keyed_edges_with_attrs_unrecorded(
            stream
                .iter()
                .map(|(l, r, k)| ((*l).to_owned(), (*r).to_owned(), *k, AttrMap::new())),
        );
        let mut proto = MgIntStorageProto::new();
        for (l, r, k) in &stream {
            proto.add_keyed_edge(l, r, *k, AttrMap::new());
        }
        assert_proto_matches_mg(&mg, &proto);

        // key=None must pick the LAST bucket key (next_back): (4,5) keys are
        // [2, 0] in insertion order -> removes 0, survivor [2].
        assert_eq!(
            mg.remove_edge("4", "5", None),
            proto.remove_edge("4", "5", None)
        );
        assert_proto_matches_mg(&mg, &proto);
        // Partial removal of a parallel bundle: survivor key order preserved.
        assert_eq!(
            mg.remove_edge("2", "10", Some(0)),
            proto.remove_edge("2", "10", Some(0))
        );
        assert_proto_matches_mg(&mg, &proto);
        // Last key of the pair -> neighbor cell drops from both rows.
        assert_eq!(
            mg.remove_edge("2", "10", None),
            proto.remove_edge("2", "10", None)
        );
        assert_proto_matches_mg(&mg, &proto);
        // Self-loop partial removal.
        assert_eq!(
            mg.remove_edge("1", "1", Some(0)),
            proto.remove_edge("1", "1", Some(0))
        );
        assert_proto_matches_mg(&mg, &proto);
        // Missing pair / missing key: both sides must refuse identically.
        assert_eq!(
            mg.remove_edge("0", "10", None),
            proto.remove_edge("0", "10", None)
        );
        assert_eq!(
            mg.remove_edge("2", "3", Some(9)),
            proto.remove_edge("2", "3", Some(9))
        );
        assert_proto_matches_mg(&mg, &proto);

        // THE renumber: remove a mid-order node with live edges.
        assert_eq!(mg.remove_node("2"), proto.remove_node("2"));
        assert_proto_matches_mg(&mg, &proto);
        // Re-adds AFTER the renumber: fresh node + edges into shifted indices.
        mg.extend_keyed_edges_with_attrs_unrecorded(vec![
            ("3".to_owned(), "99".to_owned(), 0, AttrMap::new()),
            ("0".to_owned(), "3".to_owned(), 0, AttrMap::new()),
        ]);
        proto.add_keyed_edge("3", "99", 0, AttrMap::new());
        proto.add_keyed_edge("0", "3", 0, AttrMap::new());
        assert_proto_matches_mg(&mg, &proto);
        // Renumber again from the other end, then the self-loop node.
        assert_eq!(mg.remove_node("10"), proto.remove_node("10"));
        assert_proto_matches_mg(&mg, &proto);
        assert_eq!(mg.remove_node("1"), proto.remove_node("1"));
        assert_proto_matches_mg(&mg, &proto);
        // Removing a missing node refuses identically.
        assert_eq!(mg.remove_node("2"), proto.remove_node("2"));
        assert_proto_matches_mg(&mg, &proto);
    }

    /// br-r37-c1-thp6w S8 A/B: the flip's COST side — `remove_node` under the
    /// index layout pays the d58s8 positional renumber (O(V+E) per removal:
    /// row drop+decrement passes + full edges-map rebuild) where the current
    /// String store pays only O(V + degree) (shift_remove memmoves, no edge
    /// rekey). Same build stream, same 200-name removal sequence, removal
    /// phase timed alone, paired-interleaved with a null arm. This number
    /// decides whether the real flip needs the slab/stable-slot + tombstone
    /// node store (see the bead's S8 design note) instead of positional
    /// renumber.
    /// `cargo test --release -p fnx-classes --lib thp6w_s8_removal_cost_ab -- --ignored --nocapture`
    #[test]
    #[ignore = "paired A/B benchmark; run --release with --ignored --nocapture"]
    fn thp6w_s8_removal_cost_ab() {
        use super::mg_int_storage_proto::MgIntStorageProto;
        use std::collections::HashMap;
        use std::hint::black_box;
        use std::time::Instant;

        fn push_edge(
            stream: &mut Vec<(usize, usize, usize)>,
            key_counter: &mut HashMap<(usize, usize), usize>,
            u: usize,
            v: usize,
        ) {
            let entry = key_counter.entry((u.min(v), u.max(v))).or_insert(0);
            stream.push((u, v, *entry));
            *entry += 1;
        }

        let n = 20000usize;
        let mut stream = Vec::new();
        let mut key_counter = HashMap::new();
        for i in 0..n {
            push_edge(&mut stream, &mut key_counter, i, (i + 1) % n);
        }
        let mut state = 0x2545_F491_4F6C_DD1D_u64;
        let draw = |state: &mut u64| -> usize {
            *state = state
                .wrapping_mul(6_364_136_223_846_793_005)
                .wrapping_add(1_442_695_040_888_963_407);
            usize::try_from(*state >> 33).unwrap() % n
        };
        for _ in 0..3 * n {
            let u = draw(&mut state);
            let v = draw(&mut state);
            push_edge(&mut stream, &mut key_counter, u, v);
        }
        let victims: Vec<String> = (0..n).step_by(100).map(|i| i.to_string()).collect();

        let time_current_removals = |stream: &[(usize, usize, usize)]| -> f64 {
            let mut g = MultiGraph::strict();
            let _ = g.extend_fresh_int_prefix_keyed_edges_unrecorded(n, stream.iter().copied());
            let t0 = Instant::now();
            for name in &victims {
                assert!(g.remove_node(name));
            }
            let dt = t0.elapsed().as_secs_f64();
            black_box(g.edge_count());
            dt
        };
        let time_proto_removals = |stream: &[(usize, usize, usize)]| -> f64 {
            let mut proto = MgIntStorageProto::bulk_load_int_prefix(n, stream.iter().copied());
            let t0 = Instant::now();
            for name in &victims {
                assert!(proto.remove_node(name));
            }
            let dt = t0.elapsed().as_secs_f64();
            black_box(proto.edge_count);
            dt
        };

        // Post-removal structural agreement (once, outside timing).
        let mut g = MultiGraph::strict();
        let _ = g.extend_fresh_int_prefix_keyed_edges_unrecorded(n, stream.iter().copied());
        let mut proto = MgIntStorageProto::bulk_load_int_prefix(n, stream.iter().copied());
        for name in &victims {
            assert!(g.remove_node(name));
            assert!(proto.remove_node(name));
        }
        assert_eq!(
            proto.edge_count,
            g.edge_count(),
            "removal arms diverged in edge_count"
        );
        assert_eq!(
            proto
                .node_names
                .iter()
                .map(String::as_str)
                .collect::<Vec<_>>(),
            g.nodes_ordered(),
            "removal arms diverged in node order"
        );

        let median = |samples: &mut Vec<f64>| -> f64 {
            samples.sort_by(f64::total_cmp);
            samples[samples.len() / 2]
        };
        let (mut cur, mut pro, mut nul) = (Vec::new(), Vec::new(), Vec::new());
        for _ in 0..7 {
            cur.push(time_current_removals(&stream));
            pro.push(time_proto_removals(&stream));
            nul.push(time_current_removals(&stream));
        }
        // br-r37-c1-thp6w S9: slab arm — must be ~parity with the String store.
        let time_slab_removals = |stream: &[(usize, usize, usize)]| -> f64 {
            let mut slab = super::mg_int_storage_proto::MgSlabStorageProto::bulk_load_int_prefix(
                n,
                stream.iter().copied(),
            );
            let t0 = Instant::now();
            for name in &victims {
                assert!(slab.remove_node(name));
            }
            let dt = t0.elapsed().as_secs_f64();
            black_box(slab.edge_count);
            dt
        };
        let mut g2 = MultiGraph::strict();
        let _ = g2.extend_fresh_int_prefix_keyed_edges_unrecorded(n, stream.iter().copied());
        let mut slab = super::mg_int_storage_proto::MgSlabStorageProto::bulk_load_int_prefix(
            n,
            stream.iter().copied(),
        );
        for name in &victims {
            assert!(g2.remove_node(name));
            assert!(slab.remove_node(name));
        }
        assert_eq!(
            slab.edge_count,
            g2.edge_count(),
            "slab removal arm diverged in edge_count"
        );
        assert_eq!(
            slab.node_order
                .keys()
                .map(String::as_str)
                .collect::<Vec<_>>(),
            g2.nodes_ordered(),
            "slab removal arm diverged in node order"
        );
        let mut sla = Vec::new();
        for _ in 0..7 {
            sla.push(time_slab_removals(&stream));
        }
        let msl = median(&mut sla);

        let (mc, mp, mn) = (median(&mut cur), median(&mut pro), median(&mut nul));
        println!(
            "THP6W_S8_REMOVAL_AB n={n} m={} removals={} current={mc:.6}s proto_renumber={mp:.6}s slab={msl:.6}s ratio_proto_over_current={:.3} ratio_slab_over_current={:.3} null={:.3}",
            stream.len(),
            victims.len(),
            mp / mc,
            msl / mc,
            mc / mn,
        );
    }

    /// br-r37-c1-thp6w S9 helper: full observable-order parity between the
    /// real MultiGraph and the slab prototype (order from `node_order`, rows
    /// resolved slot -> name), plus slab self-consistency (live slots named,
    /// free slots tombstoned).
    fn assert_slab_matches_mg(
        mg: &MultiGraph,
        slab: &super::mg_int_storage_proto::MgSlabStorageProto,
    ) {
        assert_eq!(
            slab.node_order
                .keys()
                .map(String::as_str)
                .collect::<Vec<_>>(),
            mg.nodes_ordered(),
            "slab node order"
        );
        for (name, &slot) in &slab.node_order {
            assert_eq!(
                slab.slot_names[slot].as_deref(),
                Some(name.as_str()),
                "slot_names desync for {name}"
            );
        }
        for &free in &slab.free_slots {
            assert!(
                slab.slot_names[free].is_none(),
                "free slot {free} still named"
            );
            assert!(slab.rows[free].is_empty(), "free slot {free} has row cells");
        }
        for (pos, name) in mg.nodes_ordered().iter().enumerate() {
            let mg_row: Vec<&str> = mg
                .neighbors_iter(name)
                .map_or_else(Vec::new, Iterator::collect);
            assert_eq!(
                slab.neighbor_names(pos),
                mg_row,
                "slab row order for {name}"
            );
            for v in &mg_row {
                assert_eq!(
                    slab.key_order(name, v),
                    mg.edge_keys_vec(name, v),
                    "slab key order for ({name}, {v})"
                );
            }
        }
        assert_eq!(slab.edge_count, mg.edge_count(), "slab edge_count");
    }

    /// br-r37-c1-thp6w S9 PARITY GAUNTLET (slab + slot recycling): the
    /// S8-mandated layout must stay byte-identical to the real MultiGraph
    /// through the S7 removal shapes AND the slab-specific hazards — slot
    /// reuse after removal (fresh name AND the removed name re-added must
    /// append at the END of node order with no phantom edges from the slot's
    /// previous occupant).
    #[test]
    fn thp6w_s9_slab_recycling_parity_gauntlet() {
        use super::mg_int_storage_proto::MgSlabStorageProto;

        let stream: Vec<(&str, &str, usize)> = vec![
            ("2", "10", 0),
            ("10", "2", 1),
            ("1", "1", 0),
            ("2", "3", 0),
            ("3", "2", 0),
            ("10", "1", 5),
            ("0", "2", 0),
            ("2", "10", 1),
            ("4", "5", 2),
            ("5", "4", 0),
            ("1", "1", 1),
        ];
        let mut mg = MultiGraph::strict();
        let _ = mg.extend_keyed_edges_with_attrs_unrecorded(
            stream
                .iter()
                .map(|(l, r, k)| ((*l).to_owned(), (*r).to_owned(), *k, AttrMap::new())),
        );
        let mut slab = MgSlabStorageProto::new();
        for (l, r, k) in &stream {
            slab.add_keyed_edge(l, r, *k, AttrMap::new());
        }
        assert_slab_matches_mg(&mg, &slab);

        // S7 removal shapes.
        assert_eq!(
            mg.remove_edge("4", "5", None),
            slab.remove_edge("4", "5", None)
        );
        assert_slab_matches_mg(&mg, &slab);
        assert_eq!(
            mg.remove_edge("2", "10", Some(0)),
            slab.remove_edge("2", "10", Some(0))
        );
        assert_slab_matches_mg(&mg, &slab);
        assert_eq!(
            mg.remove_edge("2", "10", None),
            slab.remove_edge("2", "10", None)
        );
        assert_slab_matches_mg(&mg, &slab);
        assert_eq!(
            mg.remove_edge("1", "1", Some(0)),
            slab.remove_edge("1", "1", Some(0))
        );
        assert_slab_matches_mg(&mg, &slab);
        assert_eq!(
            mg.remove_edge("0", "10", None),
            slab.remove_edge("0", "10", None)
        );
        assert_eq!(
            mg.remove_edge("2", "3", Some(9)),
            slab.remove_edge("2", "3", Some(9))
        );
        assert_slab_matches_mg(&mg, &slab);

        // Tombstone a mid-order node with live parallel edges...
        assert_eq!(mg.remove_node("2"), slab.remove_node("2"));
        assert_slab_matches_mg(&mg, &slab);
        // ...then RECYCLE its slot with a FRESH name: must append at the END
        // of node order and carry no phantom adjacency from the old occupant.
        mg.extend_keyed_edges_with_attrs_unrecorded(vec![(
            "fresh".to_owned(),
            "3".to_owned(),
            0,
            AttrMap::new(),
        )]);
        slab.add_keyed_edge("fresh", "3", 0, AttrMap::new());
        assert_slab_matches_mg(&mg, &slab);
        // ...and re-add the REMOVED name too (recycles another slot or a fresh
        // one; order must be append-at-end either way).
        mg.extend_keyed_edges_with_attrs_unrecorded(vec![(
            "2".to_owned(),
            "fresh".to_owned(),
            7,
            AttrMap::new(),
        )]);
        slab.add_keyed_edge("2", "fresh", 7, AttrMap::new());
        assert_slab_matches_mg(&mg, &slab);
        // Remove the recycled node again (double-recycle path).
        assert_eq!(mg.remove_node("fresh"), slab.remove_node("fresh"));
        assert_slab_matches_mg(&mg, &slab);
        // Self-loop node and end nodes.
        assert_eq!(mg.remove_node("1"), slab.remove_node("1"));
        assert_slab_matches_mg(&mg, &slab);
        assert_eq!(mg.remove_node("10"), slab.remove_node("10"));
        assert_slab_matches_mg(&mg, &slab);
        // Missing-node refusal parity.
        assert_eq!(mg.remove_node("gone"), slab.remove_node("gone"));
        assert_slab_matches_mg(&mg, &slab);
    }

    /// br-r37-c1-thp6w S10 helper: the ONLY observed edge order — walk-order
    /// emission with String-lex canonical orientation — must be byte-identical
    /// between the real MultiGraph and the slab layout.
    fn assert_slab_edges_ordered_matches_mg(
        mg: &MultiGraph,
        slab: &super::mg_int_storage_proto::MgSlabStorageProto,
    ) {
        let mg_ordered: Vec<(&str, &str, usize)> = mg
            .edges_ordered_borrowed()
            .into_iter()
            .map(|(l, r, k, _)| (l, r, k))
            .collect();
        assert_eq!(
            slab.edges_ordered_names(),
            mg_ordered,
            "edges_ordered walk emission must match"
        );
        // br-r37-c1-thp6w S12: the attrs-carrying walk must match in FULL,
        // including per-cell attr payloads.
        assert_eq!(
            slab.edges_ordered_borrowed(),
            mg.edges_ordered_borrowed(),
            "attrs-carrying edges_ordered walk must match"
        );
    }

    /// br-r37-c1-thp6w S10 PARITY GAUNTLET (copy-walk reorder + snapshot
    /// orientation): the two remaining tie-break axes for the real flip.
    /// `edges_ordered` (walk emission with lex-canonical orientation) and
    /// `reorder_rows_for_nx_copy_walk` (the MultiGraph.copy row-order
    /// contract) must stay byte-identical through reorders, post-reorder
    /// mutations, removals, and slot recycling.
    #[test]
    fn thp6w_s10_copy_walk_and_snapshot_orientation_gauntlet() {
        use super::mg_int_storage_proto::MgSlabStorageProto;

        let stream: Vec<(&str, &str, usize)> = vec![
            ("2", "10", 0),
            ("10", "2", 1),
            ("1", "1", 0),
            ("2", "3", 0),
            ("10", "1", 5),
            ("0", "2", 0),
            ("4", "5", 2),
            ("5", "4", 0),
            ("3", "0", 0),
            ("1", "1", 1),
            ("5", "0", 3),
        ];
        let mut mg = MultiGraph::strict();
        let _ = mg.extend_keyed_edges_with_attrs_unrecorded(
            stream
                .iter()
                .map(|(l, r, k)| ((*l).to_owned(), (*r).to_owned(), *k, AttrMap::new())),
        );
        let mut slab = MgSlabStorageProto::new();
        for (l, r, k) in &stream {
            slab.add_keyed_edge(l, r, *k, AttrMap::new());
        }
        assert_slab_matches_mg(&mg, &slab);
        assert_slab_edges_ordered_matches_mg(&mg, &slab);

        // THE copy-walk reorder (MultiGraph.copy row-order contract).
        mg.reorder_rows_for_nx_copy_walk();
        slab.reorder_rows_for_nx_copy_walk();
        assert_slab_matches_mg(&mg, &slab);
        assert_slab_edges_ordered_matches_mg(&mg, &slab);

        // Reorder must be idempotent on both sides.
        mg.reorder_rows_for_nx_copy_walk();
        slab.reorder_rows_for_nx_copy_walk();
        assert_slab_matches_mg(&mg, &slab);
        assert_slab_edges_ordered_matches_mg(&mg, &slab);

        // Post-reorder mutations: new edges append after the reordered cells.
        mg.extend_keyed_edges_with_attrs_unrecorded(vec![
            ("0".to_owned(), "9".to_owned(), 0, AttrMap::new()),
            ("9".to_owned(), "2".to_owned(), 0, AttrMap::new()),
        ]);
        slab.add_keyed_edge("0", "9", 0, AttrMap::new());
        slab.add_keyed_edge("9", "2", 0, AttrMap::new());
        assert_slab_matches_mg(&mg, &slab);
        assert_slab_edges_ordered_matches_mg(&mg, &slab);

        // Removal + slot recycling, then reorder AGAIN on the recycled state.
        assert_eq!(mg.remove_node("2"), slab.remove_node("2"));
        mg.extend_keyed_edges_with_attrs_unrecorded(vec![(
            "fresh".to_owned(),
            "9".to_owned(),
            0,
            AttrMap::new(),
        )]);
        slab.add_keyed_edge("fresh", "9", 0, AttrMap::new());
        assert_slab_matches_mg(&mg, &slab);
        assert_slab_edges_ordered_matches_mg(&mg, &slab);
        mg.reorder_rows_for_nx_copy_walk();
        slab.reorder_rows_for_nx_copy_walk();
        assert_slab_matches_mg(&mg, &slab);
        assert_slab_edges_ordered_matches_mg(&mg, &slab);
    }

    /// br-r37-c1-thp6w S12 A/B: the `edges_ordered_borrowed` read on the
    /// String store (per-cell `EdgeKeyRef` String-pair hashing + String-pair
    /// seen-set probes) vs the slab walk (usize hashing throughout). Same
    /// graph state on both sides (slab via `from_string_state`), full-output
    /// equality asserted outside timing, paired-interleaved with a null arm.
    /// `cargo test --release -p fnx-classes --lib thp6w_s12_edges_ordered_read_ab -- --ignored --nocapture`
    #[test]
    #[ignore = "paired A/B benchmark; run --release with --ignored --nocapture"]
    fn thp6w_s12_edges_ordered_read_ab() {
        use super::mg_int_storage_proto::MgSlabStorageProto;
        use std::collections::HashMap;
        use std::hint::black_box;
        use std::time::Instant;

        fn push_edge(
            stream: &mut Vec<(usize, usize, usize)>,
            key_counter: &mut HashMap<(usize, usize), usize>,
            u: usize,
            v: usize,
        ) {
            let entry = key_counter.entry((u.min(v), u.max(v))).or_insert(0);
            stream.push((u, v, *entry));
            *entry += 1;
        }

        let n = 20000usize;
        let mut stream = Vec::new();
        let mut key_counter = HashMap::new();
        for i in 0..n {
            push_edge(&mut stream, &mut key_counter, i, (i + 1) % n);
        }
        let mut state = 0x2545_F491_4F6C_DD1D_u64;
        let draw = |state: &mut u64| -> usize {
            *state = state
                .wrapping_mul(6_364_136_223_846_793_005)
                .wrapping_add(1_442_695_040_888_963_407);
            usize::try_from(*state >> 33).unwrap() % n
        };
        for _ in 0..3 * n {
            let u = draw(&mut state);
            let v = draw(&mut state);
            push_edge(&mut stream, &mut key_counter, u, v);
        }

        let mut g = MultiGraph::strict();
        let _ = g.extend_fresh_int_prefix_keyed_edges_unrecorded(n, stream.iter().copied());
        let slab = MgSlabStorageProto::from_string_state(&g);
        assert_eq!(
            slab.edges_ordered_borrowed(),
            g.edges_ordered_borrowed(),
            "arms must emit identical sequences"
        );

        let time_string = || -> f64 {
            let t0 = Instant::now();
            let out = g.edges_ordered_borrowed();
            let dt = t0.elapsed().as_secs_f64();
            black_box(out.len());
            dt
        };
        let time_slab = || -> f64 {
            let t0 = Instant::now();
            let out = slab.edges_ordered_borrowed();
            let dt = t0.elapsed().as_secs_f64();
            black_box(out.len());
            dt
        };
        let median = |samples: &mut Vec<f64>| -> f64 {
            samples.sort_by(f64::total_cmp);
            samples[samples.len() / 2]
        };
        let (mut cur, mut sla, mut nul) = (Vec::new(), Vec::new(), Vec::new());
        for _ in 0..9 {
            cur.push(time_string());
            sla.push(time_slab());
            nul.push(time_string());
        }
        let (mc, ms, mn) = (median(&mut cur), median(&mut sla), median(&mut nul));
        println!(
            "THP6W_S12_EDGES_ORDERED_AB n={n} m={} string={mc:.6}s slab={ms:.6}s ratio_string_over_slab={:.3} null={:.3}",
            stream.len(),
            mc / ms,
            mc / mn,
        );
    }

    /// br-r37-c1-thp6w S13 A/B: the INDEX-space `edges_ordered_indices_borrowed`
    /// read — String store (per-edge `nodes.get_index_of` String hash + `EdgeKey`
    /// pair hash) vs the slab (hash-free `slot->position` array + usize walk).
    /// Same graph state, output equality asserted outside timing, paired-
    /// interleaved with a null arm.
    /// `cargo test --release -p fnx-classes --lib thp6w_s13_edges_ordered_indices_ab -- --ignored --nocapture`
    #[test]
    #[ignore = "paired A/B benchmark; run --release with --ignored --nocapture"]
    fn thp6w_s13_edges_ordered_indices_ab() {
        use super::mg_int_storage_proto::MgSlabStorageProto;
        use std::collections::HashMap;
        use std::hint::black_box;
        use std::time::Instant;

        fn push_edge(
            stream: &mut Vec<(usize, usize, usize)>,
            key_counter: &mut HashMap<(usize, usize), usize>,
            u: usize,
            v: usize,
        ) {
            let entry = key_counter.entry((u.min(v), u.max(v))).or_insert(0);
            stream.push((u, v, *entry));
            *entry += 1;
        }

        let n = 20000usize;
        let mut stream = Vec::new();
        let mut key_counter = HashMap::new();
        for i in 0..n {
            push_edge(&mut stream, &mut key_counter, i, (i + 1) % n);
        }
        let mut state = 0x2545_F491_4F6C_DD1D_u64;
        let draw = |state: &mut u64| -> usize {
            *state = state
                .wrapping_mul(6_364_136_223_846_793_005)
                .wrapping_add(1_442_695_040_888_963_407);
            usize::try_from(*state >> 33).unwrap() % n
        };
        for _ in 0..3 * n {
            let u = draw(&mut state);
            let v = draw(&mut state);
            push_edge(&mut stream, &mut key_counter, u, v);
        }

        let mut g = MultiGraph::strict();
        let _ = g.extend_fresh_int_prefix_keyed_edges_unrecorded(n, stream.iter().copied());
        let slab = MgSlabStorageProto::from_string_state(&g);
        assert_eq!(
            slab.edges_ordered_indices_borrowed(),
            g.edges_ordered_indices_borrowed(),
            "arms must emit identical index sequences"
        );

        let time_string = || -> f64 {
            let t0 = Instant::now();
            let out = g.edges_ordered_indices_borrowed();
            let dt = t0.elapsed().as_secs_f64();
            black_box(out.len());
            dt
        };
        let time_slab = || -> f64 {
            let t0 = Instant::now();
            let out = slab.edges_ordered_indices_borrowed();
            let dt = t0.elapsed().as_secs_f64();
            black_box(out.len());
            dt
        };
        let median = |samples: &mut Vec<f64>| -> f64 {
            samples.sort_by(f64::total_cmp);
            samples[samples.len() / 2]
        };
        let (mut cur, mut sla, mut nul) = (Vec::new(), Vec::new(), Vec::new());
        for _ in 0..9 {
            cur.push(time_string());
            sla.push(time_slab());
            nul.push(time_string());
        }
        let (mc, ms, mn) = (median(&mut cur), median(&mut sla), median(&mut nul));
        println!(
            "THP6W_S13_EDGES_ORDERED_INDICES_AB n={n} m={} string={mc:.6}s slab={ms:.6}s ratio_string_over_slab={:.3} null={:.3}",
            stream.len(),
            mc / ms,
            mc / mn,
        );
    }

    /// br-r37-c1-thp6w S14: a fresh bulk-built graph must be WARM from birth
    /// (the slab co-built during construction), byte-identical, and stay warm
    /// through instrumented mutations. NOTE: `edges_ordered_borrowed` is a
    /// ROUTED read (S13) — comparing it against the shadow would be circular
    /// with a warm shadow, so this gauntlet uses only unrouted ground-truth
    /// accessors (`nodes_ordered`, `neighbors_iter`, `edge_keys_vec`); the
    /// walk itself is gated non-circularly by the S13 route gate.
    #[cfg(feature = "mg-int-storage")]
    #[test]
    fn thp6w_s14_fresh_bulk_graph_is_warm_from_birth() {
        let mut g = MultiGraph::strict();
        let stream = vec![
            (0usize, 1usize, 0usize),
            (1, 2, 0),
            (0, 1, 1), // parallel
            (2, 2, 0), // self-loop
            (3, 0, 0),
        ];
        let _ = g.extend_fresh_int_prefix_keyed_edges_unrecorded(5, stream.into_iter());
        assert!(
            g.slab_shadow_is_warm(),
            "fresh bulk graph must be born warm"
        );
        {
            let shadow = g.slab_shadow.as_deref().expect("shadow present");
            assert_slab_matches_mg(&g, &shadow.1);
        }
        // Instrumented mutations keep the born-warm shadow warm.
        let _ = g.add_edge("2", "4");
        assert!(g.slab_shadow_is_warm());
        assert!(g.remove_edge("0", "1", None));
        assert!(g.slab_shadow_is_warm());
        assert!(g.remove_node("1"));
        assert!(g.slab_shadow_is_warm());
        let shadow = g.slab_shadow.as_deref().expect("shadow present");
        assert_slab_matches_mg(&g, &shadow.1);

        // br-r37-c1-thp6w S15: the ATTRIBUTED fresh path is born warm too —
        // arbitrary labels, dup-(pair,key) attr merge, out-of-bounds skip.
        let mut h = MultiGraph::strict();
        let mut w1 = AttrMap::new();
        w1.insert("w".to_owned(), fnx_runtime::CgseValue::Int(1));
        let mut w2 = AttrMap::new();
        w2.insert("x".to_owned(), fnx_runtime::CgseValue::Int(2));
        let _ = h.extend_fresh_index_keyed_edges_with_attrs_unrecorded(
            vec!["b".to_owned(), "a".to_owned(), "c".to_owned()],
            vec![
                (0, 1, 0, w1.clone()),
                (1, 0, 0, w2),             // dup (pair, key) reversed -> attr merge
                (2, 2, 0, w1),             // self-loop
                (0, 9, 0, AttrMap::new()), // out-of-bounds -> skipped by BOTH sides
                (1, 2, 3, AttrMap::new()), // sparse key
            ],
        );
        assert!(h.slab_shadow_is_warm(), "attributed fresh graph born warm");
        let shadow = h.slab_shadow.as_deref().expect("shadow present");
        assert_slab_matches_mg(&h, &shadow.1);
        assert_eq!(
            shadow.1.edges[&(0, 1)].attrs_for(0),
            h.edge_attrs("b", "a", 0),
            "merged attrs on the dup cell must match"
        );
    }

    /// br-r37-c1-thp6w S11 GAUNTLET (production dual-write shadow): with the
    /// `mg-int-storage` feature on, every instrumented mutation (single-edge
    /// add incl. autocreate/parallel/self-loop/attr-merge, keyed batch,
    /// edge/node removal with slot recycling) must ADVANCE the shadow in
    /// place (warm + byte-identical), and every UNINSTRUMENTED mutation must
    /// leave it stale (revision key) or dropped (`apply_row_orders`) — never
    /// silently wrong.
    #[cfg(feature = "mg-int-storage")]
    #[test]
    fn thp6w_s11_slab_shadow_dual_write_gauntlet() {
        let shadow_parity = |g: &MultiGraph| {
            let shadow = g.slab_shadow.as_deref().expect("shadow must be present");
            assert_eq!(shadow.0, g.revision, "shadow must be warm (advanced)");
            assert_slab_matches_mg(g, &shadow.1);
        };

        let mut g = MultiGraph::strict();
        let _ = g.add_edge("a", "b");
        g.sync_slab_shadow();
        assert!(g.slab_shadow_is_warm());
        shadow_parity(&g);

        // Instrumented single-edge adds.
        let _ = g.add_edge("b", "c"); // autocreated endpoint
        shadow_parity(&g);
        let _ = g.add_edge("a", "b"); // parallel key
        shadow_parity(&g);
        let _ = g.add_edge("d", "d"); // self-loop, fresh node
        shadow_parity(&g);
        let mut attrs = AttrMap::new();
        attrs.insert("w".to_owned(), fnx_runtime::CgseValue::Int(3));
        let _ = g.add_edge_with_key_and_attrs("a", "b", 0, attrs); // attr merge
        shadow_parity(&g);

        // Instrumented keyed batch (write-through).
        let _ = g.extend_keyed_edges_with_attrs_unrecorded(vec![
            ("x".to_owned(), "y".to_owned(), 0, AttrMap::new()),
            ("y".to_owned(), "x".to_owned(), 1, AttrMap::new()),
            ("a".to_owned(), "x".to_owned(), 0, AttrMap::new()),
        ]);
        shadow_parity(&g);

        // Instrumented removals: parallel key (next_back), last key, node
        // removal, then slot recycling via a fresh name.
        assert!(g.remove_edge("a", "b", None));
        shadow_parity(&g);
        assert!(g.remove_edge("a", "b", None));
        shadow_parity(&g);
        assert!(g.remove_node("b"));
        shadow_parity(&g);
        let _ = g.add_edge("recycled", "c");
        shadow_parity(&g);

        // Uninstrumented order-only mutation DROPS the shadow.
        g.reorder_rows_for_nx_copy_walk();
        assert!(
            g.slab_shadow.is_none(),
            "apply_row_orders must drop the shadow"
        );
        // Re-sync must capture the post-reorder row orders exactly.
        g.sync_slab_shadow();
        shadow_parity(&g);

        // Uninstrumented content mutations leave the shadow STALE, never wrong.
        g.add_node("island");
        assert!(
            !g.slab_shadow_is_warm(),
            "uninstrumented mutation must stale the shadow"
        );
        g.sync_slab_shadow();
        shadow_parity(&g);
        g.clear_edges();
        assert!(!g.slab_shadow_is_warm());
        g.sync_slab_shadow();
        shadow_parity(&g);

        // br-r37-c1-thp6w S13 ROUTE GATE: with a warm shadow the production
        // `edges_ordered_borrowed` serves from the slab; the sequence must be
        // byte-identical to what the String walk produced while the shadow
        // was STALE (owned snapshot so it survives the sync).
        let _ = g.add_edge("r1", "r2"); // stales nothing — shadow advances...
        g.add_node("stale_maker"); // ...so force staleness via an uninstrumented op
        assert!(!g.slab_shadow_is_warm());
        let _ = g.add_edge("r2", "r1"); // parallel via reverse orientation (shadow stays stale)
        let _ = g.add_edge("r3", "r3");
        let expected: Vec<(String, String, usize, AttrMap)> = g
            .edges_ordered_borrowed() // stale shadow -> String walk
            .into_iter()
            .map(|(l, r, k, a)| (l.to_owned(), r.to_owned(), k, a.clone()))
            .collect();
        // Same gate for the OWNED `edges_ordered` route (captured stale first).
        let expected_owned: Vec<(String, String, usize, AttrMap)> = g
            .edges_ordered() // stale shadow -> String walk (owned)
            .into_iter()
            .map(|e| (e.left, e.right, e.key, e.attrs))
            .collect();
        g.sync_slab_shadow();
        assert!(g.slab_shadow_is_warm());
        let served: Vec<(String, String, usize, AttrMap)> = g
            .edges_ordered_borrowed() // warm shadow -> slab walk
            .into_iter()
            .map(|(l, r, k, a)| (l.to_owned(), r.to_owned(), k, a.clone()))
            .collect();
        assert_eq!(
            served, expected,
            "shadow-served edges_ordered must equal the String walk"
        );
        let served_owned: Vec<(String, String, usize, AttrMap)> = g
            .edges_ordered() // warm shadow -> slab walk (owned)
            .into_iter()
            .map(|e| (e.left, e.right, e.key, e.attrs))
            .collect();
        assert_eq!(
            served_owned, expected_owned,
            "shadow-served owned edges_ordered must equal the String walk"
        );
    }

    /// br-r37-c1-thp6w S5 A/B: pure storage-representation tax of the String-
    /// keyed MultiGraph core vs the index-keyed prototype layout, on the SAME
    /// pre-resolved (u_idx, v_idx, key) stream via the SAME-shape bulk loaders
    /// (`extend_fresh_int_prefix_keyed_edges_unrecorded` vs
    /// `bulk_load_int_prefix`) — no canonicalization, no Python boundary, no
    /// per-edge ledger in either arm. Paired-interleaved (current, proto,
    /// current-null per round), medians over 9 rounds.
    /// `cargo test --release -p fnx-classes --lib thp6w_s5_int_storage_construction_ab -- --ignored --nocapture`
    #[test]
    #[ignore = "paired A/B benchmark; run --release with --ignored --nocapture"]
    fn thp6w_s5_int_storage_construction_ab() {
        use super::mg_int_storage_proto::MgIntStorageProto;
        use std::collections::HashMap;
        use std::hint::black_box;
        use std::time::Instant;

        fn push_edge(
            stream: &mut Vec<(usize, usize, usize)>,
            key_counter: &mut HashMap<(usize, usize), usize>,
            u: usize,
            v: usize,
        ) {
            let entry = key_counter.entry((u.min(v), u.max(v))).or_insert(0);
            stream.push((u, v, *entry));
            *entry += 1;
        }

        let n = 20000usize;
        let mut stream = Vec::new();
        let mut key_counter = HashMap::new();
        for i in 0..n {
            push_edge(&mut stream, &mut key_counter, i, (i + 1) % n);
        }
        // Deterministic LCG chords (incl. incidental self-loops) + explicit parallels.
        let mut state = 0x2545_F491_4F6C_DD1D_u64;
        let draw = |state: &mut u64| -> usize {
            *state = state
                .wrapping_mul(6_364_136_223_846_793_005)
                .wrapping_add(1_442_695_040_888_963_407);
            usize::try_from(*state >> 33).unwrap() % n
        };
        for _ in 0..3 * n {
            let u = draw(&mut state);
            let v = draw(&mut state);
            push_edge(&mut stream, &mut key_counter, u, v);
        }
        for i in (0..2000).step_by(2) {
            push_edge(&mut stream, &mut key_counter, i, i + 1);
        }

        let time_current = |stream: &[(usize, usize, usize)]| -> f64 {
            let t0 = Instant::now();
            let mut g = MultiGraph::strict();
            let _ = g.extend_fresh_int_prefix_keyed_edges_unrecorded(n, stream.iter().copied());
            let dt = t0.elapsed().as_secs_f64();
            black_box(&g);
            dt
        };
        let time_proto = |stream: &[(usize, usize, usize)]| -> f64 {
            let t0 = Instant::now();
            let proto = MgIntStorageProto::bulk_load_int_prefix(n, stream.iter().copied());
            let dt = t0.elapsed().as_secs_f64();
            black_box(&proto);
            dt
        };
        // br-r37-c1-thp6w S6: compact One/Many bucket arm.
        let time_compact = |stream: &[(usize, usize, usize)]| -> f64 {
            let t0 = Instant::now();
            let compact =
                super::mg_int_storage_proto::MgIntStorageProtoCompact::bulk_load_int_prefix(
                    n,
                    stream.iter().copied(),
                );
            let dt = t0.elapsed().as_secs_f64();
            black_box(&compact);
            dt
        };

        // Structural agreement between the arms (once, outside timing):
        // the real store's derived integer rows must equal both proto rows.
        let mut g = MultiGraph::strict();
        let _ = g.extend_fresh_int_prefix_keyed_edges_unrecorded(n, stream.iter().copied());
        let proto = MgIntStorageProto::bulk_load_int_prefix(n, stream.iter().copied());
        let compact = super::mg_int_storage_proto::MgIntStorageProtoCompact::bulk_load_int_prefix(
            n,
            stream.iter().copied(),
        );
        g.with_int_adjacency(|adj| {
            for (i, row) in adj.iter().enumerate() {
                let proto_row: Vec<usize> = proto.rows[i].keys().copied().collect();
                assert_eq!(row, &proto_row, "derived integer row {i} must agree");
                let compact_row: Vec<usize> = compact.rows[i].keys().copied().collect();
                assert_eq!(row, &compact_row, "compact integer row {i} must agree");
            }
        });
        assert_eq!(
            proto.edge_count,
            g.edge_count(),
            "A/B arms built different graphs"
        );
        assert_eq!(
            compact.edge_count,
            g.edge_count(),
            "compact arm built a different graph"
        );
        // br-r37-c1-thp6w S9: slab arm — must hold the compact win.
        let time_slab = |stream: &[(usize, usize, usize)]| -> f64 {
            let t0 = Instant::now();
            let slab = super::mg_int_storage_proto::MgSlabStorageProto::bulk_load_int_prefix(
                n,
                stream.iter().copied(),
            );
            let dt = t0.elapsed().as_secs_f64();
            black_box(&slab);
            dt
        };
        let slab = super::mg_int_storage_proto::MgSlabStorageProto::bulk_load_int_prefix(
            n,
            stream.iter().copied(),
        );
        g.with_int_adjacency(|adj| {
            for (i, row) in adj.iter().enumerate() {
                let slab_row: Vec<usize> = slab.rows[i].keys().copied().collect();
                assert_eq!(row, &slab_row, "slab integer row {i} must agree");
            }
        });
        assert_eq!(
            slab.edge_count,
            g.edge_count(),
            "slab arm built a different graph"
        );

        let median = |samples: &mut Vec<f64>| -> f64 {
            samples.sort_by(f64::total_cmp);
            samples[samples.len() / 2]
        };
        let (mut cur, mut pro, mut com, mut sla, mut nul) =
            (Vec::new(), Vec::new(), Vec::new(), Vec::new(), Vec::new());
        for _ in 0..9 {
            cur.push(time_current(&stream));
            pro.push(time_proto(&stream));
            com.push(time_compact(&stream));
            sla.push(time_slab(&stream));
            nul.push(time_current(&stream));
        }
        let (mc, mp, mk, ms, mn) = (
            median(&mut cur),
            median(&mut pro),
            median(&mut com),
            median(&mut sla),
            median(&mut nul),
        );
        println!(
            "THP6W_S5_AB n={n} m={} current={mc:.6}s proto={mp:.6}s compact={mk:.6}s slab={ms:.6}s ratio_current_over_proto={:.3} ratio_current_over_compact={:.3} ratio_current_over_slab={:.3} ratio_compact_over_slab={:.3} null_current_over_current={:.3}",
            stream.len(),
            mc / mp,
            mc / mk,
            mc / ms,
            mk / ms,
            mc / mn,
        );
    }

    #[test]
    fn thp6w_int_adjacency_cache_is_fresh_per_clone() {
        let mut g = MultiGraph::strict();
        for i in 0..4 {
            g.add_node(format!("n{i}"));
        }
        let _ = g.add_edge("n0", "n1");
        // Populate g's memo.
        assert_int_adjacency_matches(&g);
        // Clone, then mutate the CLONE differently. The clone must NOT serve g's rows
        // (fresh-per-clone memo), and g must keep its own.
        let mut clone = g.clone();
        let _ = clone.add_edge("n2", "n3");
        assert_int_adjacency_matches(&clone);
        assert_int_adjacency_matches(&g);
        // And mutate g after the clone; both stay self-consistent.
        let _ = g.add_edge("n0", "n2");
        assert_int_adjacency_matches(&g);
        assert_int_adjacency_matches(&clone);
    }

    fn single_attr(key: &str, value: &str) -> AttrMap {
        let mut attrs = AttrMap::new();
        attrs.insert(key.to_owned(), CgseValue::from(value));
        attrs
    }

    #[test]
    fn edges_ordered_tracks_node_and_neighbor_iteration_order() {
        let mut graph = Graph::strict();
        graph
            .add_edge_with_attrs("a", "b", AttrMap::new())
            .expect("edge add should succeed");
        graph
            .add_edge_with_attrs("b", "c", AttrMap::new())
            .expect("edge add should succeed");
        graph
            .add_edge_with_attrs("a", "c", AttrMap::new())
            .expect("edge add should succeed");

        let pairs = graph
            .edges_ordered()
            .into_iter()
            .map(|edge| (edge.left, edge.right))
            .collect::<Vec<(String, String)>>();
        assert_eq!(
            pairs,
            vec![
                ("a".to_owned(), "b".to_owned()),
                ("a".to_owned(), "c".to_owned()),
                ("b".to_owned(), "c".to_owned()),
            ]
        );
    }

    #[test]
    fn edges_ordered_preserves_traversed_endpoint_orientation() {
        let mut graph = Graph::strict();
        graph
            .add_edge_with_attrs("2", "1", AttrMap::new())
            .expect("edge add should succeed");

        let pairs = graph
            .edges_ordered()
            .into_iter()
            .map(|edge| (edge.left, edge.right))
            .collect::<Vec<(String, String)>>();
        assert_eq!(pairs, vec![("2".to_owned(), "1".to_owned())]);

        let borrowed_pairs = graph
            .edges_ordered_borrowed()
            .into_iter()
            .map(|(left, right, _)| (left.to_owned(), right.to_owned()))
            .collect::<Vec<(String, String)>>();
        assert_eq!(borrowed_pairs, vec![("2".to_owned(), "1".to_owned())]);
    }

    #[test]
    fn edges_ordered_uses_node_order_for_preexisting_nodes() {
        let mut graph = Graph::strict();
        graph.add_node("1".to_owned());
        graph.add_node("2".to_owned());
        graph
            .add_edge_with_attrs("2", "1", AttrMap::new())
            .expect("edge add should succeed");

        let pairs = graph
            .edges_ordered()
            .into_iter()
            .map(|edge| (edge.left, edge.right))
            .collect::<Vec<(String, String)>>();
        assert_eq!(pairs, vec![("1".to_owned(), "2".to_owned())]);
    }

    #[test]
    fn edge_storage_order_index_iter_tracks_mutations() {
        let mut graph = Graph::strict();
        graph.add_node("c");
        graph.add_node("a");
        graph.add_node("b");
        graph
            .add_edge_with_attrs("c", "a", single_attr("weight", "1"))
            .expect("edge add should succeed");
        graph
            .add_edge_with_attrs("b", "c", single_attr("weight", "2"))
            .expect("edge add should succeed");
        graph
            .add_edge_with_attrs("a", "c", single_attr("color", "red"))
            .expect("duplicate edge update should succeed");

        let indexed_edges = |graph: &Graph| {
            graph
                .edges_storage_order_index_iter()
                .map(|(left, right, attrs)| {
                    (
                        graph
                            .get_node_name(left)
                            .expect("left endpoint index should resolve")
                            .to_owned(),
                        graph
                            .get_node_name(right)
                            .expect("right endpoint index should resolve")
                            .to_owned(),
                        attrs.get("weight").cloned(),
                    )
                })
                .collect::<Vec<_>>()
        };

        assert_eq!(
            indexed_edges(&graph),
            vec![
                (
                    "a".to_owned(),
                    "c".to_owned(),
                    Some(CgseValue::String("1".to_owned())),
                ),
                (
                    "b".to_owned(),
                    "c".to_owned(),
                    Some(CgseValue::String("2".to_owned())),
                ),
            ]
        );

        assert!(graph.remove_edge("a", "c"));
        assert_eq!(
            indexed_edges(&graph),
            vec![(
                "b".to_owned(),
                "c".to_owned(),
                Some(CgseValue::String("2".to_owned())),
            )]
        );

        assert!(graph.remove_node("b"));
        assert!(indexed_edges(&graph).is_empty());
    }

    fn assert_graph_core_invariants(graph: &Graph) {
        let mut unique_edges = BTreeSet::new();
        for node in graph.nodes_ordered() {
            let neighbors = graph
                .neighbors(node)
                .expect("graph nodes should always have adjacency buckets");
            for neighbor in neighbors {
                assert!(graph.has_node(neighbor));
                assert!(graph.has_edge(node, neighbor));
                let reverse_neighbors = graph
                    .neighbors(neighbor)
                    .expect("neighbor should always have adjacency bucket");
                assert!(reverse_neighbors.contains(&node));
                unique_edges.insert(canonical_edge(node, neighbor));
            }
        }
        assert_eq!(graph.edge_count(), unique_edges.len());
    }

    fn assert_multigraph_core_invariants(graph: &MultiGraph) {
        let mut edge_instances = BTreeSet::new();
        for node in graph.nodes_ordered() {
            let neighbors = graph
                .neighbors(node)
                .expect("multigraph nodes should always have adjacency buckets");
            for neighbor in neighbors {
                assert!(graph.has_node(neighbor));
                assert!(graph.has_edge(node, neighbor));
                let reverse_neighbors = graph
                    .neighbors(neighbor)
                    .expect("neighbor should always have adjacency bucket");
                assert!(reverse_neighbors.contains(&node));
                let keys = graph
                    .edge_keys(node, neighbor)
                    .expect("parallel edge bucket should exist");
                for key in keys {
                    let canonical = canonical_edge(node, neighbor);
                    edge_instances.insert((canonical.0, canonical.1, key));
                }
            }
        }
        assert_eq!(graph.edge_count(), edge_instances.len());
    }

    fn assert_decision_record_schema(record: &DecisionRecord, expected_mode: CompatibilityMode) {
        assert!(record.ts_unix_ms > 0);
        assert!(!record.operation.trim().is_empty());
        assert_eq!(record.mode, expected_mode);
        assert!((0.0..=1.0).contains(&record.incompatibility_probability));
        assert!(!record.rationale.trim().is_empty());
        assert!(!record.evidence.is_empty());
        for term in &record.evidence {
            assert!(!term.signal.trim().is_empty());
            assert!(!term.observed_value.trim().is_empty());
        }
    }

    #[test]
    fn add_edge_autocreates_nodes_and_preserves_order() {
        let mut graph = Graph::strict();
        graph
            .add_edge_with_attrs("a", "b", AttrMap::new())
            .expect("edge insert should succeed");
        graph
            .add_edge_with_attrs("a", "c", AttrMap::new())
            .expect("edge insert should succeed");

        assert_eq!(graph.node_count(), 3);
        assert_eq!(graph.edge_count(), 2);
        assert_eq!(graph.nodes_ordered(), vec!["a", "b", "c"]);
        assert_eq!(graph.neighbors("a"), Some(vec!["b", "c"]));
    }

    #[test]
    fn extend_edges_unrecorded_preserves_adjacency_and_records_once() {
        let mut graph = Graph::strict();
        graph.add_node("a");
        graph.add_node("b");
        graph.add_node("c");
        let before = graph.evidence_ledger().records().len();

        let inserted = graph.extend_edges_unrecorded([("a", "b"), ("a", "c"), ("b", "a")]);

        assert_eq!(inserted, 2);
        assert_eq!(graph.edge_count(), 2);
        assert_eq!(graph.neighbors("a"), Some(vec!["b", "c"]));
        let records = graph.evidence_ledger().records();
        assert_eq!(records.len(), before + 1);
        assert_eq!(
            records.last().map(|record| record.operation.as_str()),
            Some("extend_edges_unrecorded")
        );
    }

    #[test]
    fn extend_existing_index_edges_unrecorded_matches_string_batch_on_int_prefix() {
        let nodes = (0..12).map(|node| node.to_string()).collect::<Vec<_>>();
        let edge_indices = vec![(10usize, 2usize), (2, 10), (3, 3), (1, 11), (11, 1)];
        let edge_strings = edge_indices
            .iter()
            .map(|(left, right)| (left.to_string(), right.to_string()))
            .collect::<Vec<_>>();

        let mut by_string = Graph::strict();
        let mut by_index = Graph::strict();
        let _ = by_string.extend_nodes_unrecorded(nodes.clone());
        let _ = by_index.extend_nodes_unrecorded(nodes);

        assert!(by_index.nodes_are_contiguous_int_prefix());
        assert_eq!(by_string.extend_edges_unrecorded(edge_strings), 3);
        assert_eq!(
            by_index.extend_existing_index_edges_unrecorded(edge_indices),
            3
        );

        assert_eq!(by_index.snapshot(), by_string.snapshot());
        assert_graph_core_invariants(&by_index);
    }

    #[test]
    fn extend_edges_with_attrs_unrecorded_matches_add_edge_with_attrs() {
        // br-r37-c1-pr8q6: bulk attributed insertion must be observationally
        // identical to a sequence of add_edge_with_attrs calls (node order,
        // adjacency order, attr merge on duplicates) minus the per-edge
        // ledger records.
        let mut attrs1 = AttrMap::new();
        attrs1.insert("w".to_owned(), CgseValue::Int(1));
        let mut attrs2 = AttrMap::new();
        attrs2.insert("w".to_owned(), CgseValue::Int(7));
        attrs2.insert("c".to_owned(), CgseValue::String("x".to_owned()));

        let mut reference = Graph::strict();
        reference
            .add_edge_with_attrs("a", "b", attrs1.clone())
            .unwrap();
        reference
            .add_edge_with_attrs("b", "c", AttrMap::new())
            .unwrap();
        // duplicate edge: attrs merge
        reference
            .add_edge_with_attrs("b", "a", attrs2.clone())
            .unwrap();
        // self-loop
        reference
            .add_edge_with_attrs("d", "d", attrs1.clone())
            .unwrap();

        let mut bulk = Graph::strict();
        let before = bulk.evidence_ledger().records().len();
        let inserted = bulk.extend_edges_with_attrs_unrecorded([
            ("a".to_owned(), "b".to_owned(), attrs1.clone()),
            ("b".to_owned(), "c".to_owned(), AttrMap::new()),
            ("b".to_owned(), "a".to_owned(), attrs2.clone()),
            ("d".to_owned(), "d".to_owned(), attrs1.clone()),
        ]);

        assert_eq!(inserted, 3);
        assert_eq!(bulk.edge_count(), reference.edge_count());
        assert_eq!(bulk.nodes_ordered(), reference.nodes_ordered());
        for node in bulk.nodes_ordered() {
            assert_eq!(bulk.neighbors(node), reference.neighbors(node));
        }
        assert_eq!(bulk.edge_attrs("a", "b"), reference.edge_attrs("a", "b"));
        assert_eq!(bulk.edge_attrs("d", "d"), reference.edge_attrs("d", "d"));
        // one summary record, not one per edge
        assert_eq!(bulk.evidence_ledger().records().len(), before + 1);
    }

    #[test]
    fn multigraph_int_prefix_keyed_edges_match_string_batch() {
        let indexed_edges = vec![
            (0usize, 1usize, 0usize),
            (1, 2, 0),
            (2, 0, 0),
            (0, 1, 1),
            (2, 2, 0),
        ];
        let string_edges = indexed_edges
            .iter()
            .map(|(left, right, key)| (left.to_string(), right.to_string(), *key, AttrMap::new()))
            .collect::<Vec<_>>();

        let mut by_string = MultiGraph::strict();
        let mut by_index = MultiGraph::strict();

        assert_eq!(
            by_string.extend_keyed_edges_with_attrs_unrecorded(string_edges),
            indexed_edges.len()
        );
        assert_eq!(
            by_index.extend_fresh_int_prefix_keyed_edges_unrecorded(3, indexed_edges),
            5
        );

        assert_eq!(by_index.snapshot(), by_string.snapshot());
        assert_multigraph_core_invariants(&by_index);
    }

    #[test]
    fn extend_nodes_unrecorded_preserves_order_and_records_once() {
        let mut graph = Graph::strict();
        graph.add_node("1");
        let before = graph.evidence_ledger().records().len();

        let inserted =
            graph.extend_nodes_unrecorded(["0".to_owned(), "1".to_owned(), "2".to_owned()]);

        assert_eq!(inserted, 2);
        assert_eq!(graph.node_count(), 3);
        assert_eq!(graph.nodes_ordered(), vec!["1", "0", "2"]);
        assert_eq!(graph.neighbor_count("0"), 0);
        assert_eq!(graph.neighbor_count("2"), 0);
        let records = graph.evidence_ledger().records();
        assert_eq!(records.len(), before + 1);
        assert_eq!(
            records.last().map(|record| record.operation.as_str()),
            Some("extend_nodes_unrecorded")
        );
    }

    #[test]
    fn neighbors_iter_preserves_deterministic_order() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        graph.add_edge("a", "c").expect("edge add should succeed");
        graph.add_edge("a", "d").expect("edge add should succeed");

        let neighbors = graph
            .neighbors_iter("a")
            .expect("neighbors should exist")
            .collect::<Vec<&str>>();
        assert_eq!(neighbors, vec!["b", "c", "d"]);
    }

    #[test]
    fn neighbor_count_matches_neighbors_len() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        graph.add_edge("a", "c").expect("edge add should succeed");
        assert_eq!(graph.neighbor_count("a"), 2);
        assert_eq!(graph.neighbor_count("missing"), 0);
    }

    #[test]
    fn repeated_edge_updates_attrs_in_place() {
        let mut graph = Graph::strict();
        let mut first = AttrMap::new();
        first.insert("weight".to_owned(), "1".into());
        graph
            .add_edge_with_attrs("a", "b", first)
            .expect("edge insert should succeed");

        let mut second = AttrMap::new();
        second.insert("color".to_owned(), "blue".into());
        graph
            .add_edge_with_attrs("b", "a", second)
            .expect("edge update should succeed");

        let attrs = graph
            .edge_attrs("a", "b")
            .expect("edge attrs should be present");
        assert_eq!(
            attrs.get("weight"),
            Some(&CgseValue::String("1".to_owned()))
        );
        assert_eq!(
            attrs.get("color"),
            Some(&CgseValue::String("blue".to_owned()))
        );
        assert_eq!(graph.edge_count(), 1);
    }

    #[test]
    fn complete_graph_bulk_constructor_preserves_ordered_contract() {
        let graph = Graph::complete_graph(CompatibilityMode::Strict, 5);

        assert_eq!(graph.node_count(), 5);
        assert_eq!(graph.edge_count(), 10);
        assert_eq!(graph.nodes_ordered(), vec!["0", "1", "2", "3", "4"]);
        assert_eq!(
            graph.neighbors("0").expect("node 0 should exist"),
            vec!["1", "2", "3", "4"]
        );
        assert_eq!(
            graph.neighbors("4").expect("node 4 should exist"),
            vec!["0", "1", "2", "3"]
        );
        assert_eq!(
            graph
                .edges_ordered()
                .into_iter()
                .map(|edge| (edge.left, edge.right))
                .collect::<Vec<_>>(),
            vec![
                ("0".to_owned(), "1".to_owned()),
                ("0".to_owned(), "2".to_owned()),
                ("0".to_owned(), "3".to_owned()),
                ("0".to_owned(), "4".to_owned()),
                ("1".to_owned(), "2".to_owned()),
                ("1".to_owned(), "3".to_owned()),
                ("1".to_owned(), "4".to_owned()),
                ("2".to_owned(), "3".to_owned()),
                ("2".to_owned(), "4".to_owned()),
                ("3".to_owned(), "4".to_owned()),
            ]
        );

        let operations = graph
            .evidence_ledger()
            .records()
            .iter()
            .map(|record| record.operation.as_str())
            .collect::<Vec<_>>();
        assert_eq!(operations, vec!["complete_graph_bulk"]);
    }

    #[test]
    fn remove_node_removes_incident_edges() {
        let mut graph = Graph::strict();
        graph.add_edge("a", "b").expect("edge add should succeed");
        graph.add_edge("b", "c").expect("edge add should succeed");
        assert!(graph.remove_node("b"));
        assert_eq!(graph.node_count(), 2);
        assert_eq!(graph.edge_count(), 0);
    }

    // br-r37-c1-p6bxu: A/B substrate bench for MultiGraph::remove_node
    // (O(degree) swap_remove vs the old O(|E|) retain). Ignored by default;
    // run with `cargo test -p fnx-classes --release ab_bench_multigraph_remove_node
    // -- --ignored --nocapture`. Also asserts byte-exact parity (node_count,
    // edge_count, edges_ordered) between the two paths.
    #[test]
    #[ignore]
    fn ab_bench_multigraph_remove_node() {
        use std::time::Instant;
        const N: usize = 1000;
        const M: usize = 8000;
        const ITERS: usize = 500;
        let build = || {
            let mut g = MultiGraph::new(CompatibilityMode::Strict);
            for i in 0..N {
                let _ = g.add_node(i.to_string());
            }
            let mut s: u64 = 0x9E3779B97F4A7C15;
            let mut next = || {
                s = s
                    .wrapping_mul(6364136223846793005)
                    .wrapping_add(1442695040888963407);
                (s >> 33) as usize % N
            };
            for _ in 0..M {
                let a = next();
                let b = next();
                let _ = g.add_edge(a.to_string(), b.to_string());
            }
            g
        };

        let mut gnew = build();
        let victims: Vec<String> = gnew.nodes.keys().take(ITERS).cloned().collect();
        let t = Instant::now();
        for node in &victims {
            gnew.remove_node(node);
        }
        let new_t = t.elapsed();

        // OLD path: full O(|E|) retain per removal.
        let mut gold = build();
        let t = Instant::now();
        for node in &victims {
            if !gold.nodes.contains_key(node) {
                continue;
            }
            if let Some(neighbors) = gold.adjacency.get(node) {
                let names: Vec<String> = neighbors.keys().cloned().collect();
                for nb in names {
                    if nb != *node
                        && let Some(rn) = gold.adjacency.get_mut(&nb)
                    {
                        rn.shift_remove(node.as_str());
                    }
                }
            }
            let mut rc = 0usize;
            let nd = node.clone();
            gold.edges.retain(|k, bucket| {
                let keep = k.left != nd && k.right != nd;
                if !keep {
                    rc += bucket.len();
                }
                keep
            });
            gold.edge_count -= rc;
            gold.adjacency.shift_remove(node);
            gold.nodes.shift_remove(node);
        }
        let old_t = t.elapsed();

        assert_eq!(gnew.node_count(), gold.node_count());
        assert_eq!(gnew.edge_count(), gold.edge_count());
        assert_eq!(gnew.edges_ordered(), gold.edges_ordered());
        eprintln!(
            "MultiGraph remove_node x{ITERS}: retain {old_t:?} -> swap_remove {new_t:?} = {:.2}x",
            old_t.as_secs_f64() / new_t.as_secs_f64()
        );
    }

    #[test]
    fn remove_nodes_from_matches_repeated_removal_and_rebuilds_indices() {
        let edges = [
            ("0", "1"),
            ("1", "2"),
            ("2", "3"),
            ("3", "4"),
            ("4", "5"),
            ("0", "5"),
            ("1", "4"),
            ("2", "5"),
        ];
        let mut batch = Graph::strict();
        let mut repeated = Graph::strict();
        for (left, right) in edges {
            batch.add_edge(left, right).expect("batch edge add");
            repeated.add_edge(left, right).expect("repeated edge add");
        }

        let victims = ["1", "3", "99", "1"];
        let removed = batch.remove_nodes_from(victims);
        for victim in victims {
            let _ = repeated.remove_node(victim);
        }

        assert_eq!(removed, (2, 5));
        assert_eq!(batch.snapshot(), repeated.snapshot());
        let ordered_nodes = batch
            .nodes_ordered()
            .into_iter()
            .map(str::to_owned)
            .collect::<Vec<_>>();
        for (node_index, node) in ordered_nodes.iter().enumerate() {
            let names_from_strings = batch.neighbors(node).expect("node should exist");
            let names_from_indices = batch
                .neighbors_indices(node_index)
                .expect("index should exist")
                .iter()
                .map(|index| batch.get_node_name(*index).expect("index should resolve"))
                .collect::<Vec<_>>();
            assert_eq!(names_from_indices, names_from_strings);
        }
        let names_from_edge_indices = batch
            .edges_storage_order_index_iter()
            .map(|(left, right, _)| {
                (
                    batch
                        .get_node_name(left)
                        .expect("left endpoint should resolve")
                        .to_owned(),
                    batch
                        .get_node_name(right)
                        .expect("right endpoint should resolve")
                        .to_owned(),
                )
            })
            .collect::<Vec<_>>();
        let names_from_edge_storage = batch
            .edges_storage_order_iter()
            .map(|(left, right, _)| (left.to_owned(), right.to_owned()))
            .collect::<Vec<_>>();
        assert_eq!(names_from_edge_indices, names_from_edge_storage);
    }

    #[test]
    fn multigraph_ordered_indices_match_borrowed_edges() {
        let mut graph = MultiGraph::strict();
        graph
            .add_edge_with_key_and_attrs("b", "a", 2, single_attr("w", "left"))
            .expect("first keyed edge should be added");
        graph
            .add_edge_with_key_and_attrs("a", "b", 0, single_attr("w", "right"))
            .expect("parallel keyed edge should be added");
        graph
            .add_edge_with_key_and_attrs("a", "c", 3, AttrMap::new())
            .expect("third edge should be added");
        graph
            .add_edge_with_key_and_attrs("c", "c", 1, single_attr("w", "loop"))
            .expect("self-loop should be added");

        let nodes = graph.nodes_ordered();
        let from_indices = graph
            .edges_ordered_indices_borrowed()
            .into_iter()
            .map(|(left, right, key, attrs)| {
                (
                    nodes[left].to_owned(),
                    nodes[right].to_owned(),
                    key,
                    attrs.clone(),
                )
            })
            .collect::<Vec<_>>();
        let from_borrowed = graph
            .edges_ordered_borrowed()
            .into_iter()
            .map(|(left, right, key, attrs)| {
                (left.to_owned(), right.to_owned(), key, attrs.clone())
            })
            .collect::<Vec<_>>();

        assert_eq!(from_indices, from_borrowed);
    }

    #[test]
    fn multigraph_node_index_accessors_follow_remove_readd() {
        let mut graph = MultiGraph::strict();
        for node in ["prefix", "s", "a", "b", "t"] {
            let _ = graph.add_node(node.to_owned());
        }

        for (expected_index, node) in ["prefix", "s", "a", "b", "t"].into_iter().enumerate() {
            assert_eq!(graph.get_node_index(node), Some(expected_index));
            assert_eq!(graph.get_node_name(expected_index), Some(node));
        }

        assert!(graph.remove_node("prefix"));
        assert!(graph.remove_node("a"));
        let _ = graph.add_node("a".to_owned());

        for (expected_index, node) in ["s", "b", "t", "a"].into_iter().enumerate() {
            assert_eq!(graph.get_node_index(node), Some(expected_index));
            assert_eq!(graph.get_node_name(expected_index), Some(node));
        }
        assert_eq!(graph.get_node_index("prefix"), None);
        assert_eq!(graph.get_node_name(graph.node_count()), None);
    }

    #[test]
    fn strict_mode_fails_closed_for_unknown_incompatible_feature() {
        let mut graph = Graph::strict();
        let mut attrs = AttrMap::new();
        attrs.insert("__fnx_incompatible_decoder".to_owned(), "v2".into());
        let err = graph
            .add_edge_with_attrs("a", "b", attrs)
            .expect_err("strict mode should fail closed");

        assert_eq!(
            err,
            GraphError::FailClosed {
                operation: "add_edge",
                reason: "incompatible edge metadata".to_owned(),
            }
        );

        let last_record = graph
            .evidence_ledger()
            .records()
            .last()
            .expect("strict fail-closed path should emit a ledger row");
        assert_decision_record_schema(last_record, CompatibilityMode::Strict);
        assert_eq!(last_record.operation, "add_edge");
        assert_eq!(last_record.action, DecisionAction::FailClosed);
        assert!(
            last_record
                .evidence
                .iter()
                .any(|term| term.signal == "unknown_incompatible_feature")
        );
    }

    #[test]
    fn revision_increments_on_mutating_operations() {
        let mut graph = Graph::strict();
        let r0 = graph.revision();
        let _ = graph.add_node("a");
        let r1 = graph.revision();
        assert!(r1 > r0);

        graph.add_edge("a", "b").expect("edge add should succeed");
        let r2 = graph.revision();
        assert!(r2 > r1);

        let _ = graph.remove_edge("a", "b");
        let r3 = graph.revision();
        assert!(r3 > r2);
    }

    #[test]
    fn add_node_with_attrs_reports_change_on_existing_node() {
        let mut graph = Graph::strict();
        assert!(graph.add_node_with_attrs("a", single_attr("color", "red")));
        let r1 = graph.revision();
        assert!(graph.add_node_with_attrs("a", single_attr("color", "blue")));
        let r2 = graph.revision();
        assert!(r2 > r1);
        let expected = CgseValue::from("blue");
        assert_eq!(graph.node_attrs("a").unwrap().get("color"), Some(&expected));
    }

    #[test]
    fn multigraph_add_node_with_attrs_reports_change_on_existing_node() {
        let mut graph = MultiGraph::strict();
        assert!(graph.add_node_with_attrs("a", single_attr("color", "red")));
        let r1 = graph.revision();
        assert!(graph.add_node_with_attrs("a", single_attr("color", "blue")));
        let r2 = graph.revision();
        assert!(r2 > r1);
        let expected = CgseValue::from("blue");
        assert_eq!(graph.node_attrs("a").unwrap().get("color"), Some(&expected));
    }

    #[test]
    fn hardened_self_loop_records_allow_decision() {
        let mut graph = Graph::hardened();
        graph
            .add_edge("loop", "loop")
            .expect("hardened self-loop edge should be accepted");

        let add_edge_record = graph
            .evidence_ledger()
            .records()
            .iter()
            .rev()
            .find(|record| record.operation == "add_edge")
            .expect("add_edge operation should emit ledger row");
        assert_decision_record_schema(add_edge_record, CompatibilityMode::Hardened);
        assert_eq!(add_edge_record.action, DecisionAction::Allow);
        assert!(
            add_edge_record
                .evidence
                .iter()
                .any(|term| term.signal == "self_loop" && term.observed_value == "true")
        );
    }

    #[test]
    fn runtime_policy_tracks_hardened_graph_recovery() {
        let mut graph = Graph::hardened();
        graph
            .add_edge("a", "b")
            .expect("hardened graph edge add should succeed");

        assert_eq!(graph.runtime_policy().mode(), CompatibilityMode::Hardened);
        assert!(!graph.runtime_policy().decision_log().records().is_empty());
        assert!(graph.runtime_policy().posterior().observation_count >= 1);
    }

    #[test]
    fn snapshot_roundtrip_replays_to_identical_state() {
        let mut graph = Graph::strict();

        let mut first_attrs = AttrMap::new();
        first_attrs.insert("weight".to_owned(), "7".into());
        graph
            .add_edge_with_attrs("a", "b", first_attrs)
            .expect("edge insert should succeed");

        let mut second_attrs = AttrMap::new();
        second_attrs.insert("color".to_owned(), "green".into());
        graph
            .add_edge_with_attrs("b", "c", second_attrs)
            .expect("edge insert should succeed");

        let snapshot = graph.snapshot();
        let mut replayed = Graph::new(snapshot.mode);
        for node in &snapshot.nodes {
            let _ = replayed.add_node(node.clone());
        }
        for edge in &snapshot.edges {
            replayed
                .add_edge_with_attrs(edge.left.clone(), edge.right.clone(), edge.attrs.clone())
                .expect("snapshot replay should be valid");
        }

        assert_eq!(replayed.snapshot(), snapshot);
        assert_graph_core_invariants(&replayed);
    }

    #[test]
    fn multigraph_tracks_parallel_edges_with_distinct_keys() {
        let mut graph = MultiGraph::strict();
        let first = graph.add_edge("a", "b").expect("edge add should succeed");
        let second = graph.add_edge("a", "b").expect("edge add should succeed");

        assert_ne!(first, second);
        assert_eq!(graph.edge_count(), 2);
        assert_eq!(graph.edge_keys("a", "b"), Some(vec![0, 1]));
        assert_multigraph_core_invariants(&graph);
    }

    #[test]
    fn multigraph_counts_parallel_selfloops_only() {
        let mut graph = MultiGraph::strict();
        let _ = graph
            .add_edge("a", "a")
            .expect("self-loop add should succeed");
        let _ = graph
            .add_edge("a", "a")
            .expect("self-loop add should succeed");
        let _ = graph
            .add_edge("b", "b")
            .expect("self-loop add should succeed");
        let _ = graph.add_edge("a", "b").expect("edge add should succeed");
        let _ = graph.add_edge("a", "b").expect("edge add should succeed");

        assert_eq!(graph.number_of_selfloops(), 3);
        assert_multigraph_core_invariants(&graph);
    }

    #[test]
    fn multigraph_add_fresh_edge_unrecorded_rejects_occupied_bucket() {
        let mut graph = MultiGraph::strict();
        assert_eq!(graph.add_fresh_edge_unrecorded("a", "b"), Some(0));
        let revision = graph.revision();
        let edge_count = graph.edge_count();

        assert_eq!(graph.add_fresh_edge_unrecorded("b", "a"), None);

        assert_eq!(graph.revision(), revision);
        assert_eq!(graph.edge_count(), edge_count);
        assert_eq!(graph.edge_keys("a", "b"), Some(vec![0]));
        assert_eq!(graph.nodes_ordered(), vec!["a", "b"]);
        assert_multigraph_core_invariants(&graph);
    }

    #[test]
    fn multigraph_add_fresh_edge_with_key_unrecorded_preserves_key() {
        let mut graph = MultiGraph::strict();

        assert_eq!(
            graph.add_fresh_edge_with_key_unrecorded("a", "b", 42),
            Some(42)
        );

        assert_eq!(graph.edge_count(), 1);
        assert_eq!(graph.edge_keys("a", "b"), Some(vec![42]));
        assert_eq!(graph.nodes_ordered(), vec!["a", "b"]);
        assert_multigraph_core_invariants(&graph);
    }

    #[test]
    fn multigraph_remove_edge_without_key_removes_latest_instance() {
        let mut graph = MultiGraph::strict();
        let first = graph.add_edge("a", "b").expect("edge add should succeed");
        let second = graph.add_edge("a", "b").expect("edge add should succeed");

        assert!(graph.remove_edge("a", "b", None));
        assert_eq!(graph.edge_count(), 1);
        assert_eq!(graph.edge_keys("a", "b"), Some(vec![first]));
        assert_ne!(first, second);
        assert_multigraph_core_invariants(&graph);
    }

    #[test]
    fn multigraph_remove_node_clears_parallel_incident_edges() {
        let mut graph = MultiGraph::strict();
        let _ = graph.add_edge("a", "b").expect("edge add should succeed");
        let _ = graph.add_edge("a", "b").expect("edge add should succeed");
        let _ = graph.add_edge("b", "c").expect("edge add should succeed");

        assert!(graph.remove_node("b"));
        assert_eq!(graph.edge_count(), 0);
        assert!(!graph.has_node("b"));
        assert_eq!(graph.neighbors("a"), Some(vec![]));
        assert_eq!(graph.neighbors("c"), Some(vec![]));
        assert_multigraph_core_invariants(&graph);
    }

    #[test]
    fn multigraph_clear_edges_preserves_nodes_attrs_and_rows() {
        let mut graph = MultiGraph::strict();
        assert!(graph.add_node_with_attrs("a", single_attr("color", "red")));
        assert!(graph.add_node_with_attrs("b", single_attr("color", "blue")));
        let _ = graph
            .add_edge_with_key_and_attrs("a", "b", 7, single_attr("weight", "3"))
            .expect("edge add should succeed");
        let _ = graph
            .add_edge_with_key_and_attrs("b", "a", 2, single_attr("weight", "5"))
            .expect("edge add should succeed");
        let before_revision = graph.revision();

        graph.clear_edges();

        assert_eq!(graph.node_count(), 2);
        assert_eq!(graph.nodes_ordered(), vec!["a", "b"]);
        assert_eq!(graph.edge_count(), 0);
        assert!(graph.edges_ordered().is_empty());
        assert_eq!(graph.neighbors("a"), Some(vec![]));
        assert_eq!(graph.neighbors("b"), Some(vec![]));
        assert_eq!(
            graph.node_attrs("a").unwrap().get("color"),
            Some(&CgseValue::from("red"))
        );
        assert!(graph.revision() > before_revision);
        assert_multigraph_core_invariants(&graph);
    }

    #[test]
    fn runtime_policy_tracks_hardened_multigraph_recovery() {
        let mut graph = MultiGraph::hardened();
        graph
            .add_edge("a", "b")
            .expect("hardened multigraph edge add should succeed");

        assert_eq!(graph.runtime_policy().mode(), CompatibilityMode::Hardened);
        assert!(!graph.runtime_policy().decision_log().records().is_empty());
        assert!(graph.runtime_policy().posterior().observation_count >= 1);
    }

    #[test]
    fn multigraph_roundtrips_sparse_snapshot_keys() {
        let mut graph = MultiGraph::strict();
        assert_eq!(
            graph.add_edge("a", "b").expect("edge add should succeed"),
            0
        );
        assert_eq!(
            graph.add_edge("a", "b").expect("edge add should succeed"),
            1
        );
        assert_eq!(
            graph.add_edge("a", "b").expect("edge add should succeed"),
            2
        );
        assert!(graph.remove_edge("a", "b", Some(1)));
        assert_eq!(
            graph.add_edge("a", "b").expect("edge add should succeed"),
            3
        );

        let snapshot = graph.snapshot();
        assert_eq!(
            snapshot
                .edges
                .iter()
                .map(|edge| edge.key)
                .collect::<Vec<_>>(),
            vec![0, 2, 3]
        );

        let mut replayed = MultiGraph::new(snapshot.mode);
        for node in &snapshot.nodes {
            let _ = replayed.add_node(node.clone());
        }
        for edge in &snapshot.edges {
            replayed
                .add_edge_with_key_and_attrs(
                    edge.left.clone(),
                    edge.right.clone(),
                    edge.key,
                    edge.attrs.clone(),
                )
                .expect("snapshot replay should preserve explicit keys");
        }

        assert_eq!(replayed.snapshot(), snapshot);
        assert_multigraph_core_invariants(&replayed);
    }

    proptest! {
        #[test]
        fn prop_core_invariants_hold_for_mixed_edge_mutations(
            ops in prop::collection::vec((0_u8..8, 0_u8..8, any::<bool>()), 1..80),
        ) {
            let mut graph = Graph::strict();
            let mut last_revision = graph.revision();

            for (left_id, right_id, is_add) in ops {
                let left = node_name(left_id);
                let right = node_name(right_id);
                if is_add {
                    prop_assert!(graph.add_edge(left.clone(), right.clone()).is_ok());
                } else {
                    let _ = graph.remove_edge(&left, &right);
                }
                let revision = graph.revision();
                prop_assert!(revision >= last_revision);
                last_revision = revision;
                assert_graph_core_invariants(&graph);
            }
        }

        #[test]
        fn prop_snapshot_is_deterministic_for_same_operation_stream(
            ops in prop::collection::vec((0_u8..8, 0_u8..8, 0_u8..3), 0..64),
        ) {
            let mut graph_left = Graph::hardened();
            let mut graph_right = Graph::hardened();

            for (left_id, right_id, attrs_variant) in ops {
                let left = node_name(left_id);
                let right = node_name(right_id);
                let mut attrs = AttrMap::new();
                if attrs_variant == 1 {
                    attrs.insert("weight".to_owned(), (left_id % 5).to_string().into());
                } else if attrs_variant == 2 {
                    attrs.insert("tag".to_owned(), format!("k{}", right_id % 4).into());
                }
                prop_assert!(
                    graph_left
                        .add_edge_with_attrs(left.clone(), right.clone(), attrs.clone())
                        .is_ok()
                );
                prop_assert!(
                    graph_right
                        .add_edge_with_attrs(left, right, attrs)
                        .is_ok()
                );
            }

            prop_assert_eq!(graph_left.snapshot(), graph_right.snapshot());
            prop_assert_eq!(graph_left.snapshot(), graph_left.snapshot());
        }

        #[test]
        fn prop_reapplying_identical_edge_attrs_is_revision_stable(
            left_id in 0_u8..8,
            right_id in 0_u8..8,
            weight in 0_u16..5000,
        ) {
            let mut graph = Graph::strict();
            let left = node_name(left_id);
            let right = node_name(right_id);
            let mut attrs = AttrMap::new();
            attrs.insert("weight".to_owned(), weight.to_string().into());

            prop_assert!(
                graph
                    .add_edge_with_attrs(left.clone(), right.clone(), attrs.clone())
                    .is_ok()
            );
            let revision_after_first = graph.revision();
            prop_assert!(
                graph
                    .add_edge_with_attrs(left, right, attrs)
                    .is_ok()
            );
            prop_assert_eq!(graph.revision(), revision_after_first);
        }

        #[test]
        fn prop_remove_node_clears_incident_edges(
            ops in prop::collection::vec((0_u8..8, 0_u8..8), 1..64),
            target_id in 0_u8..8,
        ) {
            let mut graph = Graph::strict();
            for (left_id, right_id) in ops {
                let left = node_name(left_id);
                let right = node_name(right_id);
                prop_assert!(graph.add_edge(left, right).is_ok());
            }

            let target = node_name(target_id);
            let removed = graph.remove_node(&target);
            if removed {
                prop_assert!(!graph.has_node(&target));
                for node in graph.nodes_ordered() {
                    let neighbors = graph
                        .neighbors(node)
                        .expect("graph nodes should always have adjacency buckets");
                    prop_assert!(!neighbors.contains(&target.as_str()));
                    prop_assert!(!graph.has_edge(node, &target));
                }
            }
            assert_graph_core_invariants(&graph);
        }

        #[test]
        fn prop_decision_ledger_records_follow_schema(
            ops in prop::collection::vec((0_u8..8, 0_u8..8, 0_u8..4), 1..72),
        ) {
            let mut graph = Graph::strict();
            for (left_id, right_id, attrs_kind) in ops {
                let left = node_name(left_id);
                let right = node_name(right_id);
                let mut attrs = AttrMap::new();
                match attrs_kind {
                    0 => {}
                    1 => {
                        attrs.insert("weight".to_owned(), (left_id % 9).to_string().into());
                    }
                    2 => {
                        attrs.insert("color".to_owned(), format!("c{}", right_id % 6).into());
                    }
                    _ => {
                        attrs.insert("__fnx_incompatible_decoder".to_owned(), "v2".into());
                    }
                }
                let _ = graph.add_edge_with_attrs(left, right, attrs);
            }

            let records = graph.evidence_ledger().records();
            prop_assert!(!records.is_empty());
            for record in records {
                assert_decision_record_schema(record, CompatibilityMode::Strict);
                if record.operation == "add_node" {
                    prop_assert_eq!(record.action, DecisionAction::Allow);
                    prop_assert!(record.evidence.iter().any(|term| term.signal == "node_preexisting"));
                    prop_assert!(record.evidence.iter().any(|term| term.signal == "attrs_count"));
                } else {
                    prop_assert_eq!(&record.operation, "add_edge");
                    if record.action == DecisionAction::FailClosed {
                        prop_assert!(
                            record
                                .evidence
                                .iter()
                                .any(|term| term.signal == "unknown_incompatible_feature")
                        );
                    } else {
                        prop_assert_eq!(record.action, DecisionAction::Allow);
                        // add_edge records two decisions: a pre-check (only
                        // unknown_incompatible_feature) and a post-check (with
                        // self_loop, edge_attr_count, etc.). Both are valid.
                        let is_precheck = record
                            .evidence
                            .iter()
                            .any(|term| term.signal == "unknown_incompatible_feature")
                            && !record
                                .evidence
                                .iter()
                                .any(|term| term.signal == "edge_attr_count");
                        if !is_precheck {
                            prop_assert!(record.evidence.iter().any(|term| term.signal == "edge_attr_count"));
                            prop_assert!(record.evidence.iter().any(|term| term.signal == "self_loop"));
                        }
                    }
                }
            }
        }
    }
}
