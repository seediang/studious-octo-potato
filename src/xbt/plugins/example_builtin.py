"""Example built-in plugin for xbt."""

import logging

import pluggy

logger = logging.getLogger(__name__)

__plugin_name__ = "example_builtin"

hookimpl = pluggy.HookimplMarker("xbt")


@hookimpl
def before_dbt(command_args: list[str], context: dict) -> None:
    """Example before_dbt hook."""
    project_name = context.get("project_name", "unknown")
    logger.info(f"[xbt-builtin] Running dbt for project: {project_name}")


@hookimpl
def after_dbt(result, artifacts: dict, context: dict) -> None:
    """Example after_dbt hook."""
    project_name = context.get("project_name", "unknown")
    logger.info(
        f"[xbt-builtin] dbt completed with exit code: {result.returncode} "
        f"(project: {project_name})"
    )
