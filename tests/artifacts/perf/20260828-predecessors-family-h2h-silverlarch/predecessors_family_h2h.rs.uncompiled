//! Head-to-head for the directed predecessors/successors family, run entirely on the worker.
//!
//! br-r37-c1-predrow-8vytj records `DiGraph.predecessors` at 0.383x with two controls that
//! agree it is a per-binding cost rather than a directed-graph or predecessor cost: the SAME
//! class's `successors` reads 0.819x and the OTHER class's `predecessors` reads 0.775x. Those
//! three numbers came from separate rows of a repeat-min harness at load ~9. This re-measures
//! all four family members with the incumbent live in the SAME invocation, so the subject and
//! its own controls share a process, a CPU and a fixture generation.
//!
//! Shapes are chosen so `predecessors` and `successors` are genuinely comparable: a circulant
//! (i -> i+1, i+2, i+3 mod n) gives EVERY node in-degree 3 and out-degree 3, and the hub shape
//! wires 2000 edges in each direction so both rows materialise 2000 items. A control that read
//! a different row width would not be a control.
//!
//! Protocol: arms interleaved inside one loop with the order reversed on odd rounds (ABBA),
//! median over rounds, and an A/A NULL arm - a SEPARATELY BUILT fnx graph through the identical
//! call protocol, because timing one object against itself is blind to the spread between
//! separately built fixtures. Every arm is warmed over the full probe list before the rounds
//! begin: `DiGraph.predecessors` keeps a keydict cache in the instance dict, and charging its
//! construction to round 1 would measure the cold path while claiming the warm one. A row whose
//! null strays from 1.0 is reported as not quotable rather than quietly used.
//!
//! Results go to STDERR so the remote runner returns them.

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

/// Repo root from CARGO_MANIFEST_DIR so paths resolve on a remote worker where CWD is not
/// the repo, plus the extension this same invocation will import.
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
# The workers now have networkx 3.6.1 installed, which is the release users actually have;
# the vendored legacy_networkx_code copy is 3.7rc0.dev0, a DEV PRERELEASE. Default to the
# installed one and keep the vendored path available for isolating the version variable.
_vendored = os.environ.get('FNX_INCUMBENT', 'installed') != 'installed'
_rel = ('python',)
if _vendored:
    _rel = _rel + ('legacy_networkx_code/networkx', 'legacy_networkx_code')
for rel_path in _rel:
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
        import hashlib
        with open(path, 'rb') as fh:
            _sha = hashlib.sha256(fh.read()).hexdigest()
        sys._fnx_ext = f'{{path}} sha256={{_sha}}'
        print(f'fnx extension: {{sys._fnx_ext}}', file=sys.stderr)
        break
"
    )
}

/// The timing loop lives in Python so every arm is called through the identical protocol -
/// the same bound-method call, the same `list()`, the same loop, the same interpreter.
const HARNESS: &str = r#"
import statistics, time
import networkx as nx
import franken_networkx as fnx

import sys as _sys
NX_BUILD = f"{nx.__version__} @ {nx.__file__}"
FNX_EXT = getattr(_sys, "_fnx_ext", "unavailable")

N = 1000

def build(mod, cls, shape):
    """The axis is NODE KEY LENGTH, which is what br-r37-c1-predrow-8vytj's K=3 / K=2000
    columns vary - NOT row width. Its networkx arm moves 149.4 -> 233.8 ns between the two,
    and materialising a 2000-element row could not cost 84 ns, so K is characters. That axis
    is the one that matters here: the Python shim this conversion replaced was FLAT in key
    length because it cached the row in the instance dict, so a native path resolving through
    a fresh canonical each call would have LOST at long keys. Measuring row width instead
    would never touch the property the fix was built to preserve.

    Circulant edges give every node in-degree 3 AND out-degree 3, so the `successors` control
    reads the same row width as the `predecessors` subject - a control on a different row
    width would not be a control."""
    g = getattr(mod, cls)()
    if shape == "key3":
        names = [f"{i:03d}" for i in range(N)]
    else:
        names = [f"{i:04d}".ljust(2000, "x") for i in range(N)]
    g.add_nodes_from(names)
    for i in range(N):
        for d in (1, 2, 3):
            g.add_edge(names[i], names[(i + d) % N])
    probes = names[::5]
    return g, probes

