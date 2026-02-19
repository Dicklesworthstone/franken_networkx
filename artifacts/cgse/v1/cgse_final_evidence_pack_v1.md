# CGSE Final Evidence Pack (V1)

- artifact id: `cgse-final-evidence-pack-v1`
- json: `artifacts/cgse/v1/cgse_final_evidence_pack_v1.json`

## Scope

CGSE completion bundle for deterministic tie-break semantics:

- Legacy extraction ledger
- Deterministic strict/hardened policy spec
- Semantics boundary threat model
- Conformance gates + replay commands
- Performance one-lever optimization evidence (baseline/candidate/delta)
- Durability sidecar + scrub + decode drill artifacts

## Quick Replay

1. Conformance gate:
   - `rch exec -- cargo test -p fnx-conformance --test cgse_legacy_tiebreak_gate -- --nocapture`
2. Runtime unit checks:
   - `rch exec -- cargo test -p fnx-runtime cgse_policy_engine_ -- --nocapture`
3. Perf microbench:
   - `rch exec -- cargo build -q -p fnx-runtime --bin cgse_policy_bench --release`
   - `/usr/bin/time -f 'elapsed_s=%e max_rss_kb=%M' ./target/release/cgse_policy_bench --iterations 2500000`

## Durability

The JSON artifact includes the durability commands and the expected sidecar paths:

- sidecar: `artifacts/cgse/v1/cgse_final_evidence_pack_v1.raptorq.json`
- recovered output: `artifacts/cgse/v1/cgse_final_evidence_pack_v1.recovered.json`
- scrub report: `artifacts/cgse/v1/cgse_final_evidence_pack_v1_scrub_report.json`

