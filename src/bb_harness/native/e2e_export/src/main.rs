mod binding;
mod compat;
mod export;
mod render;
#[cfg(target_os = "linux")]
mod shared_publish;

use clap::Parser;
use std::collections::BTreeMap;
use std::fs;
use std::io;
use std::path::{Path, PathBuf};
use std::process::ExitCode;

#[derive(Parser)]
#[command(version, about = "Export reviewed manual-bb cases for Lakda replay")]
struct Args {
    #[arg(long)]
    feature_spec: PathBuf,
    #[arg(long)]
    manual_case_set: PathBuf,
    #[arg(long)]
    binding: PathBuf,
    #[arg(long)]
    approved_binding_sha256: String,
    #[arg(long)]
    out: PathBuf,
}

#[cfg(windows)]
fn publish_directory(source: &Path, destination: &Path) -> io::Result<()> {
    use std::os::windows::ffi::OsStrExt;
    use windows_sys::Win32::Storage::FileSystem::MoveFileExW;
    let wide = |path: &Path| {
        path.as_os_str()
            .encode_wide()
            .chain(Some(0))
            .collect::<Vec<_>>()
    };
    let (from, to) = (wide(source), wide(destination));
    // Both buffers are NUL terminated and live through the call. Zero flags forbid replacement.
    if unsafe { MoveFileExW(from.as_ptr(), to.as_ptr(), 0) } == 0 {
        return Err(io::Error::last_os_error());
    }
    Ok(())
}

#[cfg(any(target_os = "linux", target_os = "android", target_vendor = "apple"))]
fn publish_directory(source: &Path, destination: &Path) -> io::Result<()> {
    use rustix::fs::{renameat_with, RenameFlags, CWD};
    let result = renameat_with(CWD, source, CWD, destination, RenameFlags::NOREPLACE);
    #[cfg(any(target_os = "linux", target_os = "android"))]
    if result == Err(rustix::io::Errno::INVAL) {
        #[cfg(target_os = "linux")]
        if shared_publish::is_9p(destination.parent().unwrap_or(Path::new(".")))? {
            return shared_publish::publish(source, destination);
        }
        return Err(io::Error::new(
            io::ErrorKind::Unsupported,
            "exclusive atomic directory rename rejected (EINVAL); the destination filesystem may not support RENAME_NOREPLACE; use a filesystem that supports it",
        ));
    }
    Ok(result?)
}

#[cfg(not(any(
    windows,
    target_os = "linux",
    target_os = "android",
    target_vendor = "apple"
)))]
fn publish_directory(_source: &Path, _destination: &Path) -> io::Result<()> {
    Err(io::Error::new(
        io::ErrorKind::Unsupported,
        "exclusive directory rename unavailable",
    ))
}

fn publish(out: &Path, cases: &[(String, BTreeMap<String, String>)]) -> Result<(), String> {
    if out.exists() {
        return Err("output directory already exists".into());
    }
    let name = out.file_name().ok_or("invalid output directory")?;
    let parent = out
        .parent()
        .filter(|p| !p.as_os_str().is_empty())
        .unwrap_or(Path::new("."));
    let write_output = || -> io::Result<()> {
        fs::create_dir_all(parent)?;
        let parent = parent.canonicalize()?;
        let staging = tempfile::Builder::new()
            .prefix(".bb-export-")
            .tempdir_in(&parent)?;
        let tree = staging.path().join("export");
        fs::create_dir(&tree)?;
        for (id, files) in cases {
            let dir = tree.join(id);
            fs::create_dir(&dir)?;
            for (filename, content) in files {
                fs::write(dir.join(filename), content.as_bytes())?;
            }
        }
        publish_directory(&tree, &parent.join(name))
    };
    write_output().map_err(|err| {
        if out.exists() || err.kind() == io::ErrorKind::AlreadyExists {
            "output directory already exists".into()
        } else {
            format!("{}: {}", out.display(), err)
        }
    })
}

#[cfg(test)]
mod publication_tests {
    use super::*;
    use std::sync::{Arc, Barrier};

    fn cases() -> Vec<(String, BTreeMap<String, String>)> {
        vec![(
            "TC-001".into(),
            BTreeMap::from([("scenario.json".into(), "test".into())]),
        )]
    }

    #[test]
    fn concurrent_publication_preserves_winner_and_existing_output() {
        let root = tempfile::tempdir().unwrap();
        let destination = root.path().join("out");
        let barrier = Arc::new(Barrier::new(8));
        let threads: Vec<_> = (0..8)
            .map(|_| {
                let path = destination.clone();
                let barrier = barrier.clone();
                std::thread::spawn(move || {
                    barrier.wait();
                    publish(&path, &cases())
                })
            })
            .collect();
        let results: Vec<_> = threads.into_iter().map(|t| t.join().unwrap()).collect();
        assert_eq!(results.iter().filter(|r| r.is_ok()).count(), 1);
        assert!(results
            .iter()
            .filter_map(|r| r.as_ref().err())
            .all(|e| e.contains("already exists")));
        assert_eq!(
            fs::read(destination.join("TC-001/scenario.json")).unwrap(),
            b"test"
        );
        assert_eq!(fs::read_dir(root.path()).unwrap().count(), 1);
    }

    #[test]
    fn existing_empty_directory_and_failed_staging_are_preserved() {
        let root = tempfile::tempdir().unwrap();
        let destination = root.path().join("out");
        fs::create_dir(&destination).unwrap();
        assert!(publish(&destination, &cases()).is_err());
        assert_eq!(fs::read_dir(&destination).unwrap().count(), 0);
        let invalid = vec![(
            "TC-001".into(),
            BTreeMap::from([("missing/file".into(), "test".into())]),
        )];
        let failed = root.path().join("failed");
        assert!(publish(&failed, &invalid).is_err());
        assert!(!failed.exists());
        assert_eq!(fs::read_dir(root.path()).unwrap().count(), 1);
    }
}

fn main() -> ExitCode {
    let args = Args::parse();
    match export::export(
        &args.feature_spec,
        &args.manual_case_set,
        &args.binding,
        &args.out,
        &args.approved_binding_sha256,
    ) {
        Ok(ids) => {
            println!("{}", serde_json::json!(ids));
            ExitCode::SUCCESS
        }
        Err(reason) => {
            eprintln!("{reason}");
            ExitCode::from(2)
        }
    }
}
