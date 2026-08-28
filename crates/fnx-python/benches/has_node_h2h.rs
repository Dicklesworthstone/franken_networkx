//! Head-to-head for `G.has_node`, run entirely on the worker in one invocation.
//!
//! br-r37-c1-p80x1. The README publishes `has_node` at 0.41x and the claim-coverage audit
//! lists it among three published LOSSES that are "still unverified numbers". Two beads
//! disagreed about it: br-r37-c1-native-method-attribute-lookup-tax-w7wjs concluded the
//! accessors are "at parity or better once measured honestly", while br-r37-c1-fov4a
//! recorded "still a loss". Instruction counts (artifact
//! 20260828-has-node-absent-int-silverlarch) showed both are right about different cells -
//! hits are at parity, absent keys lose, and the absent-INT cell reads 0.430x. This
//! measures the same four cells in WALL CLOCK.
//!
//! Both arms run in ONE process on ONE worker CPU in ONE invocation, so there is no local
//! ELF to retrieve and nothing to correlate across machines. The binary self-reports its
//! own SHA-256 and the NetworkX build actually imported.
//!
//! Protocol: arms interleaved inside one loop with the order reversed on odd rounds
//! (ABBA), median over rounds, and an A/A NULL arm - a SEPARATELY BUILT fnx graph timed
//! through the identical call protocol, because timing one object against itself is blind
//! to the spread between separately built fixtures. A row whose null strays from 1.0 is
//! reported as not quotable rather than quietly used.

use pyo3::prelude::*;
use pyo3::types::PyDict;
use sha2::{Digest, Sha256};
use std::ffi::CString;

fn self_identity() -> String {
    let Ok(path) = std::env::current_exe() else {
        return "unavailable".to_owned();
    };
    let Ok(bytes) = std::fs::read(&path) else {
        return "unavailable".to_owned();
    };
    let mut hasher = Sha256::new();
    hasher.update(&bytes);
    format!("{:x} ({} bytes)", hasher.finalize(), bytes.len())
}

fn cstring(source: &str) -> CString {
    CString::new(source).expect("Python snippets must not contain NUL bytes")
}

/// Bootstrap identical to `public_api_gauntlet`: repo root from CARGO_MANIFEST_DIR so the
/// paths resolve on a remote worker where CWD is not the repo, plus the freshly built
/// extension from this same cargo invocation.
fn preload_source() -> String {
    let repo_root = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .and_then(std::path::Path::parent)
        .expect("fnx-python crate must live under crates/")
        .to_str()
        .expect("repo path must be UTF-8");
    format!(
        "import importlib.util, os, sys
cwd = {repo_root:?}
for rel_path in (
    'crates/fnx-python/benches',
    'python',
    'legacy_networkx_code/networkx',
    'legacy_networkx_code',
):
    path = os.path.join(cwd, rel_path)
    if path not in sys.path:
        sys.path.insert(0, path)
available_cpus = sorted(os.sched_getaffinity(0))
if available_cpus:
    os.sched_setaffinity(0, set((available_cpus[-1],)))
    print(f'bench cpu: {{available_cpus[-1]}}', file=sys.stderr)
target_dir = os.environ.get('CARGO_TARGET_DIR') or os.path.join(cwd, 'target')
candidates = [
    os.path.join(target_dir, 'release', 'lib_fnx.so'),
    os.path.join(target_dir, 'release', 'libfnx_python.so'),
    os.path.join(cwd, 'python', 'franken_networkx', '_fnx.abi3.so'),
]
for path in candidates:
    if os.path.exists(path):
        spec = importlib.util.spec_from_file_location('franken_networkx._fnx', path)
        module = importlib.util.module_from_spec(spec)
        sys.modules['franken_networkx._fnx'] = module
        spec.loader.exec_module(module)
        print(f'fnx extension: {{path}}', file=sys.stderr)
        break
"
    )
}

/// The timing loop lives in Python so both arms are called through the identical
/// protocol - the same bound-method call, the same loop, the same interpreter.
const HARNESS: &str = r#"
import statistics, time
import networkx as nx
import franken_networkx as fnx

NX_BUILD = f"{nx.__version__} @ {nx.__file__}"

def _graph(mod, n, key):
    g = mod.Graph()
    names = [f"n{i}" for i in range(n)] if key == "str" else list(range(n))
    g.add_nodes_from(names)
    for i in range(0, n - 1, 2):
        g.add_edge(names[i], names[i + 1])
    return g, names

def run_cell(key, miss, n=2000, rounds=21, inner=2000):
    fg, names = _graph(fnx, n, key)
    ng, _ = _graph(nx, n, key)
    fg2, _ = _graph(fnx, n, key)      # separately built: the A/A null fixture
    if miss:
        probe = [f"zz{i}" for i in range(inner)] if key == "str" else [-(i + 1) for i in range(inner)]
    else:
        probe = [names[i % n] for i in range(inner)]

    arms = {"fnx": fg.has_node, "nx": ng.has_node, "null": fg2.has_node}
    samples = {k: [] for k in arms}
    for r in range(rounds):
        order = list(arms) if r % 2 == 0 else list(arms)[::-1]
        for name in order:
            fn = arms[name]
            t = time.perf_counter()
            for k in probe:
                fn(k)
            samples[name].append((time.perf_counter() - t) / len(probe))
    med = {k: statistics.median(v) for k, v in samples.items()}
    return med["nx"] / med["fnx"], med["null"] / med["fnx"], med["fnx"] * 1e9, med["nx"] * 1e9

def main():
    rows = []
    for key in ("str", "int"):
        for miss in (False, True):
            ratio, null, fns, nns = run_cell(key, miss)
            rows.append((key, "MISS" if miss else "hit", ratio, null, fns, nns))
    return rows
"#;

fn main() {
    pyo3::prepare_freethreaded_python();
    Python::attach(|py| {
        py.run(cstring(&preload_source()).as_c_str(), None, None)
            .expect("bootstrap failed: is legacy_networkx_code present?");
        let globals = PyDict::new(py);
        py.run(cstring(HARNESS).as_c_str(), Some(&globals), None)
            .expect("harness failed to define");
        let nx_build: String = globals
            .get_item("NX_BUILD")
            .expect("NX_BUILD lookup")
            .expect("NX_BUILD missing")
            .extract()
            .expect("NX_BUILD is a str");

        println!("bench_elf_sha256 {}", self_identity());
        println!("incumbent {nx_build}");
        println!(
            "{:<6} {:<6} {:>11} {:>9} {:>11} {:>11}",
            "key", "probe", "nx/fnx", "A/A null", "fnx ns", "nx ns"
        );

        let rows = globals
            .get_item("main")
            .expect("main lookup")
            .expect("main missing")
            .call0()
            .expect("harness main() raised");
        for row in rows.try_iter().expect("rows iterable") {
            let row = row.expect("row");
            let key: String = row.get_item(0).unwrap().extract().unwrap();
            let probe: String = row.get_item(1).unwrap().extract().unwrap();
            let ratio: f64 = row.get_item(2).unwrap().extract().unwrap();
            let null: f64 = row.get_item(3).unwrap().extract().unwrap();
            let fns: f64 = row.get_item(4).unwrap().extract().unwrap();
            let nns: f64 = row.get_item(5).unwrap().extract().unwrap();
            let flag = if (0.90..=1.10).contains(&null) {
                ""
            } else {
                "  <- NULL OUT OF BAND, not quotable"
            };
            println!(
                "{key:<6} {probe:<6} {ratio:10.3}x {null:9.3} {fns:10.1} {nns:10.1}{flag}"
            );
        }
    });
}
