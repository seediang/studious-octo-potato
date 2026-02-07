"""Command-line interface for xbt - dbt passthrough wrapper."""

import logging
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

import yaml

from . import __version__
from .plugin_manager import (
    collect_artifacts,
    create_plugin_manager,
    get_loaded_plugins,
    load_config,
)

logger = logging.getLogger(__name__)


def main() -> None:
    """Entry point for the xbt CLI."""
    # Configure logging
    logging.basicConfig(level=logging.INFO)

    # Get all remaining arguments
    argv = sys.argv[1:]

    # Handle --version flag (print xbt version, dbt version, and loaded plugins)
    if "--version" in argv:
        print(f"xbt: {__version__}")
        print()

        # Load and display plugins
        try:
            config = load_config()
            plugin_manager = create_plugin_manager(config)
            plugins = get_loaded_plugins(plugin_manager)

            if plugins:
                print("xbt-plugins:")
                for plugin_name in plugins:
                    print(f"  - {plugin_name}")
            else:
                print("xbt-plugins: none")

            print()
        except Exception as e:
            logger.debug(f"Failed to load plugins for version display: {e}")

        # Print dbt version
        run_dbt(["--version"])
        return

    # Determine project directory and load config
    project_dir = get_project_dir(argv)
    config = load_config(project_dir)

    # Load project name from dbt_project.yaml
    project_name = load_dbt_project_name(project_dir)

    # Build context for plugins
    context = {
        "original_args": argv.copy() if argv else [],
        "project_dir": project_dir,
        "project_name": project_name,
        "target_dir": get_target_dir(argv, project_dir),
        "cwd": str(Path.cwd()),
    }

    # Create and setup plugin manager
    plugin_manager = create_plugin_manager(config)

    # Call before_dbt hooks
    dbt_args = argv if argv else []
    hook_result = plugin_manager.hook.before_dbt(command_args=dbt_args, context=context)

    # Check if any plugin returned modified args
    modified_args = None
    for result in hook_result:
        if result is not None:
            modified_args = result
            break

    # Use modified args if provided, otherwise use original
    dbt_args = modified_args if modified_args is not None else dbt_args

    # If no arguments, run dbt with no args
    if not dbt_args:
        dbt_args = []

    # Run dbt
    result = run_dbt(dbt_args)

    # Collect artifacts
    artifacts = collect_artifacts(context["target_dir"], project_dir)

    # Call after_dbt hooks
    plugin_manager.hook.after_dbt(result=result, artifacts=artifacts, context=context)

    # Exit with dbt's exit code
    sys.exit(result.returncode)


def run_dbt(dbt_args: list[str]) -> subprocess.CompletedProcess:
    """
    Run dbt with the given arguments.

    Streams stdout and stderr to console in real-time.

    Args:
        dbt_args: Arguments to pass to dbt.

    Returns:
        subprocess.CompletedProcess with the result.
    """
    # Find dbt executable
    dbt_exe = shutil.which("dbt")
    if not dbt_exe:
        print("Error: dbt not found in PATH", file=sys.stderr)
        sys.exit(1)

    # Build command
    cmd = [dbt_exe] + dbt_args

    logger.debug(f"Running: {' '.join(cmd)}")

    # Run with streaming output
    process = subprocess.Popen(
        cmd,
        stdout=sys.stdout,
        stderr=sys.stderr,
        text=True,
    )

    process.wait()

    # Return as CompletedProcess for consistency
    return subprocess.CompletedProcess(
        args=cmd,
        returncode=process.returncode,
    )


def get_project_dir(dbt_args: list[str]) -> str:
    """
    Determine the dbt project directory.

    Checks for --project-dir flag in dbt args, otherwise uses current directory.

    Args:
        dbt_args: Arguments passed to xbt.

    Returns:
        Path to the project directory.
    """
    # Look for --project-dir in args
    for i, arg in enumerate(dbt_args):
        if arg == "--project-dir" and i + 1 < len(dbt_args):
            return dbt_args[i + 1]

    return str(Path.cwd())


def load_dbt_project_name(project_dir: str) -> Optional[str]:
    """
    Load the dbt project name from dbt_project.yaml.

    Args:
        project_dir: Path to the project directory.

    Returns:
        Project name or None if file not found or cannot be parsed.
    """
    try:
        project_file = Path(project_dir) / "dbt_project.yaml"
        if not project_file.exists():
            logger.debug(f"dbt_project.yaml not found in {project_dir}")
            return None

        with open(project_file) as f:
            project_data = yaml.safe_load(f)
            if project_data and isinstance(project_data, dict):
                return project_data.get("name")
    except Exception as e:
        logger.warning(f"Failed to load dbt_project.yaml from {project_dir}: {e}")

    return None


def get_target_dir(dbt_args: list[str], project_dir: str) -> Optional[str]:
    """
    Determine the dbt target directory.

    Checks for --target-dir flag in dbt args, otherwise uses project_dir/target.

    Args:
        dbt_args: Arguments passed to xbt.
        project_dir: Path to the project directory.

    Returns:
        Path to the target directory or None if determination fails.
    """
    # Look for --target-dir in args
    for i, arg in enumerate(dbt_args):
        if arg == "--target-dir" and i + 1 < len(dbt_args):
            return dbt_args[i + 1]

    # Default to project_dir/target
    return str(Path(project_dir) / "target")


if __name__ == "__main__":
    main()
