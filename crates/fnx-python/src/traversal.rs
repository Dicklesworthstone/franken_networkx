//! Incremental traversal over caller-owned Python adjacency rows.
//!
//! The queue and traversal loop live in Rust, while owned Python iterators keep
//! the graph's ordering, node identities, and between-yield mutation behavior.
//! No native graph borrow or adjacency snapshot survives an iterator step.

use std::collections::VecDeque;

use pyo3::exceptions::{PyRuntimeError, PyStopIteration, PyValueError};
use pyo3::gc::{PyTraverseError, PyVisit};
use pyo3::intern;
use pyo3::prelude::*;
use pyo3::types::{PyAny, PyIterator, PyModule, PySet, PyTuple};

fn generator_result<T>(py: Python<'_>, result: PyResult<T>) -> PyResult<T> {
    match result {
        Err(error) if error.is_instance_of::<PyStopIteration>(py) => {
            // Callback StopIteration escapes a Python generator as RuntimeError
            // (PEP 479). Only the row iterator's next() treats it as exhaustion.
            let converted = PyRuntimeError::new_err("generator raised StopIteration");
            converted
                .value(py)
                .setattr(intern!(py, "__context__"), error.value(py))?;
            converted.set_cause(py, Some(error));
            Err(converted)
        }
        result => result,
    }
}

struct TraversalRow {
    node: Py<PyAny>,
    children: Py<PyAny>,
    cursor: Option<Py<PyIterator>>,
}

impl TraversalRow {
    fn next_child<'py>(&mut self, py: Python<'py>) -> PyResult<Option<Bound<'py, PyAny>>> {
        if self.cursor.is_none() {
            self.cursor = Some(self.children.bind(py).try_iter()?.unbind());
        }
        self.cursor
            .as_ref()
            .expect("activated row iterator")
            .bind(py)
            .clone()
            .next()
            .transpose()
    }

    fn traverse(&self, visit: &PyVisit<'_>) -> Result<(), PyTraverseError> {
        visit.call(&self.node)?;
        visit.call(&self.children)?;
        visit.call(&self.cursor)
    }
}

struct BfsState {
    graph: Py<PyAny>,
    source: Py<PyAny>,
    reverse: bool,
    depth_limit: Option<usize>,
    neighbors: Option<Py<PyAny>>,
    seen: Option<Py<PySet>>,
    initial_node_count: usize,
    depth: usize,
    frontier: VecDeque<TraversalRow>,
    following: VecDeque<TraversalRow>,
}

impl BfsState {
    fn initialize(&mut self, py: Python<'_>) -> PyResult<()> {
        let graph = self.graph.bind(py);
        let method_name = if self.reverse
            && graph
                .call_method0(intern!(py, "is_directed"))?
                .is_truthy()?
        {
            intern!(py, "predecessors")
        } else {
            intern!(py, "neighbors")
        };
        let neighbors = graph.getattr(method_name)?;
        if self.depth_limit.is_none() {
            self.depth_limit = Some(graph.len()?);
        }
        let seen = PySet::empty(py)?;
        seen.add(self.source.bind(py))?;
        // A source's hash can run Python and mutate the graph. Capture this
        // separately from the default depth limit, after creating the set.
        self.initial_node_count = graph.len()?;
        let children = neighbors.call1((self.source.bind(py),))?;
        self.frontier.push_back(TraversalRow {
            node: self.source.clone_ref(py),
            children: children.unbind(),
            cursor: None,
        });
        self.seen = Some(seen.unbind());
        self.neighbors = Some(neighbors.unbind());
        Ok(())
    }

