//! 9p lacks Linux RENAME_NOREPLACE. Reserve the output with mkdir, then
//! populate it through directory handles. Readers can observe partial output.
use rustix::fs::{fstat, mkdirat, openat, statat, statfs, unlinkat, AtFlags, Mode, OFlags, CWD};
use std::fs::{self, File};
use std::io::{self, Write};
use std::path::{Path, PathBuf};

pub fn is_9p(parent: &Path) -> io::Result<bool> {
    Ok(statfs(parent)?.f_type as u64 == 0x0102_1997)
}

struct Created {
    parent: File,
    name: PathBuf,
    handle: File,
    directory: bool,
}

fn open_dir(parent: &File, name: &Path) -> io::Result<File> {
    Ok(openat(
        parent,
        name,
        OFlags::RDONLY | OFlags::DIRECTORY | OFlags::NOFOLLOW | OFlags::CLOEXEC,
        Mode::empty(),
    )?
    .into())
}

fn remember(
    created: &mut Vec<Created>,
    parent: &File,
    name: &Path,
    handle: &File,
    directory: bool,
) -> io::Result<()> {
    created.push(Created {
        parent: parent.try_clone()?,
        name: name.into(),
        handle: handle.try_clone()?,
        directory,
    });
    Ok(())
}

fn populate(source: &Path, destination: &File, created: &mut Vec<Created>) -> io::Result<()> {
    for item in fs::read_dir(source)? {
        let item = item?;
        let name = PathBuf::from(item.file_name());
        if item.file_type()?.is_dir() {
            mkdirat(destination, &name, Mode::from_raw_mode(0o777))?;
            let child = open_dir(destination, &name)?;
            remember(created, destination, &name, &child, true)?;
            populate(&item.path(), &child, created)?;
        } else {
            let fd = openat(
                destination,
                &name,
                OFlags::WRONLY | OFlags::CREATE | OFlags::EXCL | OFlags::NOFOLLOW | OFlags::CLOEXEC,
                Mode::from_raw_mode(0o666),
            )?;
            let mut file: File = fd.into();
            remember(created, destination, &name, &file, false)?;
            file.write_all(&fs::read(item.path())?)?;
        }
    }
    Ok(())
}

pub fn publish(source: &Path, destination: &Path) -> io::Result<()> {
    let parent_path = destination.parent().unwrap_or(Path::new("."));
    let name = Path::new(
        destination
            .file_name()
            .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidInput, "invalid destination"))?,
    );
    let parent: File = openat(
        CWD,
        parent_path,
        OFlags::RDONLY | OFlags::DIRECTORY | OFlags::CLOEXEC,
        Mode::empty(),
    )?
    .into();
    mkdirat(&parent, name, Mode::from_raw_mode(0o777))?;
    let root = open_dir(&parent, name)?;
    let mut created = Vec::new();
    remember(&mut created, &parent, name, &root, true)?;
    let result = populate(source, &root, &mut created);
    if result.is_err() {
        for item in created.iter().rev() {
            // Never remove an entry whose identity can no longer be confirmed.
            if let (Ok(opened), Ok(current)) = (
                fstat(&item.handle),
                statat(&item.parent, &item.name, AtFlags::SYMLINK_NOFOLLOW),
            ) {
                if opened.st_dev == current.st_dev && opened.st_ino == current.st_ino {
                    let flags = if item.directory {
                        AtFlags::REMOVEDIR
                    } else {
                        AtFlags::empty()
                    };
                    let _ = unlinkat(&item.parent, &item.name, flags);
                }
            }
        }
    }
    result
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn failure_cleans_own_output_and_existing_symlink_is_preserved() {
        use std::os::unix::fs::symlink;
        let root = tempfile::tempdir().unwrap();
        let source = root.path().join("source");
        fs::create_dir(&source).unwrap();
        symlink("missing", source.join("broken")).unwrap();
        let destination = root.path().join("out");
        assert!(publish(&source, &destination).is_err());
        assert!(!destination.exists());
        let target = root.path().join("target");
        fs::create_dir(&target).unwrap();
        symlink(&target, &destination).unwrap();
        assert!(publish(&source, &destination).is_err());
        assert!(fs::symlink_metadata(&destination)
            .unwrap()
            .file_type()
            .is_symlink());
        assert_eq!(fs::read_dir(&target).unwrap().count(), 0);
    }
}
