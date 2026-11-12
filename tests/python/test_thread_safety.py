"""Thread-safety tests for GIL release in algorithm bindings.

Verifies that py.allow_threads() correctly releases and re-acquires the GIL,
and that concurrent Python threads can safely call FrankenNetworkX operations.

Run through DSR's guarded, targeted Python test recipe.
"""

import concurrent.futures
import hashlib
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest

try:
    import franken_networkx as fnx
except ImportError:
    pytest.skip("franken_networkx not installed", allow_module_level=True)


# ---------------------------------------------------------------------------
# Shared fixtures — read-only graphs built once per module
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def large_path():
    """Path graph with 200 nodes."""
    g = fnx.Graph()
    for i in range(200):
        g.add_node(i)
    for i in range(199):
        g.add_edge(i, i + 1, weight=1.0)
    return g


@pytest.fixture(scope="module")
def large_complete():
    """Complete graph K_30."""
    g = fnx.Graph()
    for i in range(30):
        for j in range(i + 1, 30):
            g.add_edge(i, j, weight=1.0)
    return g


@pytest.fixture(scope="module")
def connected_graph():
    """A connected graph with some structure."""
    g = fnx.Graph()
    # Ring of 50 nodes
    for i in range(50):
        g.add_edge(i, (i + 1) % 50, weight=1.0)
    # Cross edges for richer structure
    for i in range(0, 50, 5):
        g.add_edge(i, (i + 25) % 50, weight=2.0)
    return g


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NUM_WORKERS = 4
ITERATIONS = 100


# Fresh interpreters are essential: an already initialized pool hides first-use
# failure. These are real OS limits, not a mocked ThreadPoolBuildError.
_RESOURCE_PROBE = r'''
import concurrent.futures, hashlib, importlib.util, io, json, os, platform, resource, sys, threading, time
from pathlib import Path

limit = 2 * 1024**3
resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
# The isolated interpreter must exercise the parent's selected DSR candidate,
# not whichever editable extension happens to be installed in this venv.
library = Path(sys.argv[5]).resolve()
expected_sha = sys.argv[6]
assert hashlib.sha256(library.read_bytes()).hexdigest() == expected_sha
sys.path.insert(0, sys.argv[7])
spec = importlib.util.spec_from_file_location('franken_networkx._fnx', library)
selected_native = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = selected_native
spec.loader.exec_module(selected_native)
import franken_networkx as fnx
import franken_networkx._fnx as native
import networkx as nx
assert Path(native.__file__).resolve() == library

if sys.argv[4] == "nproc":
    resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))
mode, concurrent_first, graph_kind = sys.argv[1], sys.argv[2] == "concurrent", sys.argv[3]
identity = dict(host=platform.node(), python=sys.executable, nx_version=nx.__version__,
                so_sha256=hashlib.sha256(Path(native.__file__).read_bytes()).hexdigest(),
                address_space_limit=limit, cpu_count=os.cpu_count(),
                affinity_count=len(os.sched_getaffinity(0)),
                requested_threads=os.environ.get("RAYON_NUM_THREADS", "default"),
                graph_kind=graph_kind, uid=os.getuid(),
                process_limit=resource.getrlimit(resource.RLIMIT_NPROC))
graph = fnx.karate_club_graph()
oracle = nx.karate_club_graph()
expected_diameter = nx.diameter(oracle)
before = list(graph.edges())
pool_graph = fnx.cycle_graph(520, create_using=getattr(fnx, graph_kind))
pool_oracle = nx.cycle_graph(520, create_using=getattr(nx, graph_kind))
pool_diameter = nx.diameter(pool_oracle)
pool_closeness = nx.closeness_centrality(pool_oracle)

def first_call(graph=graph):
    with fnx.compatibility_mode(mode):
        assert fnx.get_compatibility_mode() == mode
        result = fnx.diameter(graph)
        assert fnx.diameter(pool_graph) == pool_diameter
        assert fnx.closeness_centrality(pool_graph) == pool_closeness
        assert fnx.get_compatibility_mode() == mode
        assert result == expected_diameter
        return result

if concurrent_first:
    barrier = threading.Barrier(3)
    def simultaneous():
        barrier.wait(timeout=10)
        return first_call()
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as workers:
        assert list(workers.map(lambda _: simultaneous(), range(3))) == [expected_diameter] * 3
else:
    first_call()
first_call()
assert list(graph.edges()) == before
print(json.dumps(dict(case_id="karate-default-first-use", n=len(graph), m=graph.number_of_edges(),
                      input_type="Graph", result=expected_diameter, mode=mode,
                      concurrent=concurrent_first, **identity)), flush=True)

# Cross the production parallel thresholds, with independently constructed
# oracle graphs. Integer-valued distances/clustering are compared exactly;
# floats retain their original source-ordered arithmetic (no widened epsilon).
graph = fnx.cycle_graph(520, create_using=getattr(fnx, graph_kind))
oracle = nx.cycle_graph(520, create_using=getattr(nx, graph_kind))
if graph.is_multigraph():
    # Exercise real parallel edges, not a multigraph with one key per pair.
    graph.add_edges_from((u, v, "parallel", {"weight": 2.0}) for u, v in list(graph.edges()))
    oracle.add_edges_from((u, v, "parallel", {"weight": 2.0}) for u, v in list(oracle.edges()))
operations = [
    ("eccentricity", lambda api, g: api.eccentricity(g)),
    ("diameter", lambda api, g: api.diameter(g)),
    ("radius", lambda api, g: api.radius(g)),
    ("center", lambda api, g: api.center(g)),
    ("periphery", lambda api, g: api.periphery(g)),
    ("closeness", lambda api, g: api.closeness_centrality(g)),
    ("harmonic", lambda api, g: api.harmonic_centrality(g)),
    ("betweenness", lambda api, g: api.betweenness_centrality(g)),
    ("edge_betweenness", lambda api, g: api.edge_betweenness_centrality(g)),
    ("clustering", lambda api, g: api.clustering(g)),
    ("average_clustering", lambda api, g: api.average_clustering(g)),
    ("triangles", lambda api, g: api.triangles(g)),
    ("transitivity", lambda api, g: api.transitivity(g)),
    ("aspl", lambda api, g: api.average_shortest_path_length(g)),
    ("all_pairs_bfs", lambda api, g: dict(api.all_pairs_shortest_path_length(g))),
    ("all_pairs_dijkstra", lambda api, g: dict(api.all_pairs_dijkstra_path_length(g))),
    ("sampled_betweenness", lambda api, g: api.betweenness_centrality(g, k=2, seed=17)),
    ("load", lambda api, g: api.load_centrality(g)),
    ("weighted_betweenness", lambda api, g: api.betweenness_centrality(g, weight="weight")),
    ("weighted_edge_betweenness", lambda api, g: api.edge_betweenness_centrality(g, weight="weight")),
    ("weighted_load", lambda api, g: api.load_centrality(g, weight="weight")),
    ("weighted_percolation", lambda api, g: api.percolation_centrality(g, states={i: 1.0 for i in g}, weight="weight")),
]
for name, operation in operations:
    if graph_kind == "DiGraph" and name == "triangles":
        # This route is unsupported by the oracle, not a capacity refusal or
        # a successful algorithm result. Keep the ordinary exception contract.
        for api, current in ((nx, oracle), (fnx, graph)):
            try:
                operation(api, current)
            except api.NetworkXNotImplemented:
                pass
            else:
                raise AssertionError("directed triangles was accepted")
        print(json.dumps(dict(case_id=name, n=len(graph), m=graph.number_of_edges(),
                              expected_exception="NetworkXNotImplemented",
                              mode=mode, **identity)), flush=True)
        continue
    start = time.monotonic()
    try:
        expected = operation(nx, oracle)
    except nx.NetworkXNotImplemented as expected_error:
        # Some clustering routes deliberately exclude multigraphs. Exercise
        # their real public refusal without counting it as a positive result.
        with fnx.compatibility_mode(mode):
            try:
                operation(fnx, graph)
            except fnx.NetworkXNotImplemented as actual_error:
                assert str(actual_error) == str(expected_error), (name, actual_error, expected_error)
            else:
                raise AssertionError((name, "unsupported graph was accepted"))
            assert fnx.get_compatibility_mode() == mode
        print(json.dumps(dict(case_id=name, n=len(graph), m=graph.number_of_edges(),
                              expected_exception="NetworkXNotImplemented",
                              mode=mode, **identity)), flush=True)
        continue
    nx_seconds = time.monotonic() - start
    start = time.monotonic()
    with fnx.compatibility_mode(mode):
        actual = operation(fnx, graph)
        assert fnx.get_compatibility_mode() == mode
    assert actual == expected, (name, actual, expected)
    print(json.dumps(dict(case_id=name, n=len(graph), m=graph.number_of_edges(),
                          fnx_seconds=time.monotonic()-start, nx_seconds=nx_seconds,
                          mode=mode, equal=True, **identity)), flush=True)

# Parser shares the worker pool; retain line/node/edge order on fallback too.
content = "".join(f"{i} {i+1}\n" for i in range(12000))
with fnx.compatibility_mode(mode):
    parsed = fnx.read_edgelist(io.BytesIO(content.encode()), data=False)
reference = nx.read_edgelist(io.BytesIO(content.encode()), data=False)
assert list(parsed.nodes()) == list(reference.nodes())
assert list(parsed.edges()) == list(reference.edges())
print(json.dumps(dict(case_id="ordered-edgelist", n=len(parsed), m=parsed.number_of_edges(),
                      input_type="Graph", mode=mode, equal=True, **identity)), flush=True)

# Original user-facing tutorial, not only isolated distance calls. PageRank
# adds a 1e-12 absolute convergence check here (stricter than the parity
# module's default); all pre-existing exact comparisons above remain exact.
with fnx.compatibility_mode(mode):
    tutorial = fnx.karate_club_graph()
    reference = nx.karate_club_graph()
    actual_rank = fnx.pagerank(tutorial)
    expected_rank = nx.pagerank(reference)
    assert list(actual_rank) == list(expected_rank)
    assert all(abs(actual_rank[node] - expected_rank[node]) <= 1e-12 for node in expected_rank)
    assert {frozenset(group) for group in fnx.community.louvain_communities(tutorial, seed=17)} == {
        frozenset(group) for group in nx.community.louvain_communities(reference, seed=17)
    }
    assert fnx.diameter(tutorial) == nx.diameter(reference)
    output = io.BytesIO()
    fnx.write_graphml(tutorial, output)
    restored = fnx.read_graphml(io.BytesIO(output.getvalue()), node_type=int)
    assert list(restored) == list(reference)
    assert dict(restored.nodes(data=True)) == dict(reference.nodes(data=True))
    assert fnx.to_dict_of_dicts(restored) == nx.to_dict_of_dicts(reference)
    assert fnx.get_compatibility_mode() == mode
print(json.dumps(dict(case_id="karate-pagerank-louvain-diameter-graphml", n=len(tutorial),
                      m=tutorial.number_of_edges(), equal=True, mode=mode, **identity)), flush=True)

# An algorithm error must still propagate, and must not poison the next call.
broken = fnx.Graph([(0, 1), (2, 3)])
try:
    fnx.diameter(broken)
except fnx.NetworkXError:
    pass
else:
    raise AssertionError("disconnected graph was accepted")
assert first_call() == expected_diameter
names = [p.read_text().strip() for p in Path("/proc/self/task").glob("*/comm")]
effective = sum(name.startswith("fnx-rayon-") for name in names)
print(json.dumps(dict(case_id="usable-after-capacity-and-algorithm-error",
                      effective_worker_threads=effective, peak_rss_kb=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                      mode=mode, task_names=names, **identity)), flush=True)
assert hashlib.sha256(library.read_bytes()).hexdigest() == expected_sha
'''


