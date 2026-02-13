use fnx_conformance::{HarnessConfig, run_smoke};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let cfg = HarnessConfig::default_paths();
    let report = run_smoke(&cfg);
    println!(
        "suite={} fixtures={} mismatches={} oracle_present={}",
        report.suite, report.fixture_count, report.mismatch_count, report.oracle_present
    );

    if report.mismatch_count > 0 {
        return Err(format!("conformance mismatches detected: {}", report.mismatch_count).into());
    }

    Ok(())
}
