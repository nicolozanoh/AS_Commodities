from pathlib import Path


def get_project_root() -> Path:
    """Returns the absolute path to the project root (v1.0.1 directory)."""
    return Path(__file__).resolve().parents[2]


def get_current_version() -> str:
    """Returns the version folder name (e.g. 'v1.0.1')."""
    return get_project_root().name
