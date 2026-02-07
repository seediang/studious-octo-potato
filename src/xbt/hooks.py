"""Pluggy hook specifications for xbt plugins."""

import subprocess
from typing import Optional

import pluggy
from pydantic import BaseModel, Field

hookspec = pluggy.HookspecMarker("xbt")
hookimpl = pluggy.HookimplMarker("xbt")


class DbtContext(BaseModel):
    """Context information passed to xbt plugin hooks."""

    original_args: list[str] = Field(description="Original dbt command arguments")
    project_dir: str = Field(description="Directory containing dbt_project.yaml")
    project_name: Optional[str] = Field(
        default=None,
        description="Project name from dbt_project.yaml",
    )
    target_dir: Optional[str] = Field(
        default=None,
        description="dbt target directory (--target-dir or default)",
    )
    cwd: str = Field(description="Current working directory")


class XbtHookSpecs:
    """Hook specifications for xbt plugins."""

    @hookspec
    def before_dbt(
        self, command_args: list[str], context: DbtContext
    ) -> Optional[list[str]]:
        """
        Hook called before dbt is executed.

        Args:
            command_args: The dbt command arguments passed to xbt.
            context: DbtContext object containing:
                - original_args: Original parsed dbt args
                - project_dir: Directory with dbt_project.yaml
                - project_name: Project name from dbt_project.yaml (or None)
                - target_dir: dbt target directory
                - cwd: Current working directory

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
        context: DbtContext,
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
            context: DbtContext object with same fields as in before_dbt.

        No return value expected.

        Plugins can use this hook to:
        - Inspect dbt results and artifacts
        - Post-process dbt outputs
        - Send results to external systems
        - Generate reports or summaries
        """