_STREAMING_RESOURCE_PROBE = r'''
import hashlib, importlib.util, json, os, platform, resource, sys
from pathlib import Path

limit = 2 * 1024**3
resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
library = Path(sys.argv[2]).resolve()
assert hashlib.sha256(library.read_bytes()).hexdigest() == sys.argv[3]
sys.path.insert(0, sys.argv[4])
spec = importlib.util.spec_from_file_location('franken_networkx._fnx', library)
native = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = native
spec.loader.exec_module(native)
import franken_networkx as fnx
import networkx as nx

name = sys.argv[1]
n = 1200
graph = fnx.path_graph(n)
oracle = nx.path_graph(n)
identity = dict(name=name, host=platform.node(), python=sys.executable,
                nx_version=nx.__version__, so_sha256=sys.argv[3],
                n=n, m=graph.number_of_edges(), address_space_limit=limit,
                cpu_count=os.cpu_count(), affinity_count=len(os.sched_getaffinity(0)),
                requested_threads=os.environ.get('RAYON_NUM_THREADS', 'default'))
print(json.dumps(dict(phase='before-first-row', **identity)), flush=True)
rows = getattr(fnx, name)(graph)
expected_rows = getattr(nx, name)(oracle)
actual_source, actual = next(rows)
expected_source, expected = next(expected_rows)
assert actual_source == expected_source == 0
if name == 'all_pairs_dijkstra':
    assert [(k, v, type(v)) for k, v in actual[0].items()] == [
        (k, v, type(v)) for k, v in expected[0].items()]
    actual, expected = actual[1], expected[1]
assert list(actual.items()) == list(expected.items())
assert len(actual) == n
assert actual[n - 1] == list(range(n))
rows.close()
expected_rows.close()
# Partial consumption and close must not poison the graph or later calls.
graph.add_edge(0, n - 1)
oracle.add_edge(0, n - 1)
assert fnx.single_source_shortest_path_length(graph, 0) == (
    nx.single_source_shortest_path_length(oracle, 0))
print(json.dumps(dict(phase='first-row-and-reuse-passed', targets=len(actual),
                     path_elements=sum(map(len, actual.values())),
                     peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                     **identity)), flush=True)
'''


_MATRIX_RESOURCE_PROBE = r'''
import concurrent.futures, hashlib, importlib.util, json, os, platform, resource, sys, threading
from pathlib import Path

limit = 2 * 1024**3
resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
library = Path(sys.argv[4]).resolve()
assert hashlib.sha256(library.read_bytes()).hexdigest() == sys.argv[5]
sys.path.insert(0, sys.argv[6])
spec = importlib.util.spec_from_file_location('franken_networkx._fnx', library)
native = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = native
spec.loader.exec_module(native)
import franken_networkx as fnx
import networkx as nx
import numpy as np

mode, graph_kind, profile = sys.argv[1:4]
if profile == 'nproc':
    resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))
identity = dict(host=platform.node(), python=sys.executable, nx_version=nx.__version__,
                so_sha256=sys.argv[5], address_space_limit=limit,
                cpu_count=os.cpu_count(), affinity_count=len(os.sched_getaffinity(0)),
                requested_threads=os.environ.get('RAYON_NUM_THREADS', 'default'),
                graph_kind=graph_kind, mode=mode, uid=os.getuid(),
                process_limit=resource.getrlimit(resource.RLIMIT_NPROC))

if profile in ('allocation', 'packing'):
    graph = fnx.empty_graph(1024, create_using=getattr(fnx, graph_kind))
    # Source repetition is supported. The input is only a few MiB, whereas
    # allocation exceeds the cap by itself; packing lets the distance vector
    # fit but leaves insufficient room for the immutable Python backing.
    sources = [0] * (600000 if profile == 'allocation' else 300000)
    print(json.dumps(dict(phase='before-allocation', rows=len(sources), columns=len(graph),
                         output_bytes=len(sources) * len(graph) * 4, **identity)), flush=True)
    with fnx.compatibility_mode(mode):
        try:
            fnx.shortest_path_length_matrix(graph, sources=sources, cutoff=0)
        except MemoryError as error:
            refusal = str(error)
        else:
            raise AssertionError('over-capacity matrix was accepted')
        assert fnx.get_compatibility_mode() == mode
        matrix = fnx.shortest_path_length_matrix(graph, sources=[0], cutoff=0)
    assert matrix.shape == (1, 1024)
    assert matrix[0, 0] == 0 and np.all(matrix[0, 1:] == -1)
    print(json.dumps(dict(phase='ordinary-refusal-and-reuse-passed',
                         boundary=profile, refusal=refusal, **identity)), flush=True)
else:
    n = 520
    graph = fnx.cycle_graph(n, create_using=getattr(fnx, graph_kind))
    oracle = nx.cycle_graph(n, create_using=getattr(nx, graph_kind))
    if graph.is_multigraph():
        graph.add_edge(0, 1, key='parallel')
        oracle.add_edge(0, 1, key='parallel')
    # Both directed and undirected CSR routes exceed 2**17 edge/source scans.
    # Reverse insertion order and include a duplicate; do not sort the result.
    sources = list(reversed(range(0, n, 2))) + [0]
    nodes = list(oracle)
    positions = {node: column for column, node in enumerate(nodes)}
    expected = np.full((len(sources), n), -1, dtype=np.int32)
    for row, source in enumerate(sources):
        for target, distance in nx.single_source_shortest_path_length(oracle, source).items():
            expected[row, positions[target]] = distance
    before = list(graph.edges())

    def calculate():
        with fnx.compatibility_mode(mode):
            assert fnx.get_compatibility_mode() == mode
            actual = fnx.shortest_path_length_matrix(graph, sources=sources)
            assert fnx.get_compatibility_mode() == mode
        assert actual.dtype == np.int32 and actual.shape == expected.shape
        assert np.array_equal(actual, expected)
        assert not actual.flags.writeable
        try:
            actual.setflags(write=True)
        except ValueError:
            pass
        else:
            raise AssertionError('immutable backing became writable')
        return True

    if mode == 'hardened' and profile != 'nproc':
        barrier = threading.Barrier(3)
        def simultaneous():
            barrier.wait(timeout=10)
            return calculate()
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as workers:
            assert list(workers.map(lambda _: simultaneous(), range(3))) == [True] * 3
    else:
        calculate()
    calculate()
    with fnx.compatibility_mode(mode):
        for cutoff in (0, 2):
            actual = fnx.shortest_path_length_matrix(graph, sources=sources, cutoff=cutoff)
            assert np.array_equal(actual, np.where(expected <= cutoff, expected, -1))
        assert fnx.shortest_path_length_matrix(graph, sources=[]).shape == (0, n)
        try:
            fnx.shortest_path_length_matrix(graph, sources=[n])
        except fnx.NodeNotFound as error:
            assert str(error) == f'Source {n} is not in G'
        else:
            raise AssertionError('missing source was accepted')
        assert fnx.single_source_shortest_path_length(graph, 0) == (
            nx.single_source_shortest_path_length(oracle, 0))
        assert fnx.get_compatibility_mode() == mode
    assert list(graph.edges()) == before
    names = [p.read_text().strip() for p in Path('/proc/self/task').glob('*/comm')]
    effective = sum(name.startswith('fnx-rayon-') for name in names)
    print(json.dumps(dict(phase='subset-first-use-and-reuse-passed', n=n,
                         m=graph.number_of_edges(), rows=len(sources),
                         effective_worker_threads=effective,
                         peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                         **identity)), flush=True)
assert hashlib.sha256(library.read_bytes()).hexdigest() == sys.argv[5]
'''


