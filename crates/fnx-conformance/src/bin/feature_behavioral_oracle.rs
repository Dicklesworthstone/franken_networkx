#![forbid(unsafe_code)]

use pyo3::prelude::*;
use pyo3::types::PyModule;
use std::env;
use std::error::Error;
use std::ffi::CString;
use std::fs;
use std::path::{Path, PathBuf};

const GENERATOR_SOURCE: &str = include_str!("../../../../scripts/generate_behavioral_oracle.py");

#[derive(Clone, Copy)]
enum Operation {
    Write,
    Check,
}

impl Operation {
    fn check(self) -> bool {
        matches!(self, Self::Check)
    }
}

fn parse_operation() -> Result<Operation, String> {
    let arguments: Vec<String> = env::args().skip(1).collect();
    match arguments.as_slice() {
        [argument] if argument == "--write" => Ok(Operation::Write),
        [argument] if argument == "--check" => Ok(Operation::Check),
        _ => Err("usage: feature_behavioral_oracle (--write | --check)".to_owned()),
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

fn main() -> Result<(), Box<dyn Error>> {
    let operation = parse_operation()
        .map_err(|message| std::io::Error::new(std::io::ErrorKind::InvalidInput, message))?;
    let repo_root = discover_repo_root()?.canonicalize()?;
    let site_packages = discover_site_packages(&repo_root)?;
    let python_package_root = repo_root.join("python");
    let generator_source = CString::new(GENERATOR_SOURCE)?;

    let summary = Python::attach(|py| -> PyResult<String> {
        prepend_python_path(py, &site_packages)
            .map_err(|error| pyo3::exceptions::PyRuntimeError::new_err(error.to_string()))?;
        prepend_python_path(py, &python_package_root)
            .map_err(|error| pyo3::exceptions::PyRuntimeError::new_err(error.to_string()))?;
        let generator = PyModule::from_code(
            py,
            generator_source.as_c_str(),
            c"generate_behavioral_oracle.py",
            c"fnx_behavioral_oracle",
        )?;
        generator
            .getattr("run_from_pyo3")?
            .call1((repo_root.to_string_lossy().as_ref(), operation.check()))?
            .extract()
    })?;
    println!("{summary}");
    Ok(())
}
