//! Re-measure the rejected `if not storage: return False` short-circuit in
//! `_has_networkx_private_storage`, WITH the candidate-arm A/A null the ledger gate demands.
//!
//! br-r37-c1-oj681: three rejected levers cannot enter NEGATIVE_EVIDENCE_cc.md because
//! `scripts/perf_ledger_preflight.py` refuses them —
//!
//!     [FAIL] VOID-NONULL - 1 REJECT row(s) carry neither a positively recorded
//!     same-invocation A/A null control nor a counted mechanism.
//!
//! The gate is right and the bead's author reverted the append rather than reword the heading
//! to dodge it. To RECORD a rejection you must first have MEASURED it admissibly, and these
//! were timed with plain repeat-min and no nulls.
//!
//! This supplies BOTH admissible forms for item 3:
//!
//!   * a COUNTED MECHANISM - the size of the instance dict, and how often the short-circuit
//!     predicate actually fires, on graphs in each regime. Deterministic, no timing;
//!   * a WALL-CLOCK A/B with a same-invocation A/A NULL ON EACH CANDIDATE ARM - the control
//!     the gate names. This is a SELF-comparison (fnx against fnx), which is MAINTENANCE and
//!     not a campaign win; it is the right shape for a REJECT verdict, whose whole claim is
//!     about our own two implementations.
//!
//! THE REGIME IS THE POINT. The source comment records the trap: the short-circuit "looks like
//! a 2.16x win if measured on a graph whose accessors were never touched, which is not a graph
//! any caller has". So both regimes are measured - a FRESH graph and a REALISTICALLY USED one
//! whose `.adj`/`.edges`/`.nodes` have been touched - and the disagreement between them IS the
//! finding.
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
for rel_path in ('python',):
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

const HARNESS: &str = r#"
import statistics, time
import franken_networkx as fnx
from franken_networkx import (
    _PRIVATE_NODE_OVERRIDE, _PRIVATE_ADJ_OVERRIDE,
    _PRIVATE_SUCC_OVERRIDE, _PRIVATE_PRED_OVERRIDE,
    _has_networkx_private_storage as REAL,
)

import sys as _sys
FNX_EXT = getattr(_sys, "_fnx_ext", "unavailable")

N = 400

# ---- the two arms, byte-for-byte the shipped body and the shipped body + the rejected test.
def current(self):
    storage = self.__dict__
    return (
        _PRIVATE_NODE_OVERRIDE in storage
        or _PRIVATE_ADJ_OVERRIDE in storage
        or _PRIVATE_SUCC_OVERRIDE in storage
        or _PRIVATE_PRED_OVERRIDE in storage
    )

def shortcircuit(self):
    storage = self.__dict__
    if not storage:
        return False
    return (
        _PRIVATE_NODE_OVERRIDE in storage
        or _PRIVATE_ADJ_OVERRIDE in storage
        or _PRIVATE_SUCC_OVERRIDE in storage
        or _PRIVATE_PRED_OVERRIDE in storage
    )

def make(regime):
    g = fnx.DiGraph()
    g.add_nodes_from(range(N))
    for i in range(N):
        for d in (1, 2, 3):
            g.add_edge(i, (i + d) % N)
    if regime == "used":
        # What any real caller has done by the time this probe is hot: touch the accessors.
        g.adj, g.edges, g.nodes
        for i in range(0, N, 50):
            list(g.neighbors(i))
            g.edges[i, (i + 1) % N]
    return g

def counted():
    """The COUNTED MECHANISM, deterministic and load-independent: how big is the instance
    dict, and does the short-circuit predicate EVER fire?"""
    out = []
    for regime in ("fresh", "used"):
        g = make(regime)
        d = g.__dict__
        out.append((regime, len(d), (not d), sorted(d)[:6]))
    return out

def fidelity():
    """Guard against measuring a divergent copy: the harness's `current` must agree with the
    SHIPPED `_has_networkx_private_storage` on every probe graph, including one carrying a
    real private-storage override."""
    checks = []
    for regime in ("fresh", "used"):
        g = make(regime)
        checks.append(current(g) == REAL(g) == shortcircuit(g))
        g._adj = {0: {}}                      # a real override: all three must now say True
        checks.append(current(g) == REAL(g) == shortcircuit(g) is True)
    return all(checks)

