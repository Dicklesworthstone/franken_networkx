//! NetworkX's default maximum-flow algorithm, `preflow_push`
//! (`networkx/algorithms/flow/preflowpush.py`, BSD-licensed), step for step
//! (br-r37-c1-uh5ua).
//!
//! A maximum flow is not unique. `nx.maximum_flow` returns the particular flow
//! its highest-label preflow-push leaves behind, and `nx.minimum_cut` reads its
//! partition from the residual network that algorithm's first phase leaves, so
//! matching networkx means making every order-dependent choice the Python makes:
//!
//! * the residual network's rows are in the order `build_residual_network`
//!   inserts edges: `G.edges(data=True)` order, each reverse edge right after
//!   its forward edge, zero-capacity edges and self-loops left out;
//! * the node `arbitrary_element(level.active)` picks is the first entry of a
//!   CPython `set` in slot order. That depends on every node's `hash()` and on
//!   the set's whole add / remove / update / clear history, so each level's
//!   active set is an exact model of CPython's set table ([`CPythonSet`]);
//! * values follow Python's int / float arithmetic ([`PyNum`]): flows and
//!   excesses start as the int `0`, an int capacity keeps a flow an int, a float
//!   makes it a float, int-float comparisons are exact, and `min` returns its
//!   first argument on a tie.
//!
//! Anything networkx can only reach by raising (a node in no level set, an
//! empty `min`) returns [`PreflowError::Diverged`] instead, as does an int that
//! leaves the `i64` range (Python's int would not), so a caller can hand those
//! inputs to networkx itself.

use rustc_hash::FxHashMap;
use std::cmp::Ordering;
use std::collections::VecDeque;

/// A Python `int` (within `i64`) or `float`, with Python's arithmetic and
/// exact mixed int-float comparison.
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum PyNum {
    Int(i64),
    Float(f64),
}

/// Why [`preflow_push`] declined to finish.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PreflowError {
    /// An int result left the `i64` range; Python's int would stay exact.
    IntOverflow,
    /// A state networkx only reaches by raising.
    Diverged,
}

impl PyNum {
    pub const ZERO: Self = Self::Int(0);

    fn add(self, other: Self) -> Result<Self, PreflowError> {
        Ok(match (self, other) {
            (Self::Int(a), Self::Int(b)) => {
                Self::Int(a.checked_add(b).ok_or(PreflowError::IntOverflow)?)
            }
            (Self::Int(a), Self::Float(b)) => Self::Float(a as f64 + b),
            (Self::Float(a), Self::Int(b)) => Self::Float(a + b as f64),
            (Self::Float(a), Self::Float(b)) => Self::Float(a + b),
        })
    }

    fn sub(self, other: Self) -> Result<Self, PreflowError> {
        Ok(match (self, other) {
            (Self::Int(a), Self::Int(b)) => {
                Self::Int(a.checked_sub(b).ok_or(PreflowError::IntOverflow)?)
            }
            (Self::Int(a), Self::Float(b)) => Self::Float(a as f64 - b),
            (Self::Float(a), Self::Int(b)) => Self::Float(a - b as f64),
            (Self::Float(a), Self::Float(b)) => Self::Float(a - b),
        })
    }

    /// Python's ordering: an int and a float compare by exact value, not by
    /// rounding the int to a float first.
    #[must_use]
    pub fn py_cmp(self, other: Self) -> Option<Ordering> {
        match (self, other) {
            (Self::Int(a), Self::Int(b)) => Some(a.cmp(&b)),
            (Self::Float(a), Self::Float(b)) => a.partial_cmp(&b),
            (Self::Int(a), Self::Float(b)) => int_float_cmp(a, b),
            (Self::Float(a), Self::Int(b)) => int_float_cmp(b, a).map(Ordering::reverse),
        }
    }

    fn lt(self, other: Self) -> bool {
        self.py_cmp(other) == Some(Ordering::Less)
    }

    #[must_use]
    pub fn py_eq(self, other: Self) -> bool {
        self.py_cmp(other) == Some(Ordering::Equal)
    }

    #[must_use]
    pub fn is_positive(self) -> bool {
        self.py_cmp(Self::ZERO) == Some(Ordering::Greater)
    }

    /// Python's `min(self, other)`: the first argument unless the second is
    /// strictly smaller.
    fn py_min(self, other: Self) -> Self {
        if other.lt(self) { other } else { self }
    }
}

