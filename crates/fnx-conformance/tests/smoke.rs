use fnx_conformance::{HarnessConfig, run_smoke};

#[test]
fn smoke_report_is_stable() {
    let cfg = HarnessConfig::default_paths();
    let report = run_smoke(&cfg);
    assert_eq!(report.suite, "smoke");
    assert!(report.fixture_count >= 1);
    assert!(report.oracle_present);
    assert_eq!(report.mismatch_count, 0);
    assert!(report.fixture_reports.iter().all(|fixture| fixture.passed));
}
