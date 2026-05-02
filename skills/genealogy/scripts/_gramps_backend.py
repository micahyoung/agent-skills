"""Shared Gramps invocation helper for genealogy scripts.

Prefers a local Gramps install and falls back to Docker.
"""

import os
import shutil
import subprocess
import sys

DOCKER_IMAGE = "ghcr.io/gramps-project/grampsweb:latest"
TREE_NAME = "tmp_tree"

#: Candidate paths for a local Gramps binary, checked in order.
_NATIVE_PATHS = (
    "/Applications/Gramps.app/Contents/MacOS/Gramps",
    "gramps",   # resolves via shutil.which
)


def _find_gramps_binary() -> str | None:
    if os.environ.get("USE_GRAMPS_DOCKER"):
        return None
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


def run_gramps(shell_script: str, input_dir: str | None = None) -> subprocess.CompletedProcess:
    """Run a bash script using Gramps natively if available, otherwise via Docker."""
    native_binary = _find_gramps_binary()
    if native_binary:
        script = shell_script.replace("gramps ", f"{native_binary} ")
        if input_dir:
            script = script.replace("/data/", f"{input_dir}/")
        return subprocess.run(
            ["bash", "-c", script],
            cwd=input_dir or None,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

    docker_cmd = [
        "docker", "run", "--rm",
        *((["-v", f"{input_dir}:/data", "-w", "/data"]) if input_dir else []),
        "--entrypoint", "",
        DOCKER_IMAGE,
        "bash", "-c", shell_script,
    ]
    return subprocess.run(docker_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def run_gramps_or_exit(shell_script: str, input_dir: str, error_msg: str) -> str:
    """Run a Gramps command and exit with an error message if it fails. Returns stdout."""
    result = run_gramps(shell_script, input_dir)
    if result.returncode != 0:
        print(result.stdout, file=sys.stderr)
        print(f"Error: {error_msg}", file=sys.stderr)
        sys.exit(1)
    return result.stdout


def remove_family_tree(tree_name: str) -> None:
    """Remove a Gramps family tree if it exists (best effort, silent on failure)."""
    try:
        run_gramps(f"gramps -y -r {tree_name} 2>/dev/null || true")
    except Exception:
        pass
