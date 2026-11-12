//! Worker-side live NetworkX/FNX head-to-head for br-r37-c1-p80x1.14.
//!
//! Run with RCH only:
//! `FNX_INCUMBENT=installed rch exec -- cargo run --release -p fnx-python --example minimum_branching_h2h`.
//! The benchmark refuses any NetworkX other than 3.6.1, validates the entire
//! preregistered result before timing, uses a separately built FNX A/A arm,
//! and writes every result to stderr so the remote transcript is the evidence.

use pyo3::prelude::*;
use pyo3::types::PyDict;
use sha2::{Digest, Sha256};
use std::ffi::CString;

fn cstring(source: &str) -> CString {
    CString::new(source).expect("embedded Python must not contain NUL")
}

fn self_sha256() -> String {
    let path = std::env::current_exe().expect("running executable path");
    let bytes = std::fs::read(&path).expect("read running executable");
    format!("{:x}", Sha256::digest(bytes))
}

fn preload_source() -> String {
    let repo_root = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .and_then(std::path::Path::parent)
        .expect("fnx-python must live under crates/")
        .to_str()
        .expect("repository path must be UTF-8");
    format!(
        r#"
import hashlib, importlib.util, os, sys
repo_root = {repo_root:?}
paths = ["python"]
if os.environ.get("FNX_INCUMBENT") != "installed":
    paths.append("legacy_networkx_code")
for relative in paths:
    path = os.path.join(repo_root, relative)
    if path not in sys.path:
        sys.path.insert(0, path)
target = os.environ.get("CARGO_TARGET_DIR") or os.path.join(repo_root, "target")
candidates = (
    os.path.join(target, "release", "lib_fnx.so"),
    os.path.join(target, "release", "libfnx_python.so"),
)
for candidate in candidates:
    if os.path.exists(candidate):
        spec = importlib.util.spec_from_file_location("franken_networkx._fnx", candidate)
        module = importlib.util.module_from_spec(spec)
        sys.modules["franken_networkx._fnx"] = module
        spec.loader.exec_module(module)
        with open(candidate, "rb") as fh:
            sys._fnx_elf = f"{{candidate}} sha256={{hashlib.sha256(fh.read()).hexdigest()}}"
        break
else:
    raise RuntimeError(f"fresh release FNX extension absent under {{target}}")
"#
    )
}

const HARNESS: &str = r#"
import hashlib, os, statistics, time
import networkx as nx
import franken_networkx as fnx
from scripts.perf_harness import _build_ordered_arc_pair, canonical_bytes

if nx.__version__ != "3.6.1":
    raise RuntimeError(f"need worker-installed NetworkX 3.6.1, got {nx.__version__} from {nx.__file__}")

NODES, EDGES, SEED = 800, 4000, 11
INPUT_BYTES = 189_843
INPUT_SHA256 = "5d7c003cd5c7507408804b01e266bb81d7cfb2fe6546c58dfebff60f621ea89b"
OUTPUT_BYTES = 16_707
OUTPUT_SHA256 = "e6fd694bc8cd85ad2b23c9bc1ed6a76292330fde172c0f2f6beb6f48ebdf2469"

def checked_graphs():
    nx_graph, fnx_graph = _build_ordered_arc_pair(NODES, EDGES, SEED, weighted=True)
    nx_input = canonical_bytes(nx_graph)
    fnx_input = canonical_bytes(fnx_graph)
    if (nx_input != fnx_input or len(nx_input) != INPUT_BYTES
            or hashlib.sha256(nx_input).hexdigest() != INPUT_SHA256):
        raise RuntimeError("minimum_branching input fixture drifted")
    return nx_graph, fnx_graph

def checked_result(module, graph):
    result = module.minimum_branching(graph)
    encoded = canonical_bytes(result)
    if (type(result) is not module.DiGraph or result.number_of_nodes() != NODES
            or result.number_of_edges() != 0 or len(encoded) != OUTPUT_BYTES
            or hashlib.sha256(encoded).hexdigest() != OUTPUT_SHA256):
        raise RuntimeError("minimum_branching complete empty-edge result drifted")
    return result

def time_arm(fn):
    started = time.perf_counter()
    result = fn()
    elapsed = time.perf_counter() - started
    if result.number_of_edges() != 0:
        raise RuntimeError("timed minimum_branching result changed")
    return elapsed

def main():
    nx_graph, fnx_graph = checked_graphs()
    _, fnx_null_graph = checked_graphs()
    checked_result(nx, nx_graph)
    checked_result(fnx, fnx_graph)
    checked_result(fnx, fnx_null_graph)
    arms = {
        "nx": lambda: nx.minimum_branching(nx_graph),
        "fnx": lambda: fnx.minimum_branching(fnx_graph),
        "null": lambda: fnx.minimum_branching(fnx_null_graph),
    }
    samples = {name: [] for name in arms}
    for round_index in range(21):
        order = ("nx", "fnx", "null", "null", "fnx", "nx")
        if round_index % 2:
            order = tuple(reversed(order))
        for name in order:
            samples[name].append(time_arm(arms[name]))
    median = {name: statistics.median(values) for name, values in samples.items()}
    return {
        "ratio": median["nx"] / median["fnx"],
        "aa_null": median["null"] / median["fnx"],
        "fnx_us": median["fnx"] * 1e6,
        "nx_us": median["nx"] * 1e6,
        "networkx": f"{nx.__version__} @ {nx.__file__}",
        "extension": getattr(__import__("sys"), "_fnx_elf", "unavailable"),
    }
"#;

fn main() {
    Python::initialize();
    Python::attach(|py| {
        py.run(cstring(&preload_source()).as_c_str(), None, None)
            .expect("fresh extension bootstrap failed");
        let globals = PyDict::new(py);
        py.run(cstring(HARNESS).as_c_str(), Some(&globals), None)
            .expect("H2H harness definition failed");
        let outcome = globals
            .get_item("main")
            .expect("H2H main lookup")
            .expect("H2H main absent")
            .call0()
            .expect("H2H preflight or timing failed");
        let ratio: f64 = outcome.get_item("ratio").unwrap().extract().unwrap();
        let aa_null: f64 = outcome.get_item("aa_null").unwrap().extract().unwrap();
        let fnx_us: f64 = outcome.get_item("fnx_us").unwrap().extract().unwrap();
        let nx_us: f64 = outcome.get_item("nx_us").unwrap().extract().unwrap();
        let networkx: String = outcome.get_item("networkx").unwrap().extract().unwrap();
        let extension: String = outcome.get_item("extension").unwrap().extract().unwrap();
        let admission = if (0.98..=1.02).contains(&aa_null) {
            "ADMISSIBLE"
        } else {
            "NULL_OUT_OF_BAND"
        };
        eprintln!("bead br-r37-c1-p80x1.14");
        eprintln!("worker_executable_sha256 {}", self_sha256());
        eprintln!("fnx_extension {extension}");
        eprintln!("incumbent {networkx}");
        eprintln!(
            "minimum_branching nx/fnx {ratio:.4}x; A/A {aa_null:.4}; fnx {fnx_us:.3}us; nx {nx_us:.3}us; {admission}"
        );
    });
}
