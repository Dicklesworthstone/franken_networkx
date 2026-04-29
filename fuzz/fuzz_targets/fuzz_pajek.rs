//! Fuzz target for Pajek (.net) format parser.
//!
//! Tests the native Rust Pajek parser with arbitrary input to find
//! crashes, hangs, and memory safety issues.

#![no_main]

use libfuzzer_sys::fuzz_target;
use std::fmt::Write;

fn parse_all(input: &str) {
    // Strict mode: must return Err, never panic.
    let mut strict = fnx_readwrite::EdgeListEngine::strict();
    let _ = strict.read_pajek(input);

    // Hardened mode: must return Ok with warnings or Ok empty, never panic.
    let mut hardened = fnx_readwrite::EdgeListEngine::hardened();
    let _ = hardened.read_pajek(input);

    // DiGraph variants.
    let mut strict_di = fnx_readwrite::EdgeListEngine::strict();
    let _ = strict_di.read_digraph_pajek(input);

    let mut hardened_di = fnx_readwrite::EdgeListEngine::hardened();
    let _ = hardened_di.read_digraph_pajek(input);
}

fn sanitized_label(data: &[u8], fallback: &str) -> String {
    let mut label = String::new();
    for byte in data.iter().copied().take(16) {
        let ch = byte as char;
        if ch.is_ascii_alphanumeric() || matches!(ch, '_' | '-' | '.') {
            label.push(ch);
        }
    }
    if label.is_empty() {
        fallback.to_owned()
    } else {
        label
    }
}

fn pajek_weight(selector: u8) -> &'static str {
    match selector % 8 {
        0 => "0",
        1 => "1",
        2 => "-1",
        3 => "0.5",
        4 => "2.75",
        5 => "1e3",
        6 => "NaN",
        _ => "not-a-weight",
    }
}

fn synthesize_pajek(data: &[u8]) -> String {
    let selector = data.first().copied().unwrap_or(0);
    let node_count = usize::from(selector % 8);
    let declared_count = match data.get(1).copied().unwrap_or(0) % 4 {
        0 => node_count,
        1 => node_count.saturating_add(1),
        2 => node_count.saturating_sub(1),
        _ => 10,
    };
    let section = match data.get(2).copied().unwrap_or(0) % 5 {
        0 => "*Edges",
        1 => "*Arcs",
        2 => "*Edgeslist",
        3 => "*Arcslist",
        _ => "*UnknownSection",
    };

    let mut input = String::new();
    let _ = writeln!(input, "% synthesized by fuzz_pajek");
    let _ = writeln!(input, "*Vertices {declared_count}");

    for idx in 0..node_count {
        let start = 3 + idx * 3;
        let end = data.len().min(start + 3);
        let label = sanitized_label(data.get(start..end).unwrap_or_default(), "node");
        if data.get(start).copied().unwrap_or(0) % 3 == 0 {
            let _ = writeln!(input, "{} \"{} {}\"", idx + 1, label, idx);
        } else {
            let _ = writeln!(input, "{} {}", idx + 1, label);
        }
    }

    let _ = writeln!(input, "{section}");

    let edge_budget = usize::from(data.get(3).copied().unwrap_or(0) % 12);
    for edge_idx in 0..edge_budget {
        let left = if node_count == 0 {
            0
        } else {
            usize::from(data.get(4 + edge_idx * 3).copied().unwrap_or(0)) % node_count + 1
        };
        let right = if node_count == 0 {
            0
        } else {
            usize::from(data.get(5 + edge_idx * 3).copied().unwrap_or(0)) % node_count + 1
        };
        let weight = pajek_weight(data.get(6 + edge_idx * 3).copied().unwrap_or(0));

        if data.get(edge_idx).copied().unwrap_or(0) % 7 == 0 {
            let _ = writeln!(input, "{left}");
        } else if data.get(edge_idx).copied().unwrap_or(0) % 11 == 0 {
            let _ = writeln!(input, "bad {right} {weight}");
        } else {
            let _ = writeln!(input, "{left} {right} {weight}");
        }
    }

    input
}

fuzz_target!(|data: &[u8]| {
    if let Ok(input) = std::str::from_utf8(data) {
        parse_all(input);
    }

    let synthesized = synthesize_pajek(data);
    parse_all(&synthesized);
});