    fn advance(&mut self, py: Python<'_>) -> PyResult<Option<Py<PyAny>>> {
        if self.neighbors.is_none() {
            self.initialize(py)?;
        }
        let depth_limit = self.depth_limit.expect("initialized depth limit");
        let neighbors = self.neighbors.as_ref().expect("initialized neighbors");
        let seen = self
            .seen
            .as_ref()
            .expect("initialized visited set")
            .bind(py);

        loop {
            if self.depth >= depth_limit {
                return Ok(None);
            }
            let Some(row) = self.frontier.front_mut() else {
                if self.following.is_empty() {
                    return Ok(None);
                }
                self.frontier = std::mem::take(&mut self.following);
                self.depth += 1;
                continue;
            };

            let child = row.next_child(py)?;
            if let Some(child) = child {
                // Use Python's membership protocol, which accepts a mutable
                // set lookup by checking its frozen equivalent. PySet_Contains
                // instead raises immediately, changing generator yield timing.
                if seen.as_any().contains(&child)? {
                    continue;
                }
                seen.add(&child)?;
                // Obtain the child's row before yielding. Ordinary neighbors
                // already returns a live cursor; a custom iterable must not
                // receive __iter__ until its parent row is consumed.
                let children = neighbors.bind(py).call1((&child,))?;
                let edge = PyTuple::new(py, [row.node.bind(py), &child])?;
                self.following.push_back(TraversalRow {
                    node: child.unbind(),
                    children: children.unbind(),
                    cursor: None,
                });
                return Ok(Some(edge.into_any().unbind()));
            }

            self.frontier.pop_front();
            // Stop only after finishing a whole parent row, not at the yield
            // which happens to discover the last initially present node.
            if seen.len() == self.initial_node_count {
                return Ok(None);
            }
        }
    }

    fn traverse(&self, visit: &PyVisit<'_>) -> Result<(), PyTraverseError> {
        visit.call(&self.graph)?;
        visit.call(&self.source)?;
        visit.call(&self.neighbors)?;
        visit.call(&self.seen)?;
        for row in self.frontier.iter().chain(&self.following) {
            row.traverse(visit)?;
        }
        Ok(())
    }
}

/// A live breadth-first traversal with no precomputed edge output.
#[pyclass(name = "_BfsEdgesIterator", module = "franken_networkx._fnx")]
pub struct BfsEdgesIterator {
    state: Option<BfsState>,
}

#[pymethods]
impl BfsEdgesIterator {
    fn __iter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> {
        slf
    }

    fn __next__(&mut self, py: Python<'_>) -> PyResult<Option<Py<PyAny>>> {
        let Some(state) = self.state.as_mut() else {
            return Ok(None);
        };
        let result = state.advance(py);
        if !matches!(&result, Ok(Some(_))) {
            self.state = None;
        }
        generator_result(py, result)
    }

    fn __traverse__(&self, visit: PyVisit<'_>) -> Result<(), PyTraverseError> {
        if let Some(state) = &self.state {
            state.traverse(&visit)?;
        }
        Ok(())
    }

    fn __clear__(&mut self) {
        self.state = None;
    }
}

/// Defer graph reads and source validation until the first requested edge.
#[pyfunction]
#[pyo3(signature = (g, source, reverse=false, depth_limit=None))]
pub fn bfs_edges_iter(
    g: &Bound<'_, PyAny>,
    source: &Bound<'_, PyAny>,
    reverse: bool,
    depth_limit: Option<usize>,
) -> BfsEdgesIterator {
    BfsEdgesIterator {
        state: Some(BfsState {
            graph: g.clone().unbind(),
            source: source.clone().unbind(),
            reverse,
            depth_limit,
            neighbors: None,
            seen: None,
            initial_node_count: 0,
            depth: 0,
            frontier: VecDeque::new(),
            following: VecDeque::new(),
        }),
    }
}

#[derive(Clone, Copy, PartialEq, Eq)]
enum DfsOrder {
    Edges,
    Preorder,
    Postorder,
}

enum DfsRoots {
    Single(Option<Py<PyAny>>),
    Forest(Option<Py<PyIterator>>),
}

struct DfsDiscovery {
    node: Py<PyAny>,
    root: bool,
}

