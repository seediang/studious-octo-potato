"""Plugin management for xbt."""

import importlib
import json
import logging
from pathlib import Path
from typing import Optional

import pluggy
import yaml

from .hooks import XbtHookSpecs

logger = logging.getLogger(__name__)


def create_plugin_manager(config: Optional[dict] = None) -> pluggy.PluginManager:
    """
    Create and initialize the xbt plugin manager.

    Args:
        config: Optional plugin configuration dict with 'enabled_plugins'
                and/or 'disabled_plugins' lists.

    Returns:
        Initialized pluggy.PluginManager with hookspecs registered.
    """
    manager = pluggy.PluginManager("xbt")
    manager.add_hookspecs(XbtHookSpecs)

    config = config or {}

    # Load built-in plugins
    load_builtin_plugins(manager, config)

    # Load external plugins from entry points (optional)
    load_plugins_from_entrypoints(manager, config)

    return manager


def load_builtin_plugins(
    manager: pluggy.PluginManager, config: Optional[dict] = None
) -> None:
    """
    Auto-discover and load built-in plugins from xbt.plugins package.

    Args:
        manager: The pluggy.PluginManager instance.
        config: Optional plugin configuration dict.
    """
    config = config or {}

    try:
        # Import the plugins package
        from . import plugins as plugins_pkg

        # Get all modules in the plugins package
        plugins_dir = Path(plugins_pkg.__file__).parent
        for module_file in plugins_dir.glob("*.py"):
            if module_file.name == "__init__.py":
                continue

            module_name = module_file.stem
            if should_load_plugin(module_name, config):
                try:
                    # Dynamically import the plugin module
                    plugin_module = importlib.import_module(
                        f"xbt.plugins.{module_name}"
                    )
                    manager.register(plugin_module)
                    logger.debug(f"Loaded built-in plugin: {module_name}")
                except Exception as e:
                    logger.warning(f"Failed to load plugin {module_name}: {e}")
    except ImportError:
        logger.debug("No built-in plugins package found")


def load_plugins_from_entrypoints(
    manager: pluggy.PluginManager,
    config: Optional[dict] = None,
    group_name: str = "xbt.plugins",
) -> None:
    """
    Load plugins from entry points.

    Args:
        manager: The pluggy.PluginManager instance.
        config: Optional plugin configuration dict.
        group_name: Entry point group name to search.
    """
    config = config or {}

    try:
        from importlib.metadata import entry_points

        # Get all entry points in the xbt.plugins group
        discovered = entry_points()
        if hasattr(discovered, "select"):
            # Python 3.10+
            eps = discovered.select(group=group_name)
        else:
            # Python 3.9 and earlier
            eps = discovered.get(group_name, [])

        for ep in eps:
            plugin_name = ep.name
            if should_load_plugin(plugin_name, config):
                try:
                    plugin = ep.load()
                    manager.register(plugin)
                    logger.debug(f"Loaded entry point plugin: {plugin_name}")
                except Exception as e:
                    logger.warning(f"Failed to load entry point {plugin_name}: {e}")
    except ImportError:
        logger.debug("Entry point discovery not available")


def should_load_plugin(plugin_name: str, config: Optional[dict] = None) -> bool:
    """
    Determine if a plugin should be loaded based on config.

    Args:
        plugin_name: The name of the plugin.
        config: Optional plugin configuration dict.

    Returns:
        True if the plugin should be loaded, False otherwise.

    Logic:
    - If enabled_plugins list is provided: return True only if plugin_name is in list
    - Else if disabled_plugins list is provided: return True if plugin_name is NOT in list
    - Else: return True (load all plugins by default)
    """
    config = config or {}

    if "enabled_plugins" in config and config["enabled_plugins"]:
        return plugin_name in config["enabled_plugins"]

    if "disabled_plugins" in config and config["disabled_plugins"]:
        return plugin_name not in config["disabled_plugins"]

    return True


def load_config(project_dir: Optional[str] = None) -> dict:
    """
    Load plugin configuration from YAML files.

    Config files are searched in this order (later takes precedence):
    1. ~/.xbt.yml (home directory)
    2. xbt.yml (project root or project_dir)

    When both exist, project config completely replaces home config rather than merging.

    Args:
        project_dir: Optional project directory. If not provided, current directory is used.

    Returns:
        Merged configuration dictionary.
    """
    config = {}

    # Load home config
    home_config_path = Path.home() / ".xbt.yml"
    if home_config_path.exists():
        try:
            with open(home_config_path) as f:
                home_config = yaml.safe_load(f) or {}
                config.update(home_config)
                logger.debug(f"Loaded config from {home_config_path}")
        except Exception as e:
            logger.warning(f"Failed to load home config {home_config_path}: {e}")

    # Load project config (replaces home config if present)
    project_dir_path = Path(project_dir or ".")
    project_config_path = project_dir_path / "xbt.yml"
    if project_config_path.exists():
        try:
            with open(project_config_path) as f:
                project_config = yaml.safe_load(f) or {}
                # Replace entire config with project config
                config = project_config
                logger.debug(f"Loaded config from {project_config_path}")
        except Exception as e:
            logger.warning(f"Failed to load project config {project_config_path}: {e}")

    return config