@pytest.mark.skipif(sys.platform != "linux", reason="real Linux address-space/task probes")
@pytest.mark.parametrize("threads", [None, "1", "2", "4096", "2-nproc"])
@pytest.mark.parametrize("mode", ["strict", "hardened"])
@pytest.mark.parametrize("graph_kind", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_packed_matrix_subset_under_real_capacity_limit(threads, mode, graph_kind, tmp_path):
    if threads == "2-nproc" and os.getuid() == 0:
        pytest.skip("Linux does not enforce RLIMIT_NPROC for uid 0")
    env = os.environ.copy()
    env.pop("RAYON_NUM_THREADS", None)
    env.pop("RAYON_RS_NUM_CPUS", None)
    env.update(OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1")
    if threads is not None:
        env["RAYON_NUM_THREADS"] = "2" if threads == "2-nproc" else threads
    library = Path(fnx._fnx.__file__).resolve()
    result = subprocess.run(
        [sys.executable, "-I", "-c", _MATRIX_RESOURCE_PROBE, mode, graph_kind,
         "nproc" if threads == "2-nproc" else "normal", str(library),
         hashlib.sha256(library.read_bytes()).hexdigest(),
         str(Path(fnx.__file__).resolve().parent.parent)],
        env=env, capture_output=True, text=True, timeout=90, check=False,
    )
    (tmp_path / "probe.stdout.jsonl").write_text(result.stdout)
    (tmp_path / "probe.stderr.log").write_text(result.stderr)
    print(result.stdout, end="")
    print(result.stderr, end="", file=sys.stderr)
    assert result.returncode == 0, result.stderr
    records = [json.loads(line) for line in result.stdout.splitlines()]
    assert len(records) == 1
    assert records[0]["phase"] == "subset-first-use-and-reuse-passed"
    assert records[0]["rows"] == 261
    if threads in ("1", "2"):
        assert records[0]["effective_worker_threads"] == int(threads)
    if threads in ("4096", "2-nproc"):
        assert "using serial kernels" in result.stderr
        assert records[0]["effective_worker_threads"] == 0
    if threads == "2-nproc":
        assert "os error 11" in result.stderr


@pytest.mark.skipif(sys.platform != "linux", reason="real Linux address-space probe")
@pytest.mark.parametrize("mode", ["strict", "hardened"])
@pytest.mark.parametrize("graph_kind", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
@pytest.mark.parametrize("boundary", ["allocation", "packing"])
def test_packed_matrix_allocation_refusal_keeps_graph_usable(mode, graph_kind, boundary, tmp_path):
    env = os.environ.copy()
    env.update(OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", RAYON_NUM_THREADS="2")
    library = Path(fnx._fnx.__file__).resolve()
    result = subprocess.run(
        [sys.executable, "-I", "-c", _MATRIX_RESOURCE_PROBE, mode, graph_kind,
         boundary, str(library), hashlib.sha256(library.read_bytes()).hexdigest(),
         str(Path(fnx.__file__).resolve().parent.parent)],
        env=env, capture_output=True, text=True, timeout=90, check=False,
    )
    (tmp_path / "probe.stdout.jsonl").write_text(result.stdout)
    (tmp_path / "probe.stderr.log").write_text(result.stderr)
    print(result.stdout, end="")
    print(result.stderr, end="", file=sys.stderr)
    assert result.returncode == 0, result.stderr
    records = [json.loads(line) for line in result.stdout.splitlines()]
    assert len(records) == 2
    assert records[-1]["phase"] == "ordinary-refusal-and-reuse-passed"


@pytest.mark.skipif(sys.platform != "linux", reason="real Linux address-space probe")
@pytest.mark.parametrize("name", ["all_pairs_shortest_path", "all_pairs_dijkstra",
                                 "all_pairs_dijkstra_path"])
def test_native_stream_first_path_row_under_real_memory_limit(name, tmp_path):
    env = os.environ.copy()
    env.update(OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", RAYON_NUM_THREADS="2")
    library = Path(fnx._fnx.__file__).resolve()
    result = subprocess.run(
        [sys.executable, "-I", "-c", _STREAMING_RESOURCE_PROBE, name,
         str(library), hashlib.sha256(library.read_bytes()).hexdigest(),
         str(Path(fnx.__file__).resolve().parent.parent)],
        env=env, capture_output=True, text=True, timeout=90, check=False,
    )
    (tmp_path / "probe.stdout.jsonl").write_text(result.stdout)
    (tmp_path / "probe.stderr.log").write_text(result.stderr)
    print(result.stdout, end="")
    print(result.stderr, end="", file=sys.stderr)
    assert result.returncode == 0, result.stderr
    records = [json.loads(line) for line in result.stdout.splitlines()]
    assert len(records) == 2
    assert records[-1]["phase"] == "first-row-and-reuse-passed"
    assert records[-1]["targets"] == 1200
    assert records[-1]["path_elements"] == 1200 * 1201 // 2


@pytest.mark.skipif(sys.platform != "linux", reason="real Linux address-space/task probes")
@pytest.mark.parametrize("threads", [None, "1", "2", "4096", "2-nproc"])
@pytest.mark.parametrize("mode", ["strict", "hardened"])
@pytest.mark.parametrize("graph_kind", ["Graph", "DiGraph", "MultiGraph", "MultiDiGraph"])
def test_parallel_first_use_under_real_capacity_limit(threads, mode, graph_kind, tmp_path):
    """Capacity failure must yield correct serial results, not PanicException."""
    if threads == "2-nproc" and os.getuid() == 0:
        pytest.skip("Linux does not enforce RLIMIT_NPROC for uid 0")
    env = os.environ.copy()
    env.pop("RAYON_NUM_THREADS", None)
    env.pop("RAYON_RS_NUM_CPUS", None)
    env.update(OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1")
    if threads is not None:
        env["RAYON_NUM_THREADS"] = "2" if threads == "2-nproc" else threads
    result = subprocess.run(
        [sys.executable, "-I", "-c", _RESOURCE_PROBE, mode,
         "concurrent" if mode == "hardened" and threads != "2-nproc" else "serial",
         graph_kind, "nproc" if threads == "2-nproc" else "normal",
         str(Path(fnx._fnx.__file__).resolve()),
         hashlib.sha256(Path(fnx._fnx.__file__).read_bytes()).hexdigest(),
         str(Path(fnx.__file__).resolve().parent.parent)],
        env=env, capture_output=True, text=True, timeout=90, check=False,
    )
    (tmp_path / "probe.stdout.jsonl").write_text(result.stdout)
    (tmp_path / "probe.stderr.log").write_text(result.stderr)
    print(result.stdout, end="")
    print(result.stderr, end="", file=sys.stderr)
    assert result.returncode == 0, result.stderr
    assert "PanicException" not in result.stderr
    records = [json.loads(line) for line in result.stdout.splitlines()]
    assert len(records) == 26  # Original 21, four public aliases, full tutorial.
    assert records[-1]["case_id"] == "usable-after-capacity-and-algorithm-error"
    if threads in ("1", "2"):
        assert records[-1]["effective_worker_threads"] == int(threads)
    if threads == "4096":
        assert "using serial kernels" in result.stderr
        assert records[-1]["effective_worker_threads"] == 0
    if threads == "2-nproc":
        assert "os error 11" in result.stderr
        assert "using serial kernels" in result.stderr
        assert records[-1]["effective_worker_threads"] == 0
    observation = {
        "case_id": "capacity-observation", "mode": mode, "graph_kind": graph_kind,
        "returncode": result.returncode, "first_use": records[0], "recovery": records[-1],
        "refusal_reason": result.stderr if "using serial kernels" in result.stderr else None,
        "stdout_sha256": hashlib.sha256(result.stdout.encode()).hexdigest(),
        "stderr_sha256": hashlib.sha256(result.stderr.encode()).hexdigest(),
    }
    (tmp_path / "capacity.receipt.json").write_text(json.dumps(observation, sort_keys=True))
    print(json.dumps(observation, sort_keys=True), flush=True)


# ---------------------------------------------------------------------------
# Concurrent read-only algorithm tests
# ---------------------------------------------------------------------------

class TestConcurrentShortestPath:
    """Multiple threads computing shortest paths on a shared graph."""

    def test_concurrent_shortest_path(self, large_path):
        """Concurrent shortest_path calls should all return correct results."""
        barrier = threading.Barrier(NUM_WORKERS)
        results = []
        errors = []

        def worker():
            try:
                barrier.wait(timeout=5)
                for _ in range(ITERATIONS):
                    path = fnx.shortest_path(large_path, 0, 199, weight="weight")
                    assert len(path) == 200
                    assert path[0] == 0
                    assert path[-1] == 199
                results.append(True)
            except Exception as e:
                errors.append(e)

        with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_WORKERS) as pool:
            futures = [pool.submit(worker) for _ in range(NUM_WORKERS)]
            concurrent.futures.wait(futures)

        assert not errors, f"Thread errors: {errors}"
        assert len(results) == NUM_WORKERS

    def test_concurrent_has_path(self, large_path):
        """Concurrent has_path calls."""
        barrier = threading.Barrier(NUM_WORKERS)
        errors = []

        def worker():
            try:
                barrier.wait(timeout=5)
                for _ in range(ITERATIONS):
                    assert fnx.has_path(large_path, 0, 199)
                    assert fnx.has_path(large_path, 50, 100)
            except Exception as e:
                errors.append(e)

        with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_WORKERS) as pool:
            futures = [pool.submit(worker) for _ in range(NUM_WORKERS)]
            concurrent.futures.wait(futures)

        assert not errors, f"Thread errors: {errors}"


class TestConcurrentCentrality:
    """Multiple threads computing centrality metrics."""

    def test_concurrent_betweenness(self, connected_graph):
        """Concurrent betweenness_centrality calls."""
        barrier = threading.Barrier(NUM_WORKERS)
        results = []
        errors = []

        def worker():
            try:
                barrier.wait(timeout=5)
                for _ in range(ITERATIONS // 10):  # Betweenness is expensive
                    bc = fnx.betweenness_centrality(connected_graph)
                    assert len(bc) == 50
                    assert all(0 <= v <= 1 for v in bc.values())
                results.append(True)
            except Exception as e:
                errors.append(e)

        with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_WORKERS) as pool:
            futures = [pool.submit(worker) for _ in range(NUM_WORKERS)]
            concurrent.futures.wait(futures)

        assert not errors, f"Thread errors: {errors}"
        assert len(results) == NUM_WORKERS

    def test_concurrent_pagerank(self, connected_graph):
        """Concurrent pagerank calls."""
        barrier = threading.Barrier(NUM_WORKERS)
        errors = []

        def worker():
            try:
                barrier.wait(timeout=5)
                for _ in range(ITERATIONS // 5):
                    pr = fnx.pagerank(connected_graph)
                    assert len(pr) == 50
                    total = sum(pr.values())
                    assert abs(total - 1.0) < 0.01
            except Exception as e:
                errors.append(e)

        with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_WORKERS) as pool:
            futures = [pool.submit(worker) for _ in range(NUM_WORKERS)]
            concurrent.futures.wait(futures)

        assert not errors, f"Thread errors: {errors}"

    def test_concurrent_degree_centrality(self, connected_graph):
        """Concurrent degree_centrality calls."""
        barrier = threading.Barrier(NUM_WORKERS)
        errors = []

        def worker():
            try:
                barrier.wait(timeout=5)
                for _ in range(ITERATIONS):
                    dc = fnx.degree_centrality(connected_graph)
                    assert len(dc) == 50
            except Exception as e:
                errors.append(e)

        with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_WORKERS) as pool:
            futures = [pool.submit(worker) for _ in range(NUM_WORKERS)]
            concurrent.futures.wait(futures)

        assert not errors, f"Thread errors: {errors}"


class TestConcurrentClustering:
    """Concurrent clustering computations."""

    def test_concurrent_clustering(self, connected_graph):
        """Concurrent clustering coefficient calls."""
        barrier = threading.Barrier(NUM_WORKERS)
        errors = []

        def worker():
            try:
                barrier.wait(timeout=5)
                for _ in range(ITERATIONS // 5):
                    cc = fnx.clustering(connected_graph)
                    assert len(cc) == 50
            except Exception as e:
                errors.append(e)

        with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_WORKERS) as pool:
            futures = [pool.submit(worker) for _ in range(NUM_WORKERS)]
            concurrent.futures.wait(futures)

        assert not errors, f"Thread errors: {errors}"

    def test_concurrent_transitivity(self, connected_graph):
        """Concurrent transitivity calls."""
        barrier = threading.Barrier(NUM_WORKERS)
        errors = []

        def worker():
            try:
                barrier.wait(timeout=5)
                for _ in range(ITERATIONS):
                    t = fnx.transitivity(connected_graph)
                    assert 0 <= t <= 1
            except Exception as e:
                errors.append(e)

        with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_WORKERS) as pool:
            futures = [pool.submit(worker) for _ in range(NUM_WORKERS)]
            concurrent.futures.wait(futures)

        assert not errors, f"Thread errors: {errors}"


class TestConcurrentConnectivity:
    """Concurrent connectivity checks."""

    def test_concurrent_is_connected(self, connected_graph):
        """Concurrent is_connected calls."""
        barrier = threading.Barrier(NUM_WORKERS)
        errors = []

        def worker():
            try:
                barrier.wait(timeout=5)
                for _ in range(ITERATIONS):
                    assert fnx.is_connected(connected_graph)
            except Exception as e:
                errors.append(e)

        with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_WORKERS) as pool:
            futures = [pool.submit(worker) for _ in range(NUM_WORKERS)]
            concurrent.futures.wait(futures)

        assert not errors, f"Thread errors: {errors}"

    def test_concurrent_connected_components(self, connected_graph):
        """Concurrent connected_components calls."""
        barrier = threading.Barrier(NUM_WORKERS)
        errors = []

        def worker():
            try:
                barrier.wait(timeout=5)
                for _ in range(ITERATIONS):
                    comps = list(fnx.connected_components(connected_graph))
                    assert len(comps) == 1
                    assert len(comps[0]) == 50
            except Exception as e:
                errors.append(e)

        with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_WORKERS) as pool:
            futures = [pool.submit(worker) for _ in range(NUM_WORKERS)]
            concurrent.futures.wait(futures)

        assert not errors, f"Thread errors: {errors}"