fn int_float_cmp(int: i64, float: f64) -> Option<Ordering> {
    const EXACT: i64 = 1 << 53;
    const TWO_63: f64 = 9_223_372_036_854_775_808.0;
    if float.is_nan() {
        return None;
    }
    if (-EXACT..=EXACT).contains(&int) {
        return (int as f64).partial_cmp(&float);
    }
    if float >= TWO_63 {
        return Some(Ordering::Less);
    }
    if float < -TWO_63 {
        return Some(Ordering::Greater);
    }
    // |float| <= 2^63, so its integral part is exact in i64.
    let whole = float.trunc();
    match int.cmp(&(whole as i64)) {
        Ordering::Equal => 0.0_f64.partial_cmp(&(float - whole)),
        unequal => Some(unequal),
    }
}

const SLOT_EMPTY: u32 = u32::MAX;
const SLOT_DUMMY: u32 = u32::MAX - 1;
const SET_MINSIZE: usize = 8;
const LINEAR_PROBES: usize = 9;
const PERTURB_SHIFT: u32 = 5;

#[derive(Debug, Clone, Copy)]
struct SetEntry {
    key: u32,
    hash: usize,
}

const EMPTY_ENTRY: SetEntry = SetEntry {
    key: SLOT_EMPTY,
    hash: 0,
};

impl SetEntry {
    fn is_live(self) -> bool {
        self.key != SLOT_EMPTY && self.key != SLOT_DUMMY
    }
}

/// CPython's `set` hash table (`Objects/setobject.c`), as far as it decides
/// iteration order: `add`, `remove`, `update` from another set, `clear`, and
/// `next(iter(s))`. Keys are distinct `u32` ids standing for Python objects
/// that never compare equal; `hash` is the object's Python `hash()` as a
/// `size_t`. Checked against the real table on CPython 3.10-3.14.
#[derive(Debug, Clone, Default)]
pub struct CPythonSet {
    /// Empty until the first insertion, standing for the pristine 8-slot table.
    table: Vec<SetEntry>,
    /// Live plus dummy slots.
    fill: usize,
    used: usize,
}

impl CPythonSet {
    #[must_use]
    pub fn len(&self) -> usize {
        self.used
    }

    #[must_use]
    pub fn is_empty(&self) -> bool {
        self.used == 0
    }

    fn mask(&self) -> usize {
        self.table.len().max(SET_MINSIZE) - 1
    }

    /// `set.add`: the key goes into the LAST dummy slot its probe passed, or
    /// the empty slot that ended the probe.
    pub fn add(&mut self, key: u32, hash: usize) {
        if self.table.is_empty() {
            self.table = vec![EMPTY_ENTRY; SET_MINSIZE];
        }
        let mask = self.table.len() - 1;
        let mut perturb = hash;
        let mut i = hash & mask;
        let mut freeslot = None;
        loop {
            let probes = if i + LINEAR_PROBES <= mask {
                LINEAR_PROBES
            } else {
                0
            };
            for j in i..=i + probes {
                let entry = self.table[j];
                if entry.key == SLOT_EMPTY {
                    let entry = SetEntry { key, hash };
                    if let Some(free) = freeslot {
                        self.table[free] = entry;
                        self.used += 1;
                        return;
                    }
                    self.table[j] = entry;
                    self.fill += 1;
                    self.used += 1;
                    if self.fill * 5 >= mask * 3 {
                        let minused = if self.used > 50_000 {
                            self.used * 2
                        } else {
                            self.used * 4
                        };
                        self.resize(minused);
                    }
                    return;
                }
                if entry.key == SLOT_DUMMY {
                    freeslot = Some(j);
                } else if entry.key == key {
                    return;
                }
            }
            perturb >>= PERTURB_SHIFT;
            i = i.wrapping_mul(5).wrapping_add(1).wrapping_add(perturb) & mask;
        }
    }

    /// `set.remove` / `set.discard`: the slot becomes a dummy. Returns whether
    /// the key was present.
    pub fn remove(&mut self, key: u32, hash: usize) -> bool {
        if self.used == 0 {
            return false;
        }
        let mask = self.table.len() - 1;
        let mut perturb = hash;
        let mut i = hash & mask;
        loop {
            let probes = if i + LINEAR_PROBES <= mask {
                LINEAR_PROBES
            } else {
                0
            };
            for j in i..=i + probes {
                let entry = self.table[j];
                if entry.key == SLOT_EMPTY {
                    return false;
                }
                if entry.key == key {
                    self.table[j] = SetEntry {
                        key: SLOT_DUMMY,
                        hash: usize::MAX,
                    };
                    self.used -= 1;
                    return true;
                }
            }
            perturb >>= PERTURB_SHIFT;
            i = i.wrapping_mul(5).wrapping_add(1).wrapping_add(perturb) & mask;
        }
    }