def run_cell(regime, rounds=21, inner=20000):
    g1, g2 = make(regime), make(regime)       # separately built: the A/A null fixtures
    arms = {"cur": (current, g1), "cur_null": (current, g2),
            "sc": (shortcircuit, g1), "sc_null": (shortcircuit, g2)}
    for fn, g in arms.values():
        for _ in range(inner):
            fn(g)
    samples = {k: [] for k in arms}
    for r in range(rounds):
        order = list(arms) if r % 2 == 0 else list(arms)[::-1]
        for name in order:
            fn, g = arms[name]
            t = time.perf_counter()
            for _ in range(inner):
                fn(g)
            samples[name].append((time.perf_counter() - t) / inner)
    m = {k: statistics.median(v) for k, v in samples.items()}
    # ratio > 1 means the SHORT-CIRCUIT is faster, i.e. the lever would have been a win
    return (m["cur"] / m["sc"], m["cur_null"] / m["cur"], m["sc_null"] / m["sc"],
            m["cur"] * 1e9, m["sc"] * 1e9)

def main():
    return fidelity(), counted(), [(r,) + run_cell(r) for r in ("fresh", "used")]
"#;

fn main() {
    Python::initialize();
    Python::attach(|py| {
        py.run(cstring(&preload_source()).as_c_str(), None, None)
            .expect("bootstrap failed");
        let globals = PyDict::new(py);
        py.run(cstring(HARNESS).as_c_str(), Some(&globals), None)
            .expect("harness failed to define");

        let ext: String = globals
            .get_item("FNX_EXT").unwrap().unwrap().extract().unwrap();
        eprintln!("bench_elf_sha256 {}", self_identity());
        eprintln!("fnx_extension {ext}");

        let out = globals
            .get_item("main").unwrap().unwrap().call0().expect("harness main() raised");
        let fidelity: bool = out.get_item(0).unwrap().extract().unwrap();
        eprintln!("harness_matches_shipped_function {fidelity}");
        if !fidelity {
            eprintln!("FIDELITY FAILED - the arms do not agree with the shipped function; \
                       every number below is void");
        }

        eprintln!("\nCOUNTED MECHANISM (deterministic, no timing):");
        eprintln!("{:<8} {:>12} {:>18}   {}", "regime", "len(__dict__)", "short-circuit fires", "first keys");
        for row in out.get_item(1).unwrap().try_iter().unwrap() {
            let row = row.unwrap();
            let regime: String = row.get_item(0).unwrap().extract().unwrap();
            let n: usize = row.get_item(1).unwrap().extract().unwrap();
            let fires: bool = row.get_item(2).unwrap().extract().unwrap();
            let keys: Vec<String> = row.get_item(3).unwrap().extract().unwrap();
            eprintln!("{regime:<8} {n:>12} {fires:>18}   {}", keys.join(", "));
        }

        eprintln!("\nWALL CLOCK, candidate-arm A/A nulls (ratio > 1 = short-circuit faster):");
        eprintln!(
            "{:<8} {:>10} {:>10} {:>10} {:>10} {:>10}",
            "regime", "cur/sc", "null cur", "null sc", "cur ns", "sc ns"
        );
        for row in out.get_item(2).unwrap().try_iter().unwrap() {
            let row = row.unwrap();
            let regime: String = row.get_item(0).unwrap().extract().unwrap();
            let g = |i: usize| -> f64 { row.get_item(i).unwrap().extract().unwrap() };
            let (ratio, null_c, null_s, cur, sc) = (g(1), g(2), g(3), g(4), g(5));
            let band = 0.90..=1.10;
            let flag = match (band.contains(&null_c), band.contains(&null_s)) {
                (true, true) => "",
                (true, false) => "  <- SC-ARM NULL OUT OF BAND, withheld",
                (false, true) => "  <- CUR-ARM NULL OUT OF BAND, withheld",
                (false, false) => "  <- BOTH NULLS OUT OF BAND, withheld",
            };
            eprintln!("{regime:<8} {ratio:9.4}x {null_c:10.3} {null_s:10.3} {cur:10.1} {sc:10.1}{flag}");
        }
    });
}
