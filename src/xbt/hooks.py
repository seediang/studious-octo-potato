"""Pluggy hook specifications for xbt plugins."""

import subprocess
from typing import Optional

import pluggy

hookspec = pluggy.HookspecMarker("xbt")
hookimpl = pluggy.HookimplMarker("xbt")


class XbtHookSpecs:
    """Hook specifications for xbt plugins."""

    @hookspec
    def before_dbt(self, command_args: list[str], context: dict) -> Optional[list[str]]:
        """
        Hook called before dbt is executed.

        Args:
            command_args: The dbt command arguments passed to xbt.
            context: Dictionary containing:
                - original_args: list[str] - original parsed dbt args
                - project_dir: str - directory containing dbt_project.yaml
                - project_name: str | None - name from dbt_project.yaml
                - target_dir: str | None - dbt target directory (--target-dir or default)
                - cwd: str - current working directory

        Returns:
            Modified command_args (list[str]) to use instead of original args,
            or None to use the original args unchanged.

        Plugins can use this hook to:
        - Log or analyze the dbt project being executed
        - Modify dbt command arguments before execution
        - Perform pre-execution validation or setup
        """

    @hookspec
    def after_dbt(
        self,
        result: subprocess.CompletedProcess,
        artifacts: dict,
        context: dict,
    ) -> None:
        """
        Hook called after dbt has executed.

        Args:
            result: subprocess.CompletedProcess from dbt execution
                - returncode: int - exit code
                - stdout: str - output (if captured)
                - stderr: str - errors (if captured)
            artifacts: Dictionary mapping artifact names to artifact data.
                Keys may include: manifest, run_results, catalog, semantic_manifest,
                sources, and other .json files found in target directory.
                Each value is a dict with:
                - path: str | None - file path to artifact
                - content: dict | None - parsed JSON content (None if parse failed or file missing)
            context: Same dict as in before_dbt.

        No return value expected.

        Plugins can use this hook to:
        - Inspect dbt results and artifacts
        - Post-process dbt outputs
        - Send results to external systems
        - Generate reports or summaries
        """