struct DfsState {
    graph: Py<PyAny>,
    roots: DfsRoots,
    depth_limit: Option<usize>,
    order: DfsOrder,
    neighbors: Option<Py<PyAny>>,
    seen: Option<Py<PySet>>,
    stack: Vec<TraversalRow>,
    pending: Option<DfsDiscovery>,
}

impl DfsState {
    fn initialize(&mut self, py: Python<'_>) -> PyResult<()> {
        let graph = self.graph.bind(py);
        if self.depth_limit.is_none() {
            self.depth_limit = Some(graph.len()?);
        }
        self.neighbors = Some(graph.getattr(intern!(py, "neighbors"))?.unbind());
        self.seen = Some(PySet::empty(py)?.unbind());
        if let DfsRoots::Forest(cursor) = &mut self.roots {
            *cursor = Some(graph.try_iter()?.unbind());
        }
        Ok(())
    }

    fn next_root(&mut self, py: Python<'_>) -> PyResult<Option<Py<PyAny>>> {
        match &mut self.roots {
            DfsRoots::Single(source) => Ok(source.take()),
            DfsRoots::Forest(cursor) => cursor
                .as_ref()
                .expect("initialized forest iterator")
                .bind(py)
                .clone()
                .next()
                .transpose()
                .map(|node| node.map(Bound::unbind)),
        }
    }

    fn activate_pending(&mut self, py: Python<'_>) -> PyResult<()> {
        let Some(discovery) = self.pending.take() else {
            return Ok(());
        };
        self.seen
            .as_ref()
            .expect("initialized visited set")
            .bind(py)
            .add(discovery.node.bind(py))?;
        if discovery.root || self.stack.len() < self.depth_limit.expect("initialized depth limit") {
            let children = self
                .neighbors
                .as_ref()
                .expect("initialized neighbors")
                .bind(py)
                .call1((discovery.node.bind(py),))?;
            // Pre/postorder project labeled DFS, which wraps a non-root
            // provider result in iter() when pushing it. Edge DFS retains
            // the provider result itself. Custom iterable callbacks expose
            // that distinction even though ordinary graph rows are iterators.
            let children = if !discovery.root && self.order != DfsOrder::Edges {
                children.try_iter()?.into_any()
            } else {
                children
            };
            if let Some(parent) = self.stack.last_mut() {
                // Descent breaks the parent's for loop. When it resumes,
                // iterate the retained provider object again, as Python does.
                parent.cursor = None;
            }
            self.stack.push(TraversalRow {
                node: discovery.node,
                children: children.unbind(),
                cursor: None,
            });
        }
        Ok(())
    }

    fn advance(&mut self, py: Python<'_>) -> PyResult<Option<Py<PyAny>>> {
        if self.neighbors.is_none() {
            self.initialize(py)?;
        }
        loop {
            // A forward event suspends before marking the node or looking up
            // its row. Caller mutations between yields therefore take effect
            // before the first access to that newly discovered node.
            self.activate_pending(py)?;
            if let Some(row) = self.stack.last_mut() {
                let child = row.next_child(py)?;
                let Some(child) = child else {
                    let finished = self.stack.pop().expect("active stack row");
                    if self.order == DfsOrder::Postorder {
                        return Ok(Some(finished.node));
                    }
                    continue;
                };
                if self
                    .seen
                    .as_ref()
                    .expect("initialized visited set")
                    .bind(py)
                    .as_any()
                    .contains(&child)?
                {
                    continue;
                }
                self.pending = Some(DfsDiscovery {
                    node: child.clone().unbind(),
                    root: false,
                });
                match self.order {
                    DfsOrder::Edges => {
                        let edge = PyTuple::new(py, [row.node.bind(py), &child])?;
                        return Ok(Some(edge.into_any().unbind()));
                    }
                    DfsOrder::Preorder => return Ok(Some(child.unbind())),
                    DfsOrder::Postorder => continue,
                }
            }

            let Some(root) = self.next_root(py)? else {
                return Ok(None);
            };
            if self
                .seen
                .as_ref()
                .expect("initialized visited set")
                .bind(py)
                .as_any()
                .contains(root.bind(py))?
            {
                continue;
            }
            self.pending = Some(DfsDiscovery {
                node: root.clone_ref(py),
                root: true,
            });
            if self.order == DfsOrder::Preorder {
                // In particular, a missing explicit source appears here and
                // fails only when its adjacency is requested on the next step.
                return Ok(Some(root));
            }
        }
    }

