"""Lab profile: equipment paths, printer, process, filaments."""

import os
import tomllib
from pathlib import Path

_REPO_PROFILE = Path(__file__).resolve().parents[2] / "lab" / "profile.toml"
_PACKAGED_PROFILE = Path(__file__).parent / "_lab" / "profile.toml"


def profile_path():
    if "HWKIT_LAB" in os.environ:
        return Path(os.environ["HWKIT_LAB"])
    return _REPO_PROFILE if _REPO_PROFILE.exists() else _PACKAGED_PROFILE


def load():
    return tomllib.loads(profile_path().read_text())


def filament_index(lab, role):
    """Filament number (from 1) of a role."""
    for i, f in enumerate(lab["filaments"], start=1):
        if f["role"] == role:
            return i
    raise KeyError(f"no filament with role {role} in {profile_path()}")
