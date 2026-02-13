use fnx_conformance::{HarnessConfig, run_smoke};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut cfg = HarnessConfig::default_paths();
    let mut args = std::env::args().skip(1);
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--fixture" => {
                let Some(value) = args.next() else {
                    return Err("--fixture requires a value".into());
                };
                cfg.fixture_filter = Some(value);
            }
            "--mode" => {
                let Some(value) = args.next() else {
                    return Err("--mode requires `strict` or `hardened`".into());
                };
                cfg.strict_mode = match value.as_str() {
                    "strict" => true,
                    "hardened" => false,
                    _ => return Err(format!("invalid --mode value `{value}`").into()),
                };
            }
            unknown => {
                return Err(format!("unknown argument `{unknown}`").into());
            }
        }
    }

    let report = run_smoke(&cfg);
    println!(
        "suite={} fixtures={} mismatches={} oracle_present={} structured_logs={}",
        report.suite,
        report.fixture_count,
        report.mismatch_count,
        report.oracle_present,
        report.structured_log_count
    );

    if cfg.fixture_filter.is_some() && report.fixture_count == 0 {
        return Err("fixture filter did not match any fixtures".into());
    }

    if report.mismatch_count > 0 {
        return Err(format!("conformance mismatches detected: {}", report.mismatch_count).into());
    }

    Ok(())
}