def run_cell(cls, meth, shape, rounds=15):
    fg, probes = build(fnx, cls, shape)
    ng, _ = build(nx, cls, shape)
    fg2, _ = build(fnx, cls, shape)      # separately built: the fnx-arm A/A null
    ng2, _ = build(nx, cls, shape)       # separately built: the nx-arm A/A null

    # DUAL NULLS. The commit that landed this conversion (4cbb18f78) reported all four of
    # its rows NULL-FAILED on the NETWORKX arm (0.972-0.975) while its fnx arm was clean,
    # and attributed that to a host slot asymmetry. A single fnx/fnx null is blind to
    # exactly that: it can read 1.000 while the incumbent arm is being systematically
    # advantaged or penalised, which is the one direction that moves a LOSS ratio.
    arms = {
        "fnx": getattr(fg, meth), "nx": getattr(ng, meth),
        "null_f": getattr(fg2, meth), "null_n": getattr(ng2, meth),
    }
    # Warm every arm over the full probe list. The Python shim this conversion replaced kept
    # a keydict cache in the instance dict; charging cache construction to round 1 would
    # measure a cold path while claiming the warm one.
    for fn in arms.values():
        for p in probes:
            list(fn(p))

    samples = {k: [] for k in arms}
    for r in range(rounds):
        order = list(arms) if r % 2 == 0 else list(arms)[::-1]
        for name in order:
            fn = arms[name]
            t = time.perf_counter()
            for p in probes:
                list(fn(p))
            samples[name].append((time.perf_counter() - t) / len(probes))
    med = {k: statistics.median(v) for k, v in samples.items()}
    return (med["nx"] / med["fnx"], med["null_f"] / med["fnx"], med["null_n"] / med["nx"],
            med["fnx"] * 1e9, med["nx"] * 1e9)

def main():
    rows = []
    for shape in ("key3", "key2000"):
        for cls in ("DiGraph", "MultiDiGraph"):
            for meth in ("predecessors", "successors"):
                ratio, null_f, null_n, fns, nns = run_cell(cls, meth, shape)
                rows.append((shape, cls, meth, ratio, null_f, null_n, fns, nns))
    return rows
"#;

fn main() {
    Python::initialize();
    Python::attach(|py| {
        py.run(cstring(&preload_source()).as_c_str(), None, None)
            .expect("bootstrap failed");
        let globals = PyDict::new(py);
        py.run(cstring(HARNESS).as_c_str(), Some(&globals), None)
            .expect("harness failed to define");

        let fetch = |name: &str| -> String {
            globals
                .get_item(name)
                .expect("lookup")
                .expect("missing")
                .extract()
                .expect("is a str")
        };
        eprintln!("bench_elf_sha256 {}", self_identity());
        eprintln!("fnx_extension {}", fetch("FNX_EXT"));
        eprintln!("incumbent {}", fetch("NX_BUILD"));
        eprintln!(
            "{:<7} {:<13} {:<13} {:>10} {:>9} {:>9} {:>10} {:>10}",
            "shape", "class", "method", "nx/fnx", "null fnx", "null nx", "fnx ns", "nx ns"
        );

        let rows = globals
            .get_item("main")
            .expect("main lookup")
            .expect("main missing")
            .call0()
            .expect("harness main() raised");
        for row in rows.try_iter().expect("rows iterable") {
            let row = row.expect("row");
            let get_s = |i: usize| -> String { row.get_item(i).unwrap().extract().unwrap() };
            let get_f = |i: usize| -> f64 { row.get_item(i).unwrap().extract().unwrap() };
            let (shape, cls, meth) = (get_s(0), get_s(1), get_s(2));
            let (ratio, null_f, null_n) = (get_f(3), get_f(4), get_f(5));
            let (fns, nns) = (get_f(6), get_f(7));
            // Both nulls gate the row. A clean fnx null next to a strayed nx null is the
            // asymmetry 4cbb18f78 reported, and it moves a loss ratio in the flattering
            // direction, so it disqualifies the row rather than being noted in passing.
            let band = 0.90..=1.10;
            let flag = match (band.contains(&null_f), band.contains(&null_n)) {
                (true, true) => "",
                (true, false) => "  <- NX-ARM NULL OUT OF BAND, not quotable",
                (false, true) => "  <- FNX-ARM NULL OUT OF BAND, not quotable",
                (false, false) => "  <- BOTH NULLS OUT OF BAND, not quotable",
            };
            eprintln!(
                "{shape:<7} {cls:<13} {meth:<13} {ratio:9.3}x {null_f:9.3} {null_n:9.3} {fns:10.1} {nns:10.1}{flag}"
            );
        }
    });
}