    /// `set.clear`: back to the pristine 8-slot table.
    pub fn clear(&mut self) {
        *self = Self::default();
    }

    /// `self.update(other)` for another set (`set_merge`).
    pub fn update_from(&mut self, other: &Self) {
        if other.used == 0 {
            return;
        }
        if (self.fill + other.used) * 5 >= self.mask() * 3 {
            self.resize((self.used + other.used) * 2);
        }
        if self.table.is_empty() {
            self.table = vec![EMPTY_ENTRY; SET_MINSIZE];
        }
        if self.fill == 0 && self.table.len() == other.table.len() && other.fill == other.used {
            self.table.copy_from_slice(&other.table);
            self.fill = other.fill;
            self.used = other.used;
            return;
        }
        if self.fill == 0 {
            let mask = self.table.len() - 1;
            self.fill = other.used;
            self.used = other.used;
            for entry in other.table.iter().copied().filter(|entry| entry.is_live()) {
                insert_clean(&mut self.table, mask, entry);
            }
            return;
        }
        for entry in other.table.iter().copied().filter(|entry| entry.is_live()) {
            self.add(entry.key, entry.hash);
        }
    }

    /// `next(iter(s))`: the first live slot.
    #[must_use]
    pub fn first(&self) -> Option<u32> {
        if self.used == 0 {
            return None;
        }
        self.table
            .iter()
            .find(|entry| entry.is_live())
            .map(|entry| entry.key)
    }

    /// The keys in iteration (slot) order.
    pub fn iter(&self) -> impl Iterator<Item = u32> + '_ {
        self.table
            .iter()
            .filter(|entry| entry.is_live())
            .map(|entry| entry.key)
    }

    /// `set_table_resize`: the smallest power of two above `minused`, live
    /// entries re-inserted in slot order.
    fn resize(&mut self, minused: usize) {
        let mut size = SET_MINSIZE;
        while size <= minused {
            size <<= 1;
        }
        let old = std::mem::replace(&mut self.table, vec![EMPTY_ENTRY; size]);
        let mask = size - 1;
        for entry in old.into_iter().filter(|entry| entry.is_live()) {
            insert_clean(&mut self.table, mask, entry);
        }
        self.fill = self.used;
    }
}

/// `set_insert_clean`: the first empty slot along the probe sequence.
fn insert_clean(table: &mut [SetEntry], mask: usize, entry: SetEntry) {
    let mut perturb = entry.hash;
    let mut i = entry.hash & mask;
    loop {
        if table[i].key == SLOT_EMPTY {
            table[i] = entry;
            return;
        }
        if i + LINEAR_PROBES <= mask {
            for j in i + 1..=i + LINEAR_PROBES {
                if table[j].key == SLOT_EMPTY {
                    table[j] = entry;
                    return;
                }
            }
        }
        perturb >>= PERTURB_SHIFT;
        i = i.wrapping_mul(5).wrapping_add(1).wrapping_add(perturb) & mask;
    }
}

/// The input graph as `build_residual_network` reads it.
pub struct FlowNetworkInput<'a> {
    /// Python `hash()` of each node, as a `size_t`, in `G`'s node order.
    pub node_hashes: &'a [usize],
    /// `G.edges(data=True)` in order, as `(u, v, capacity)` node positions.
    /// Self-loops and non-positive capacities may be included; they are left
    /// out as networkx leaves them out.
    pub edges: &'a [(usize, usize, PyNum)],
    pub directed: bool,
    pub source: usize,
    pub sink: usize,
}

/// The residual network networkx's `preflow_push` returns: `R`'s rows in
/// insertion order with each edge's final flow.
#[derive(Debug, Clone)]
pub struct PreflowResidual {
    flow_value: PyNum,
    tail: Vec<u32>,
    head: Vec<u32>,
    capacity: Vec<PyNum>,
    flow: Vec<PyNum>,
    succ_offsets: Vec<usize>,
    succ: Vec<u32>,
    pred_offsets: Vec<usize>,
    pred: Vec<u32>,
}

impl PreflowResidual {
    /// `R.graph["flow_value"]`.
    #[must_use]
    pub fn flow_value(&self) -> PyNum {
        self.flow_value
    }