class TestConcurrentMixedAlgorithms:
    """Different algorithms running simultaneously."""

    def test_mixed_algorithms_concurrent(self, connected_graph):
        """Different algorithm calls interleaved across threads."""
        barrier = threading.Barrier(NUM_WORKERS)
        errors = []

        def worker_shortest_path():
            try:
                barrier.wait(timeout=5)
                for _ in range(ITERATIONS):
                    fnx.shortest_path(connected_graph, 0, 25, weight="weight")
            except Exception as e:
                errors.append(("shortest_path", e))

        def worker_centrality():
            try:
                barrier.wait(timeout=5)
                for _ in range(ITERATIONS // 5):
                    fnx.betweenness_centrality(connected_graph)
            except Exception as e:
                errors.append(("centrality", e))

        def worker_clustering():
            try:
                barrier.wait(timeout=5)
                for _ in range(ITERATIONS // 5):
                    fnx.clustering(connected_graph)
            except Exception as e:
                errors.append(("clustering", e))

        def worker_connectivity():
            try:
                barrier.wait(timeout=5)
                for _ in range(ITERATIONS):
                    fnx.is_connected(connected_graph)
                    fnx.density(connected_graph)
            except Exception as e:
                errors.append(("connectivity", e))

        with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_WORKERS) as pool:
            futures = [
                pool.submit(worker_shortest_path),
                pool.submit(worker_centrality),
                pool.submit(worker_clustering),
                pool.submit(worker_connectivity),
            ]
            concurrent.futures.wait(futures)

        assert not errors, f"Thread errors: {errors}"

    def test_concurrent_distance_measures(self, connected_graph):
        """Concurrent distance measure computations."""
        barrier = threading.Barrier(NUM_WORKERS)
        errors = []

        def worker():
            try:
                barrier.wait(timeout=5)
                for _ in range(ITERATIONS // 5):
                    fnx.eccentricity(connected_graph)
                    fnx.diameter(connected_graph)
                    fnx.radius(connected_graph)
            except Exception as e:
                errors.append(e)

        with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_WORKERS) as pool:
            futures = [pool.submit(worker) for _ in range(NUM_WORKERS)]
            concurrent.futures.wait(futures)

        assert not errors, f"Thread errors: {errors}"


class TestConcurrentGraphCreation:
    """Concurrent graph creation (no shared mutation)."""

    def test_concurrent_independent_graph_creation(self):
        """Each thread creates and operates on its own graph."""
        barrier = threading.Barrier(NUM_WORKERS)
        errors = []

        def worker(thread_id):
            try:
                barrier.wait(timeout=5)
                for _ in range(ITERATIONS // 2):
                    g = fnx.Graph()
                    for i in range(20):
                        g.add_edge(i, (i + 1) % 20, weight=1.0)
                    assert fnx.is_connected(g)
                    path = fnx.shortest_path(g, 0, 10, weight="weight")
                    assert len(path) > 0
                    bc = fnx.betweenness_centrality(g)
                    assert len(bc) == 20
            except Exception as e:
                errors.append((thread_id, e))

        with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_WORKERS) as pool:
            futures = [pool.submit(worker, i) for i in range(NUM_WORKERS)]
            concurrent.futures.wait(futures)

        assert not errors, f"Thread errors: {errors}"


class TestConcurrentResultConsistency:
    """Verify results are consistent across concurrent calls."""

    def test_deterministic_results(self, connected_graph):
        """All threads should get identical results for the same computation."""
        barrier = threading.Barrier(NUM_WORKERS)
        all_results = []
        errors = []

        def worker():
            try:
                barrier.wait(timeout=5)
                dc = fnx.degree_centrality(connected_graph)
                all_results.append(dc)
            except Exception as e:
                errors.append(e)

        with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_WORKERS) as pool:
            futures = [pool.submit(worker) for _ in range(NUM_WORKERS)]
            concurrent.futures.wait(futures)

        assert not errors, f"Thread errors: {errors}"
        assert len(all_results) == NUM_WORKERS
        # All results should be identical.
        reference = all_results[0]
        for i, result in enumerate(all_results[1:], 1):
            assert set(result.keys()) == set(reference.keys()), (
                f"Thread {i} keys differ"
            )
            for k in reference:
                assert abs(result[k] - reference[k]) < 1e-10, (
                    f"Thread {i} value for {k} differs: {result[k]} vs {reference[k]}"
                )
