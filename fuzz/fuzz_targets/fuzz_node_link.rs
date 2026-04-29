#![no_main]

use fnx_python::parse_raw_node_link_json;
use libfuzzer_sys::fuzz_target;

fn sanitized_identifier(data: &[u8], fallback: &str) -> String {
    let mut out = String::new();
    for byte in data.iter().copied().take(16) {
        let ch = byte as char;
        if ch.is_ascii_alphanumeric() || ch == '_' || ch == '-' {
            out.push(ch.to_ascii_lowercase());
        }
    }
    if out.is_empty() {
        fallback.to_owned()
    } else {
        out
    }
}

fn json_string(data: &[u8]) -> String {
    let mut out = String::new();
    for ch in String::from_utf8_lossy(data).chars().take(64) {
        match ch {
            '\\' => out.push_str("\\\\"),
            '"' => out.push_str("\\\""),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            ch if ch.is_control() => {
                let _ = std::fmt::Write::write_fmt(&mut out, format_args!("\\u{:04x}", ch as u32));
            }
            _ => out.push(ch),
        }
    }
    out
}

fn flag_literal(selector: u8, key: &str) -> String {
    match selector.wrapping_add(key.len() as u8) % 6 {
        0 => "true".to_owned(),
        1 => "false".to_owned(),
        2 => "1".to_owned(),
        3 => "\"yes\"".to_owned(),
        4 => "null".to_owned(),
        _ => "{}".to_owned(),
    }
}

fuzz_target!(|data: &[u8]| {
    let Ok(raw_input) = std::str::from_utf8(data) else {
        return;
    };

    let _ = parse_raw_node_link_json(raw_input);

    let split = (data.len() / 4).max(1);
    let node_a = sanitized_identifier(&data[..data.len().min(split)], "a");
    let node_b = sanitized_identifier(
        &data[data.len().min(split)..data.len().min(split.saturating_mul(2))],
        "b",
    );
    let attr_key = sanitized_identifier(
        &data[data.len().min(split.saturating_mul(2))..data.len().min(split.saturating_mul(3))],
        "name",
    );
    let attr_value = json_string(&data[data.len().min(split.saturating_mul(3))..]);

    let payload = format!(
        concat!(
            "{{",
            "\"mode\":\"strict\",",
            "\"directed\":{directed},",
            "\"multigraph\":{multigraph},",
            "\"graph_attrs\":{{\"{attr_key}\":\"{attr_value}\"}},",
            "\"nodes\":[\"{node_a}\",\"{node_b}\"],",
            "\"edges\":[{{\"left\":\"{node_a}\",\"right\":\"{node_b}\",\"attrs\":{{}}}}]",
            "}}"
        ),
        directed = flag_literal(data.first().copied().unwrap_or(0), "directed"),
        multigraph = flag_literal(data.get(1).copied().unwrap_or(0), "multigraph"),
        attr_key = attr_key,
        attr_value = attr_value,
        node_a = node_a,
        node_b = node_b,
    );

    let _ = parse_raw_node_link_json(&payload);
});