    /// `(v, flow)` for each `v` in `R[u]` whose flow is positive, in row order:
    /// what `build_flow_dict` writes over `G[u]`'s zeros.
    pub fn positive_flows(&self, node: usize) -> impl Iterator<Item = (usize, PyNum)> + '_ {
        self.succ[self.succ_offsets[node]..self.succ_offsets[node + 1]]
            .iter()
            .map(|&edge| (self.head[edge as usize] as usize, self.flow[edge as usize]))
            .filter(|&(_, flow)| flow.is_positive())
    }

    /// `minimum_cut`'s `non_reachable`: the nodes that still reach `sink` once
    /// every saturated edge (`flow == capacity`) is removed from `R`, in the
    /// breadth-first order `shortest_path_length(R, target=sink)` lists them.
    #[must_use]
    pub fn sink_side_bfs_order(&self, sink: usize) -> Vec<usize> {
        let n = self.succ_offsets.len() - 1;
        let mut seen = vec![false; n];
        seen[sink] = true;
        let mut order = vec![sink];
        let mut level_start = 0;
        while level_start < order.len() {
            let level_end = order.len();
            for position in level_start..level_end {
                let node = order[position];
                for &edge in &self.pred[self.pred_offsets[node]..self.pred_offsets[node + 1]] {
                    let edge = edge as usize;
                    if self.flow[edge].py_eq(self.capacity[edge]) {
                        continue;
                    }
                    let other = self.tail[edge] as usize;
                    if !seen[other] {
                        seen[other] = true;
                        order.push(other);
                    }
                }
            }
            level_start = level_end;
        }
        order
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Membership {
    None,
    Active,
    Inactive,
}

const UNSEEN: usize = usize::MAX;

struct PreflowState<'a> {
    hashes: &'a [usize],
    n: usize,
    source: usize,
    sink: usize,
    tail: Vec<u32>,
    head: Vec<u32>,
    reverse: Vec<u32>,
    capacity: Vec<PyNum>,
    flow: Vec<PyNum>,
    succ_offsets: Vec<usize>,
    succ: Vec<u32>,
    pred_offsets: Vec<usize>,
    pred: Vec<u32>,
    excess: Vec<PyNum>,
    height: Vec<usize>,
    current_edge: Vec<usize>,
    active: Vec<CPythonSet>,
    inactive: Vec<Vec<u32>>,
    inactive_position: Vec<usize>,
    membership: Vec<Membership>,
    work: usize,
    threshold: usize,
    bfs_height: Vec<usize>,
}

/// Run networkx's `preflow_push(G, s, t, value_only=value_only)` with its
/// default `global_relabel_freq=1`.
///
/// # Errors
///
/// [`PreflowError`] when networkx would raise or an int would overflow `i64`.
pub fn preflow_push(
    input: &FlowNetworkInput<'_>,
    value_only: bool,
) -> Result<PreflowResidual, PreflowError> {
    let mut state = PreflowState::build(input);
    let flow_value = state.run(value_only)?;
    Ok(PreflowResidual {
        flow_value,
        tail: state.tail,
        head: state.head,
        capacity: state.capacity,
        flow: state.flow,
        succ_offsets: state.succ_offsets,
        succ: state.succ,
        pred_offsets: state.pred_offsets,
        pred: state.pred,
    })
}

fn flatten_rows(rows: Vec<Vec<u32>>) -> (Vec<usize>, Vec<u32>) {
    let mut offsets = Vec::with_capacity(rows.len() + 1);
    offsets.push(0);
    let mut flat = Vec::with_capacity(rows.iter().map(Vec::len).sum());
    for row in rows {
        flat.extend_from_slice(&row);
        offsets.push(flat.len());
    }
    (offsets, flat)
}

