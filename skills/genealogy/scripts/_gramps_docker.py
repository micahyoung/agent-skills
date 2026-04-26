"""Shared Docker invocation helper for Gramps scripts."""

import subprocess
import sys

DOCKER_IMAGE = "ghcr.io/gramps-project/grampsweb:latest"
TREE_NAME = "tmp_tree"


def run_gramps(shell_script: str, input_dir: str) -> subprocess.CompletedProcess:
    """Run a bash script inside the Gramps Docker container with /data mounted to input_dir."""
    docker_cmd = [
        "docker", "run", "--rm",
        "-v", f"{input_dir}:/data",
        "-w", "/data",
        "--entrypoint", "",
        DOCKER_IMAGE,
        "bash", "-c", shell_script,
    ]
    return subprocess.run(docker_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def run_gramps_or_exit(shell_script: str, input_dir: str, error_msg: str) -> str:
    """Run a Gramps Docker command and exit with an error message if it fails. Returns stdout."""
    result = run_gramps(shell_script, input_dir)
    if result.returncode != 0:
        print(result.stdout, file=sys.stderr)
        print(f"Error: {error_msg}", file=sys.stderr)
        sys.exit(1)
    return result.stdout