def collect_artifacts(
    target_dir: Optional[str] = None, project_dir: Optional[str] = None
) -> dict:
    """
    Collect dbt artifacts from the target directory.

    Args:
        target_dir: Optional explicit target directory path.
        project_dir: Optional project directory (used if target_dir not specified).

    Returns:
        Dictionary mapping artifact names to artifact data dicts with 'path' and 'content'.
        Example: {
            'manifest': {'path': '/path/to/manifest.json', 'content': {...}},
            'run_results': {'path': '/path/to/run_results.json', 'content': {...}},
        }
    """
    artifacts = {}

    # Determine target directory
    if target_dir is None:
        target_dir = str(Path(project_dir or ".") / "target")

    target_path = Path(target_dir)
    if not target_path.exists():
        logger.debug(f"Target directory does not exist: {target_dir}")
        return artifacts

    # List of known artifacts to look for
    known_artifacts = [
        "manifest.json",
        "run_results.json",
        "catalog.json",
        "semantic_manifest.json",
        "sources.json",
    ]

    # Also scan for any other .json files
    all_json_files = set(f.name for f in target_path.glob("*.json"))

    for known_artifact in known_artifacts:
        artifact_key = known_artifact.replace(".json", "")
        artifact_path = target_path / known_artifact

        if artifact_path.exists():
            artifacts[artifact_key] = {
                "path": str(artifact_path),
                "content": _load_json_safe(artifact_path),
            }
        else:
            artifacts[artifact_key] = {
                "path": None,
                "content": None,
            }

    # Add any other JSON files found
    for json_file in all_json_files:
        if json_file not in known_artifacts:
            artifact_key = json_file.replace(".json", "")
            artifact_path = target_path / json_file
            artifacts[artifact_key] = {
                "path": str(artifact_path),
                "content": _load_json_safe(artifact_path),
            }

    return artifacts


def _load_json_safe(file_path: Path) -> Optional[dict]:
    """
    Safely load a JSON file.

    Args:
        file_path: Path to the JSON file.

    Returns:
        Parsed JSON content as a dict, or None if parsing fails.
    """
    try:
        with open(file_path) as f:
            return json.load(f)
    except Exception as e:
        logger.debug(f"Failed to parse JSON file {file_path}: {e}")
        return None


def get_loaded_plugins(manager: pluggy.PluginManager) -> list[str]:
    """
    Get a list of loaded plugin names from the plugin manager.

    Args:
        manager: The pluggy.PluginManager instance.

    Returns:
        List of plugin names (from __plugin_name__ attribute or module name).
    """
    plugin_names = []

    for plugin in manager.get_plugins():
        # Try to get the plugin name from __plugin_name__ attribute
        plugin_name = getattr(plugin, "__plugin_name__", None)
        if not plugin_name:
            # Fallback to module name
            plugin_name = getattr(plugin, "__name__", str(plugin))

        if plugin_name:
            plugin_names.append(plugin_name)

    return sorted(plugin_names)


def get_loaded_plugins_with_versions(
    manager: pluggy.PluginManager,
) -> dict[str, str]:
    """
    Get a dictionary of loaded plugin names with their versions.

    Args:
        manager: The pluggy.PluginManager instance.

    Returns:
        Dictionary mapping plugin names to versions.
        If a plugin doesn't have a version, "unknown" is used.
        Example: {"example_builtin": "0.1.2", "my_plugin": "1.0.0"}
    """
    plugins_with_versions = {}

    for plugin in manager.get_plugins():
        # Try to get the plugin name from __plugin_name__ attribute
        plugin_name = getattr(plugin, "__plugin_name__", None)
        if not plugin_name:
            # Fallback to module name
            plugin_name = getattr(plugin, "__name__", str(plugin))

        if plugin_name:
            # Try to get version from __plugin_version__ attribute
            version = getattr(plugin, "__plugin_version__", "unknown")
            plugins_with_versions[plugin_name] = version

    # Return sorted by name
    return dict(sorted(plugins_with_versions.items()))