impl<'a> PreflowState<'a> {
    /// `build_residual_network(G, capacity)`.
    fn build(input: &FlowNetworkInput<'a>) -> Self {
        let n = input.node_hashes.len();
        let mut succ_rows = vec![Vec::<u32>::new(); n];
        let mut pred_rows = vec![Vec::<u32>::new(); n];
        let mut tail = Vec::new();
        let mut head = Vec::new();
        let mut reverse = Vec::new();
        let mut capacity = Vec::new();
        let mut edge_index = FxHashMap::<(usize, usize), u32>::default();
        let mut add_edge = |u: usize, v: usize, cap: PyNum| -> u32 {
            let edge = u32::try_from(tail.len()).expect("residual edge count fits u32");
            tail.push(u as u32);
            head.push(v as u32);
            reverse.push(0);
            capacity.push(cap);
            succ_rows[u].push(edge);
            pred_rows[v].push(edge);
            edge_index.insert((u, v), edge);
            edge
        };
        for &(u, v, cap) in input.edges {
            if u == v || !cap.is_positive() {
                continue;
            }
            if input.directed {
                if let Some(&edge) = edge_index.get(&(u, v)) {
                    // (u, v) was added as the reverse of (v, u).
                    capacity[edge as usize] = cap;
                    continue;
                }
                let forward = add_edge(u, v, cap);
                let backward = add_edge(v, u, PyNum::ZERO);
                reverse[forward as usize] = backward;
                reverse[backward as usize] = forward;
            } else {
                let forward = add_edge(u, v, cap);
                let backward = add_edge(v, u, cap);
                reverse[forward as usize] = backward;
                reverse[backward as usize] = forward;
            }
        }
        let m = tail.len();
        let (succ_offsets, succ) = flatten_rows(succ_rows);
        let (pred_offsets, pred) = flatten_rows(pred_rows);
        let level_count = 2 * n;
        Self {
            hashes: input.node_hashes,
            n,
            source: input.source,
            sink: input.sink,
            tail,
            head,
            reverse,
            capacity,
            flow: vec![PyNum::ZERO; m],
            succ_offsets,
            succ,
            pred_offsets,
            pred,
            excess: vec![PyNum::ZERO; n],
            height: vec![0; n],
            current_edge: vec![0; n],
            active: vec![CPythonSet::default(); level_count],
            inactive: vec![Vec::new(); level_count],
            inactive_position: vec![0; n],
            membership: vec![Membership::None; n],
            work: 0,
            // GlobalRelabelThreshold(n, R.size(), freq=1): (n + m) / 1.
            threshold: n + m,
            bfs_height: vec![UNSEEN; n],
        }
    }

    fn succ_row(&self, node: usize) -> &[u32] {
        &self.succ[self.succ_offsets[node]..self.succ_offsets[node + 1]]
    }

    /// `reverse_bfs(src)`: the heights dict, in insertion order. Leaves
    /// `bfs_height` filled for the returned nodes; the caller resets it.
    fn reverse_bfs(&mut self, src: usize) -> Vec<(usize, usize)> {
        let mut order = vec![(src, 0_usize)];
        self.bfs_height[src] = 0;
        let mut position = 0;
        while position < order.len() {
            let (node, height) = order[position];
            position += 1;
            let height = height + 1;
            for index in self.pred_offsets[node]..self.pred_offsets[node + 1] {
                let edge = self.pred[index] as usize;
                let other = self.tail[edge] as usize;
                if self.bfs_height[other] == UNSEEN && self.flow[edge].lt(self.capacity[edge]) {
                    self.bfs_height[other] = height;
                    order.push((other, height));
                }
            }
        }
        order
    }

    fn reset_bfs(&mut self, order: &[(usize, usize)]) {
        for &(node, _) in order {
            self.bfs_height[node] = UNSEEN;
        }
    }

    fn push(&mut self, node: usize, edge: usize, amount: PyNum) -> Result<(), PreflowError> {
        let other = self.head[edge] as usize;
        let back = self.reverse[edge] as usize;
        self.flow[edge] = self.flow[edge].add(amount)?;
        self.flow[back] = self.flow[back].sub(amount)?;
        self.excess[node] = self.excess[node].sub(amount)?;
        self.excess[other] = self.excess[other].add(amount)?;
        Ok(())
    }

    fn level(&self, height: usize) -> Result<usize, PreflowError> {
        if height < self.active.len() {
            Ok(height)
        } else {
            Err(PreflowError::Diverged)
        }
    }

    fn add_active(&mut self, height: usize, node: usize) -> Result<(), PreflowError> {
        let level = self.level(height)?;
        self.active[level].add(node as u32, self.hashes[node]);
        self.membership[node] = Membership::Active;
        Ok(())
    }

    fn remove_active(&mut self, height: usize, node: usize) -> Result<(), PreflowError> {
        let level = self.level(height)?;
        if !self.active[level].remove(node as u32, self.hashes[node]) {
            return Err(PreflowError::Diverged);
        }
        self.membership[node] = Membership::None;
        Ok(())
    }

    fn add_inactive(&mut self, height: usize, node: usize) -> Result<(), PreflowError> {
        let level = self.level(height)?;
        self.inactive_position[node] = self.inactive[level].len();
        self.inactive[level].push(node as u32);
        self.membership[node] = Membership::Inactive;
        Ok(())
    }

