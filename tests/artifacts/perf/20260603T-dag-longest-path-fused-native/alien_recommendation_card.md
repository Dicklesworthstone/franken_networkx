Change: Fuse exact-DiGraph topological traversal and DAG longest-path predecessor snapshot into one safe-Rust primitive.
Hotspot evidence: Baseline cProfile for 160 calls spent 0.103s in Python topological_sort plus 0.045s in _native_in_edges_data_key under dag_longest_path; baseline FNX was 0.001064320371951908s per call.
Mapped graveyard sections: cache-aware graph traversal, fused automata/state machines, zero-copy boundary reduction, and batched native snapshot construction from the no-gaps directive.
EV score: Impact 3 * Confidence 5 / Effort 2 = 7.5.
Priority tier: A.
Adoption wedge: exact DiGraph only; subclasses, views, multigraphs, explicit topo_order, and generic error paths keep existing fallback behavior.
Budgeted mode: O(V + E) memory and time; on cycle, raise NetworkXUnfeasible with the existing topological-sort error contract.
Expected-loss model: accept only same golden digest and passing DAG parity; reject on ordering, TypeError, NaN, negative-reset, cycle, or tie-break drift.
Fallback: Python helper falls back to separate topological_sort plus _native_in_edges_data_key when _native_dag_topo_pred_data_key is absent.
