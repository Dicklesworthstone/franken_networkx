#![forbid(unsafe_code)]

use pyo3::prelude::*;
use pyo3::types::PyModule;
use std::env;
use std::error::Error;
use std::ffi::CString;
use std::fs;
use std::io::Read;
use std::path::{Path, PathBuf};

const GENERATOR_SOURCE: &str = include_str!("../behavioral_oracle.py");
const MAX_CASE_BYTES: u64 = 32_768;

#[derive(Debug, PartialEq, Eq)]
enum Operation {
    Write,
    Check,
    CaseFile(PathBuf),
}

fn parse_operation(arguments: &[String]) -> Result<Operation, String> {
    match arguments {
        [argument] if argument == "--write" => Ok(Operation::Write),
        [argument] if argument == "--check" => Ok(Operation::Check),
        [argument, path] if argument == "--case-file" && !path.is_empty() => {
            Ok(Operation::CaseFile(PathBuf::from(path)))
        }
        _ => Err(
            "usage: feature_behavioral_oracle (--write | --check | --case-file FILE)".to_owned(),
        ),
    }
}

fn discover_site_packages(repo_root: &Path) -> Result<PathBuf, Box<dyn Error>> {
    let virtualenv_lib = repo_root.join(".venv/lib");
    let mut candidates = Vec::new();
    for entry in fs::read_dir(&virtualenv_lib)? {
        let entry = entry?;
        if !entry.file_type()?.is_dir() {
            continue;
        }
        let site_packages = entry.path().join("site-packages");
        if site_packages.is_dir() {
            candidates.push(site_packages);
        }
    }
    candidates.sort();
    candidates.into_iter().next().ok_or_else(|| {
        format!(
            "no Python site-packages directory found below {}",
            virtualenv_lib.display()
        )
        .into()
    })
}

fn discover_repo_root() -> Result<PathBuf, Box<dyn Error>> {
    let current_dir = env::current_dir()?;
    for candidate in current_dir.ancestors() {
        if candidate.join("docs/coverage.md").is_file()
            && candidate.join("python/franken_networkx").is_dir()
        {
            return Ok(candidate.to_path_buf());
        }
    }
    Err(format!(
        "could not find FrankenNetworkX repository root from {}",
        current_dir.display()
    )
    .into())
}

fn prepend_python_path(py: Python<'_>, path: &Path) -> Result<(), Box<dyn Error>> {
    let path = path
        .to_str()
        .ok_or_else(|| format!("Python path is not UTF-8: {}", path.display()))?;
    PyModule::import(py, "sys")?
        .getattr("path")?
        .call_method1("insert", (0, path))?;
    Ok(())
}

fn read_case_request(reader: impl Read) -> Result<String, Box<dyn Error>> {
    let mut request = Vec::new();
    reader.take(MAX_CASE_BYTES + 1).read_to_end(&mut request)?;
    if u64::try_from(request.len())? > MAX_CASE_BYTES {
        return Err("case request exceeds 32768 bytes".into());
    }
    Ok(String::from_utf8(request)?)
}

fn main() -> Result<(), Box<dyn Error>> {
    let arguments: Vec<String> = env::args().skip(1).collect();
    let operation = parse_operation(&arguments)
        .map_err(|message| std::io::Error::new(std::io::ErrorKind::InvalidInput, message))?;
    // A packaged single-case oracle uses the selected interpreter's normal
    // module search path. Only full corpus operations require checkout data.
    let (repo_root, case_request) = match &operation {
        Operation::CaseFile(path) => (None, Some(read_case_request(fs::File::open(path)?)?)),
        Operation::Write | Operation::Check => (Some(discover_repo_root()?.canonicalize()?), None),
    };
    let site_packages = repo_root
        .as_deref()
        .map(discover_site_packages)
        .transpose()?;
    let generator_source = CString::new(GENERATOR_SOURCE)?;

    let summary = Python::attach(|py| -> PyResult<String> {
        if let Some(site_packages) = &site_packages {
            prepend_python_path(py, site_packages)
                .map_err(|error| pyo3::exceptions::PyRuntimeError::new_err(error.to_string()))?;
        }
        if let Some(repo_root) = &repo_root {
            prepend_python_path(py, &repo_root.join("python"))
                .map_err(|error| pyo3::exceptions::PyRuntimeError::new_err(error.to_string()))?;
        }
        let generator = PyModule::from_code(
            py,
            generator_source.as_c_str(),
            c"generate_behavioral_oracle.py",
            c"fnx_behavioral_oracle",
        )?;
        match (repo_root.as_ref(), case_request.as_ref()) {
            (_, Some(request)) => generator
                .getattr("run_case_from_pyo3")?
                .call1((request,))?
                .extract(),
            (Some(repo_root), None) => generator
                .getattr("run_from_pyo3")?
                .call1((
                    repo_root.to_string_lossy().as_ref(),
                    matches!(operation, Operation::Check),
                ))?
                .extract(),
            (None, None) => Err(pyo3::exceptions::PyRuntimeError::new_err(
                "oracle operation has neither a repository nor a case request",
            )),
        }
    })?;
    println!("{summary}");
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::{Operation, parse_operation, read_case_request};
    use std::path::PathBuf;

    #[test]
    fn corpus_operations_and_packaged_case_are_explicit() {
        assert_eq!(parse_operation(&["--write".into()]), Ok(Operation::Write));
        assert_eq!(parse_operation(&["--check".into()]), Ok(Operation::Check));
        assert_eq!(
            parse_operation(&["--case-file".into(), "input.json".into()]),
            Ok(Operation::CaseFile(PathBuf::from("input.json")))
        );
    }

    #[test]
    fn malformed_or_combined_operations_are_rejected() {
        for arguments in [
            vec![],
            vec!["--case-file".into()],
            vec!["--case-file".into(), String::new()],
            vec!["--write".into(), "--check".into()],
            vec!["--unknown".into()],
            vec!["--case-file".into(), "input.json".into(), "extra".into()],
        ] {
            assert!(parse_operation(&arguments).is_err());
        }
    }

    #[test]
    fn case_input_is_byte_bounded_before_utf8_decoding() {
        let at_limit = "x".repeat(32_768);
        assert_eq!(read_case_request(at_limit.as_bytes()).unwrap(), at_limit);
        let beyond_limit = "é".repeat(16_385);
        let error = read_case_request(beyond_limit.as_bytes()).unwrap_err();
        assert_eq!(error.to_string(), "case request exceeds 32768 bytes");
        assert!(read_case_request([0xff].as_slice()).is_err());
    }
}