    fn remove_inactive(&mut self, height: usize, node: usize) -> Result<(), PreflowError> {
        let level = self.level(height)?;
        if self.membership[node] != Membership::Inactive {
            return Err(PreflowError::Diverged);
        }
        let position = self.inactive_position[node];
        let last = self.inactive[level].pop().ok_or(PreflowError::Diverged)?;
        if last as usize != node {
            self.inactive[level][position] = last;
            self.inactive_position[last as usize] = position;
        }
        self.membership[node] = Membership::None;
        Ok(())
    }

    /// `activate(v)`.
    fn activate(&mut self, node: usize) -> Result<(), PreflowError> {
        if node != self.source && node != self.sink && self.membership[node] == Membership::Inactive
        {
            let height = self.height[node];
            self.remove_inactive(height, node)?;
            self.add_active(height, node)?;
        }
        Ok(())
    }

    /// `relabel(u)`.
    fn relabel(&mut self, node: usize) -> Result<usize, PreflowError> {
        let row = self.succ_offsets[node]..self.succ_offsets[node + 1];
        self.work += row.len();
        self.succ[row]
            .iter()
            .map(|&edge| edge as usize)
            .filter(|&edge| self.flow[edge].lt(self.capacity[edge]))
            .map(|edge| self.height[self.head[edge] as usize])
            .min()
            .map(|lowest| lowest + 1)
            .ok_or(PreflowError::Diverged)
    }

    /// `discharge(u, is_phase1)`: returns `next_height`.
    fn discharge(&mut self, node: usize, is_phase1: bool) -> Result<usize, PreflowError> {
        let mut height = self.height[node];
        let mut next_height = height;
        self.remove_active(height, node)?;
        let degree = self.succ_row(node).len();
        if degree == 0 {
            return Err(PreflowError::Diverged);
        }
        loop {
            let edge = self.succ[self.succ_offsets[node] + self.current_edge[node]] as usize;
            let other = self.head[edge] as usize;
            if height == self.height[other] + 1 && self.flow[edge].lt(self.capacity[edge]) {
                let residual = self.capacity[edge].sub(self.flow[edge])?;
                let amount = self.excess[node].py_min(residual);
                self.push(node, edge, amount)?;
                self.activate(other)?;
                if self.excess[node].py_eq(PyNum::ZERO) {
                    self.add_inactive(height, node)?;
                    break;
                }
            }
            self.current_edge[node] += 1;
            if self.current_edge[node] == degree {
                // CurrentEdge.move_to_next ran off the end: it rewinds, and
                // discharge relabels.
                self.current_edge[node] = 0;
                height = self.relabel(node)?;
                if is_phase1 && height + 1 >= self.n {
                    self.add_active(height, node)?;
                    break;
                }
                next_height = height;
            }
        }
        self.height[node] = height;
        Ok(next_height)
    }

    /// `gap_heuristic(height)`, reading the caller's `max_height`.
    fn gap_heuristic(&mut self, gap: usize, max_height: usize) {
        let target = self.n + 1;
        let end = (max_height + 1).min(self.active.len());
        for level in gap + 1..end {
            let active = std::mem::take(&mut self.active[level]);
            let inactive = std::mem::take(&mut self.inactive[level]);
            for node in active.iter().chain(inactive.iter().copied()) {
                self.height[node as usize] = target;
            }
            if level == target {
                // `levels[n + 1].active.update(levels[n + 1].active)` is a no-op,
                // and the clears that follow empty the level.
                for node in active.iter().chain(inactive.iter().copied()) {
                    self.membership[node as usize] = Membership::None;
                }
                continue;
            }
            self.active[target].update_from(&active);
            for node in inactive {
                self.inactive_position[node as usize] = self.inactive[target].len();
                self.inactive[target].push(node);
            }
        }
    }

    /// `global_relabel(from_sink)`: returns its `max_height`.
    fn global_relabel(&mut self, from_sink: bool) -> Result<usize, PreflowError> {
        let n = self.n;
        let src = if from_sink { self.sink } else { self.source };
        let mut heights = self.reverse_bfs(src);
        // The dict as a list; deleted entries are dropped from it.
        if !from_sink {
            let Some(position) = heights.iter().position(|&(node, _)| node == self.sink) else {
                self.reset_bfs(&heights);
                return Err(PreflowError::Diverged);
            };
            heights.remove(position);
            self.bfs_height[self.sink] = UNSEEN;
        }
        let mut max_height = heights.iter().map(|&(_, height)| height).max().unwrap_or(0);
        if from_sink {
            for node in 0..n {
                if self.bfs_height[node] == UNSEEN && self.height[node] < n {
                    self.bfs_height[node] = n + 1;
                    heights.push((node, n + 1));
                }
            }
        } else {
            for entry in &mut heights {
                entry.1 += n;
            }
            max_height += n;
        }
        self.reset_bfs(&heights);
        for &(node, new_height) in &heights {
            if node == src {
                continue;
            }
            let old_height = self.height[node];
            if new_height != old_height {
                if self.membership[node] == Membership::Active {
                    self.remove_active(old_height, node)?;
                    self.add_active(new_height, node)?;
                } else {
                    self.remove_inactive(old_height, node)?;
                    self.add_inactive(new_height, node)?;
                }
                self.height[node] = new_height;
            }
        }
        Ok(max_height)
    }