    fn traverse(&self, visit: &PyVisit<'_>) -> Result<(), PyTraverseError> {
        visit.call(&self.graph)?;
        visit.call(&self.neighbors)?;
        visit.call(&self.seen)?;
        match &self.roots {
            DfsRoots::Single(source) => visit.call(source)?,
            DfsRoots::Forest(cursor) => visit.call(cursor)?,
        }
        if let Some(discovery) = &self.pending {
            visit.call(&discovery.node)?;
        }
        for row in &self.stack {
            row.traverse(visit)?;
        }
        Ok(())
    }
}

/// A live depth-first traversal with suspension at the public output events.
#[pyclass(name = "_DfsTraversalIterator", module = "franken_networkx._fnx")]
pub struct DfsTraversalIterator {
    state: Option<DfsState>,
}

#[pymethods]
impl DfsTraversalIterator {
    fn __iter__(slf: PyRef<'_, Self>) -> PyRef<'_, Self> {
        slf
    }

    fn __next__(&mut self, py: Python<'_>) -> PyResult<Option<Py<PyAny>>> {
        let Some(state) = self.state.as_mut() else {
            return Ok(None);
        };
        let result = state.advance(py);
        if !matches!(&result, Ok(Some(_))) {
            self.state = None;
        }
        generator_result(py, result)
    }

    fn __traverse__(&self, visit: PyVisit<'_>) -> Result<(), PyTraverseError> {
        if let Some(state) = &self.state {
            state.traverse(&visit)?;
        }
        Ok(())
    }

    fn __clear__(&mut self) {
        self.state = None;
    }
}

/// Stream DFS edges or nodes without snapshotting the graph or output.
#[pyfunction]
#[pyo3(signature = (g, source=None, depth_limit=None, order="edges"))]
pub fn dfs_traversal_iter(
    g: &Bound<'_, PyAny>,
    source: Option<&Bound<'_, PyAny>>,
    depth_limit: Option<usize>,
    order: &str,
) -> PyResult<DfsTraversalIterator> {
    let order = match order {
        "edges" => DfsOrder::Edges,
        "preorder" => DfsOrder::Preorder,
        "postorder" => DfsOrder::Postorder,
        _ => {
            return Err(PyValueError::new_err(
                "order must be 'edges', 'preorder', or 'postorder'",
            ));
        }
    };
    let roots = match source {
        Some(source) => DfsRoots::Single(Some(source.clone().unbind())),
        None => DfsRoots::Forest(None),
    };
    Ok(DfsTraversalIterator {
        state: Some(DfsState {
            graph: g.clone().unbind(),
            roots,
            depth_limit,
            order,
            neighbors: None,
            seen: None,
            stack: Vec::new(),
            pending: None,
        }),
    })
}

pub fn register(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_class::<BfsEdgesIterator>()?;
    module.add_function(wrap_pyfunction!(bfs_edges_iter, module)?)?;
    module.add_class::<DfsTraversalIterator>()?;
    module.add_function(wrap_pyfunction!(dfs_traversal_iter, module)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn graph(py: Python<'_>) -> PyResult<Bound<'_, PyAny>> {
        let module = PyModule::from_code(
            py,
            c"class Graph:\n    def __init__(self):\n        self.rows = {0: {1: None}, 1: {2: None}, 2: {}, 3: {}}\n        self.reads = []\n    def __len__(self):\n        return len(self.rows)\n    def neighbors(self, node):\n        self.reads.append(node)\n        return iter(self.rows[node])\ngraph = Graph()\n",
            c"test_traversal.py",
            c"test_traversal",
        )?;
        module.getattr("graph")
    }

    #[test]
    fn bfs_opens_child_row_before_yield_and_closes_after_error() -> PyResult<()> {
        Python::initialize();
        Python::attach(|py| {
            let graph = graph(py)?;
            let source = 0_i64.into_pyobject(py)?;
            let mut traversal = bfs_edges_iter(&graph, source.as_any(), false, None);
            assert_eq!(graph.getattr("reads")?.len()?, 0);
            let edge = traversal.__next__(py)?.expect("first edge");
            assert_eq!(edge.bind(py).extract::<(i64, i64)>()?, (0, 1));
            assert_eq!(graph.getattr("reads")?.extract::<Vec<i64>>()?, [0, 1]);
            graph.getattr("rows")?.get_item(1)?.set_item(3, py.None())?;
            let error = traversal.__next__(py).expect_err("live row changed size");
            assert!(error.is_instance_of::<PyRuntimeError>(py));
            assert!(traversal.__next__(py)?.is_none());
            Ok(())
        })
    }

    #[test]
    fn bfs_reads_unopened_rows_after_caller_mutations() -> PyResult<()> {
        Python::initialize();
        Python::attach(|py| {
            let graph = graph(py)?;
            let source = 0_i64.into_pyobject(py)?;
            let mut traversal = bfs_edges_iter(&graph, source.as_any(), false, None);
            let first = traversal.__next__(py)?.expect("first edge");
            assert_eq!(first.bind(py).extract::<(i64, i64)>()?, (0, 1));
            graph.getattr("rows")?.get_item(2)?.set_item(3, py.None())?;
            let second = traversal.__next__(py)?.expect("second edge");
            assert_eq!(second.bind(py).extract::<(i64, i64)>()?, (1, 2));
            let third = traversal.__next__(py)?.expect("newly added edge");
            assert_eq!(third.bind(py).extract::<(i64, i64)>()?, (2, 3));
            assert!(traversal.__next__(py)?.is_none());
            Ok(())
        })
    }

    #[test]
    fn bfs_defers_custom_iterable_activation_until_its_layer() -> PyResult<()> {
        Python::initialize();
        Python::attach(|py| {
            let module = PyModule::from_code(
                py,
                cr#"class Children:
    def __init__(self, graph, node):
        self.graph = graph
        self.node = node
    def __iter__(self):
        self.graph.events.append(("iter", self.node))
        return iter(self.graph.rows[self.node])
class Graph:
    def __init__(self):
        self.rows = {0: {1: None}, 1: {2: None}, 2: {}}
        self.events = []
    def __len__(self):
        return len(self.rows)
    def neighbors(self, node):
        self.events.append(("neighbors", node))
        return Children(self, node)
graph = Graph()
"#,
                c"test_traversal_iterable.py",
                c"test_traversal_iterable",
            )?;
            let graph = module.getattr("graph")?;
            let source = 0_i64.into_pyobject(py)?;
            let mut traversal = bfs_edges_iter(&graph, source.as_any(), false, None);
            traversal.__next__(py)?.expect("first edge");
            assert_eq!(
                graph.getattr("events")?.extract::<Vec<(String, i64)>>()?,
                [
                    ("neighbors".to_owned(), 0),
                    ("iter".to_owned(), 0),
                    ("neighbors".to_owned(), 1),
                ]
            );
            traversal.__next__(py)?.expect("second edge");
            assert_eq!(
                graph.getattr("events")?.extract::<Vec<(String, i64)>>()?,
                [
                    ("neighbors".to_owned(), 0),
                    ("iter".to_owned(), 0),
                    ("neighbors".to_owned(), 1),
                    ("iter".to_owned(), 1),
                    ("neighbors".to_owned(), 2),
                ]
            );
            Ok(())
        })
    }

    #[test]
    fn bfs_preserves_callback_stop_iteration_as_generator_error() -> PyResult<()> {
        Python::initialize();
        Python::attach(|py| {
            let graph = graph(py)?;
            let module = PyModule::from_code(
                py,
                c"error = StopIteration('callback failed')\ndef neighbors(node):\n    raise error\n",
                c"test_traversal_error.py",
                c"test_traversal_error",
            )?;
            graph.setattr("neighbors", module.getattr("neighbors")?)?;
            let source = 0_i64.into_pyobject(py)?;
            let mut traversal = bfs_edges_iter(&graph, source.as_any(), false, None);
            let error = traversal.__next__(py).expect_err("callback StopIteration");
            assert!(error.is_instance_of::<PyRuntimeError>(py));
            let original = module.getattr("error")?;
            assert!(
                error
                    .cause(py)
                    .expect("original cause")
                    .value(py)
                    .is(&original)
            );
            assert!(error.value(py).getattr("__context__")?.is(&original));
            assert!(traversal.__next__(py)?.is_none());
            Ok(())
        })
    }

    #[test]
    fn dfs_reads_child_rows_only_after_resuming_the_forward_edge() -> PyResult<()> {
        Python::initialize();
        Python::attach(|py| {
            let graph = graph(py)?;
            let source = 0_i64.into_pyobject(py)?;
            let mut traversal = dfs_traversal_iter(&graph, Some(source.as_any()), None, "edges")?;
            let first = traversal.__next__(py)?.expect("first edge");
            assert_eq!(first.bind(py).extract::<(i64, i64)>()?, (0, 1));
            assert_eq!(graph.getattr("reads")?.extract::<Vec<i64>>()?, [0]);
            graph.getattr("rows")?.get_item(1)?.set_item(3, py.None())?;
            let second = traversal.__next__(py)?.expect("second edge");
            assert_eq!(second.bind(py).extract::<(i64, i64)>()?, (1, 2));
            let third = traversal.__next__(py)?.expect("newly added edge");
            assert_eq!(third.bind(py).extract::<(i64, i64)>()?, (1, 3));
            assert!(traversal.__next__(py)?.is_none());
            Ok(())
        })
    }

    #[test]
    fn dfs_preorder_yields_missing_source_before_its_row_lookup() -> PyResult<()> {
        Python::initialize();
        Python::attach(|py| {
            let graph = graph(py)?;
            let source = 99_i64.into_pyobject(py)?;
            let mut traversal =
                dfs_traversal_iter(&graph, Some(source.as_any()), None, "preorder")?;
            let first = traversal.__next__(py)?.expect("source event");
            assert_eq!(first.bind(py).extract::<i64>()?, 99);
            assert_eq!(graph.getattr("reads")?.len()?, 0);
            let error = traversal.__next__(py).expect_err("missing source row");
            assert!(error.is_instance_of::<pyo3::exceptions::PyKeyError>(py));
            assert!(traversal.__next__(py)?.is_none());
            Ok(())
        })
    }

    #[test]
    fn dfs_postorder_does_not_emit_depth_cutoff_nodes() -> PyResult<()> {
        Python::initialize();
        Python::attach(|py| {
            let graph = graph(py)?;
            let source = 0_i64.into_pyobject(py)?;
            let mut traversal =
                dfs_traversal_iter(&graph, Some(source.as_any()), Some(1), "postorder")?;
            let first = traversal.__next__(py)?.expect("completed source row");
            assert_eq!(first.bind(py).extract::<i64>()?, 0);
            assert_eq!(graph.getattr("reads")?.extract::<Vec<i64>>()?, [0]);
            assert!(traversal.__next__(py)?.is_none());
            Ok(())
        })
    }
}
