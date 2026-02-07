"""Example built-in plugin for xbt."""

import logging

import pluggy

from xbt.hooks import DbtContext

logger = logging.getLogger(__name__)

__plugin_name__ = "example_builtin"
__plugin_version__ = "0.1.0"

hookimpl = pluggy.HookimplMarker("xbt")


@hookimpl
def before_dbt(command_args: list[str], context: DbtContext) -> None:
    """Example before_dbt hook."""
    logger.info(f"[xbt-builtin] Running dbt for project: {context.project_name}")


@hookimpl
def after_dbt(result, artifacts: dict, context: DbtContext) -> None:
    """Example after_dbt hook."""
    logger.info(
        f"[xbt-builtin] dbt completed with exit code: {result.returncode} "
        f"(project: {context.project_name})"
    )