    fn first_active(&self, height: usize) -> Option<usize> {
        self.active
            .get(height)
            .and_then(CPythonSet::first)
            .map(|node| node as usize)
    }

    /// `preflow_push_impl`, from `detect_unboundedness` on (no edge carries the
    /// simulated infinite capacity, since every capacity here is finite).
    fn run(&mut self, value_only: bool) -> Result<PyNum, PreflowError> {
        let n = self.n;
        let (source, sink) = (self.source, self.sink);
        let initial = self.reverse_bfs(sink);
        self.reset_bfs(&initial);
        if !initial.iter().any(|&(node, _)| node == source) {
            return Ok(PyNum::ZERO);
        }
        let mut max_height = initial
            .iter()
            .filter(|&&(node, _)| node != source)
            .map(|&(_, height)| height)
            .max()
            .unwrap_or(0);
        self.height.fill(n + 1);
        for &(node, height) in &initial {
            self.height[node] = height;
        }
        self.height[source] = n;

        for index in self.succ_offsets[source]..self.succ_offsets[source + 1] {
            let edge = self.succ[index] as usize;
            let amount = self.capacity[edge];
            if amount.is_positive() {
                self.push(source, edge, amount)?;
            }
        }

        for node in 0..n {
            if node != source && node != sink {
                let height = self.height[node];
                if self.excess[node].is_positive() {
                    self.add_active(height, node)?;
                } else {
                    self.add_inactive(height, node)?;
                }
            }
        }

        // Phase 1: a maximum preflow.
        let mut height = max_height as isize;
        while height > 0 {
            loop {
                let level = height as usize;
                let Some(node) = self.first_active(level) else {
                    height -= 1;
                    break;
                };
                let old_height = level;
                height = self.discharge(node, true)? as isize;
                if self.work >= self.threshold {
                    let relabeled = self.global_relabel(true)?;
                    height = relabeled as isize;
                    max_height = relabeled;
                    self.work = 0;
                } else if self.active[old_height].is_empty()
                    && self.inactive[old_height].is_empty()
                {
                    self.gap_heuristic(old_height, max_height);
                    height = old_height as isize - 1;
                    max_height = old_height - 1;
                } else {
                    max_height = max_height.max(height as usize);
                }
                if height < 0 {
                    return Err(PreflowError::Diverged);
                }
            }
        }

        if !value_only {
            // Phase 2: return the excess to the source.
            let mut height = self.global_relabel(false)?;
            self.work = 0;
            while height > n {
                loop {
                    let Some(node) = self.first_active(height) else {
                        height -= 1;
                        break;
                    };
                    height = self.discharge(node, false)?;
                    if self.work >= self.threshold {
                        height = self.global_relabel(false)?;
                        self.work = 0;
                    }
                }
            }
        }
        Ok(self.excess[sink])
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Python's `hash()` of a small int as a `size_t` (`hash(-1) == -2`).
    fn int_hash(value: i64) -> usize {
        (if value == -1 { -2 } else { value }) as isize as usize
    }

    /// Labels stand for themselves: key `i` is the int `labels[i]`.
    struct IntSets {
        labels: Vec<i64>,
    }

    impl IntSets {
        fn key(&mut self, label: i64) -> u32 {
            match self.labels.iter().position(|&known| known == label) {
                Some(key) => key as u32,
                None => {
                    self.labels.push(label);
                    (self.labels.len() - 1) as u32
                }
            }
        }

        fn build(&mut self, adds: &[i64], removes: &[i64]) -> CPythonSet {
            let mut set = CPythonSet::default();
            for &label in adds {
                let key = self.key(label);
                set.add(key, int_hash(label));
            }
            for &label in removes {
                let key = self.key(label);
                assert!(set.remove(key, int_hash(label)));
            }
            set
        }

        fn order(&self, set: &CPythonSet) -> Vec<i64> {
            set.iter().map(|key| self.labels[key as usize]).collect()
        }
    }

    // Every expected order below is CPython's own `list(s)` after the same
    // operations (3.13 and 3.14 agree); none of them is insertion order.
    #[test]
    fn set_add_follows_cpython_probing_and_resizes() {
        let mut sets = IntSets { labels: Vec::new() };
        let set = sets.build(&[9, 1, 17, 25, 2], &[]);
        assert_eq!(sets.order(&set), vec![1, 2, 9, 17, 25]);
        let grown: Vec<i64> = (0..12).map(|i| i * 1024).collect();
        let set = sets.build(&grown, &[]);
        assert_eq!(
            sets.order(&set),
            vec![0, 1024, 4096, 2048, 3072, 5120, 6144, 7168, 8192, 9216, 10240, 11264]
        );
        let set = sets.build(&[-1, -2, -9, 7, -17], &[]);
        assert_eq!(sets.order(&set), vec![7, -17, -2, -9, -1]);
        assert_eq!(set.first(), Some(sets.key(7)));
    }

    #[test]
    fn set_add_reuses_the_last_dummy_on_its_probe_path() {
        // 32 probes slot 0 (dummy), then slot 2 (dummy), then an empty slot:
        // CPython stores it in slot 2. A first-dummy model gives [32, 8].
        let mut sets = IntSets { labels: Vec::new() };
        let mut set = sets.build(&[0, 8, 2], &[0, 2]);
        let key = sets.key(32);
        set.add(key, int_hash(32));
        assert_eq!(sets.order(&set), vec![8, 32]);
        assert_eq!(set.len(), 2);
        let zero = sets.key(0);
        assert!(!set.remove(zero, int_hash(0)));
    }

    #[test]
    fn set_update_takes_each_set_merge_path() {
        let mut sets = IntSets { labels: Vec::new() };
        // Empty target, same table size, no dummies: slots copied verbatim.
        let other = sets.build(&[5, 13, 21], &[]);
        let mut target = CPythonSet::default();
        target.update_from(&other);
        assert_eq!(sets.order(&target), vec![13, 21, 5]);
        // Empty target, other has a dummy: insert_clean in other's slot order.
        let other = sets.build(&[5, 13, 21, 29], &[5]);
        let mut target = CPythonSet::default();
        target.update_from(&other);
        assert_eq!(sets.order(&target), vec![13, 21, 29]);
        // Non-empty target (a dummy keeps fill > 0): one add per entry.
        let other = sets.build(&[3, 11, 19], &[]);
        let mut target = sets.build(&[2, 10], &[2]);
        target.update_from(&other);
        assert_eq!(sets.order(&target), vec![19, 3, 10, 11]);
        // A merge that resizes the target first.
        let other_labels: Vec<i64> = (100..160).step_by(3).collect();
        let other = sets.build(&other_labels, &[]);
        let mut target = sets.build(&[7, 15], &[]);
        target.update_from(&other);
        assert_eq!(
            sets.order(&target),
            vec![
                130, 133, 7, 136, 139, 142, 15, 145, 148, 151, 154, 157, 100, 103, 106, 109, 112,
                115, 118, 121, 124, 127
            ]
        );
        // clear() returns to the 8-slot table.
        target.clear();
        for label in [17, 1] {
            let key = sets.key(label);
            target.add(key, int_hash(label));
        }
        assert_eq!(sets.order(&target), vec![17, 1]);
    }

    #[test]
    fn int_float_comparison_is_exact_like_python() {
        let big = (1_i64 << 53) + 1;
        // Python: 2**53 + 1 > float(2**53 + 1) (the float rounds down to 2**53).
        assert_eq!(
            PyNum::Int(big).py_cmp(PyNum::Float(big as f64)),
            Some(Ordering::Greater)
        );
        assert!(PyNum::Int(3).py_eq(PyNum::Float(3.0)));
        assert_eq!(PyNum::Int(-1).py_cmp(PyNum::Float(-0.5)), Some(Ordering::Less));
        assert_eq!(PyNum::Float(0.5).py_min(PyNum::Int(1)), PyNum::Float(0.5));
        // min keeps the first argument on a tie, type included.
        assert_eq!(PyNum::Int(2).py_min(PyNum::Float(2.0)), PyNum::Int(2));
        assert_eq!(PyNum::Float(2.0).py_min(PyNum::Int(2)), PyNum::Float(2.0));
        assert_eq!(PyNum::Int(i64::MAX).add(PyNum::Int(1)), Err(PreflowError::IntOverflow));
    }
}
