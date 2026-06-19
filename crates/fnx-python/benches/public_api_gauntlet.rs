#![forbid(unsafe_code)]

use criterion::{criterion_group, criterion_main, BenchmarkId, Criterion};
use pyo3::types::PyAnyMethods;
use pyo3::{Py, PyAny, Python};

fn init_python() {
    static START: std::sync::Once = std::sync::Once::new();
    START.call_once(Python::initialize);
}

fn bench_py_callable(c: &mut Criterion, workload: &str, engine: &str, callable: Py<PyAny>) {
    c.bench_with_input(
        BenchmarkId::new(workload, engine),
        &callable,
        |b, callable| {
            b.iter(|| {
                Python::attach(|py| {
                    callable
                        .bind(py)
                        .call0()
                        .and_then(|value| value.extract::<f64>())
                        .expect("Python benchmark callable should return float")
                })
            });
        },
    );
}

fn bench_public_api_gauntlet(c: &mut Criterion) {
    init_python();
    Python::attach(|py| {
        let helper = py
            .import("public_api_gauntlet")
            .expect("set PYTHONPATH=crates/fnx-python/benches:python:legacy_networkx_code");
        for (workload, engine, callable_name) in [
            (
                "flow_hierarchy_weighted_cyclic_dag",
                "fnx",
                "fnx_flow_hierarchy_weighted_cyclic_dag",
            ),
            (
                "flow_hierarchy_weighted_cyclic_dag",
                "networkx",
                "networkx_flow_hierarchy_weighted_cyclic_dag",
            ),
            (
                "within_inter_cluster_explicit_community",
                "fnx",
                "fnx_within_inter_cluster_explicit_community",
            ),
            (
                "within_inter_cluster_explicit_community",
                "networkx",
                "networkx_within_inter_cluster_explicit_community",
            ),
            (
                "non_edges_sparse_undirected",
                "fnx",
                "fnx_non_edges_sparse_undirected",
            ),
            (
                "non_edges_sparse_undirected",
                "networkx",
                "networkx_non_edges_sparse_undirected",
            ),
            (
                "raw_adamic_adar_repeated_overlap",
                "fnx",
                "fnx_raw_adamic_adar_repeated_overlap",
            ),
            (
                "raw_adamic_adar_repeated_overlap",
                "networkx",
                "networkx_adamic_adar_repeated_overlap",
            ),
            (
                "raw_resource_allocation_repeated_overlap",
                "fnx",
                "fnx_raw_resource_allocation_repeated_overlap",
            ),
            (
                "raw_resource_allocation_repeated_overlap",
                "networkx",
                "networkx_resource_allocation_repeated_overlap",
            ),
        ] {
            let callable = helper
                .getattr(callable_name)
                .expect("benchmark helper should expose callable")
                .unbind();
            bench_py_callable(c, workload, engine, callable);
        }
    });
}

criterion_group!(benches, bench_public_api_gauntlet);
criterion_main!(benches);
