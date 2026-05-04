"""Shared Gramps invocation helper for genealogy scripts."""

import os
import shutil
import subprocess

TREE_NAME = "tmp_tree"

#: Candidate paths for a local Gramps binary, checked in order.
_NATIVE_PATHS = (
    "/Applications/Gramps.app/Contents/MacOS/Gramps",
    "gramps",   # resolves via shutil.which
)


def _find_gramps_binary() -> str | None:
    for path in _NATIVE_PATHS:
        if path.startswith("/"):
            if os.path.isfile(path) and os.access(path, os.X_OK):
                return path
        else:
            resolved = shutil.which(path)
            if resolved:
                return resolved
    return None


def find_gramps_app_resources() -> tuple[str, str] | None:
    """Return (lib_dir, site_packages_dir) for the macOS Gramps app bundle, or None."""
    app_binary = "/Applications/Gramps.app/Contents/MacOS/Gramps"
    if not (os.path.isfile(app_binary) and os.access(app_binary, os.X_OK)):
        return None
    resources = os.path.join(os.path.dirname(app_binary), "..", "Resources")
    lib_dir = os.path.join(resources, "lib")
    sp_dir = os.path.join(lib_dir, "python3.13", "site-packages")
    if os.path.isdir(sp_dir):
        return lib_dir, sp_dir
    return None


def run_gramps(shell_script: str, input_dir: str) -> subprocess.CompletedProcess:
    """Run a bash script using the native Gramps binary."""
    native_binary = _find_gramps_binary()
    if not native_binary:
        raise RuntimeError("Gramps not found. Install Gramps natively.")
    script = f'GRAMPS_WORK_DIR="{input_dir}"\n'
    script += shell_script.replace("gramps ", f"{native_binary} ")
    return subprocess.run(
        ["bash", "-c", script],
        cwd=input_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def remove_family_tree(tree_name: str) -> None:
    """Remove a Gramps family tree if it exists (best effort, silent on failure)."""
    native_binary = _find_gramps_binary()
    if not native_binary:
        return
    try:
        subprocess.run(
            [native_binary, "-y", "-r", tree_name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass
