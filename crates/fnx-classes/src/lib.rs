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
                    if !graph.adj_indices[node_idx[s_idx]].contains(&node_idx[t_idx]) {
                        graph.adj_indices[node_idx[s_idx]].push(node_idx[t_idx]);
                    }
                    if node_idx[s_idx] != node_idx[t_idx]
                        && !graph.adj_indices[node_idx[t_idx]].contains(&node_idx[s_idx])
                    {
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
        let row = &self.adj_indices[idx];
        let mut count = row.len();
        if row.contains(&idx) {
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
                }
                if !self.adj_indices[left_idx].contains(&right_idx) {
                    self.adj_indices[left_idx].push(right_idx);
                }
                if left_idx != right_idx && !self.adj_indices[right_idx].contains(&left_idx) {
                    self.adj_indices[right_idx].push(left_idx);
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

#[derive(Debug, Clone)]
pub struct MultiGraph {
    mode: CompatibilityMode,
    revision: u64,
    nodes: FxIndexMap<String, AttrMap>,
    adjacency: FxIndexMap<String, IndexMap<String, IndexSet<usize>>>,
    edges: FxIndexMap<EdgeKey, IndexMap<usize, AttrMap>>,
    runtime_policy: RuntimePolicy,
    edge_count: usize,
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

    #[must_use]
    pub fn nodes_ordered(&self) -> Vec<&str> {
        self.nodes.keys().map(String::as_str).collect()
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
        let mut inserted = 0usize;
        for (left, right, key, attrs) in edges {
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

        let mut inserted = 0usize;
        for (left_idx, right_idx, key) in iterator {
            debug_assert!(left_idx < node_names.len());
            debug_assert!(right_idx < node_names.len());

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
        let edge_key = EdgeKeyRef::new(left, right);
        let removal_key = key.or_else(|| {
            self.edges
                .get(&edge_key)
                .and_then(|edge_bucket| edge_bucket.keys().next_back().copied())
        });

        let Some(removal_key) = removal_key else {
            return false;
        };

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
                    if nb.as_str() != rn && !remove_set.contains(nb.as_str())
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
            let keep = !remove_set.contains(key.left.as_str())
                && !remove_set.contains(key.right.as_str());
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
