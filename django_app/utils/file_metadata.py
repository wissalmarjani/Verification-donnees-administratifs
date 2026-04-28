from pathlib import Path


def build_file_metadata(path: Path) -> dict:
    """
    Extract basic file metadata to support traceability and analysis audit.
    """

    stat = path.stat()
    return {
        "name": path.name,
        "path": str(path),
        "size_bytes": stat.st_size,
        "suffix": path.suffix.lower(),
    }
