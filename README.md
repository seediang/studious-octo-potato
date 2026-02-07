# xbt - Extended dbt CLI Wrapper

xbt is a Python CLI tool that acts as a wrapper around dbt, allowing you to passthrough dbt commands while providing a plugin system for extending functionality before and after dbt execution.

## Features

- **dbt Passthrough**: Pass any dbt command and arguments directly through xbt
- **Plugin System**: Extensible plugin architecture using pluggy for pre- and post-dbt hooks
- **Artifact Inspection**: Plugins receive access to dbt artifacts (manifest, run_results, catalog, etc.)
- **Project Awareness**: Plugins receive dbt project information (name, directory)
- **Plugin Configuration**: Enable/disable plugins via YAML configuration
- **Built-in Plugins**: Includes example built-in plugins that can be easily extended

## Installation

```bash
pip install -e .
```

## Usage

### Basic Commands

Run dbt with xbt (passthrough):

```bash
# Run dbt with no arguments
xbt

# Run a dbt command
xbt run
xbt run --models +tag:daily

# Other dbt commands work too
xbt test
xbt docs generate
```

### Version Information

Check both xbt and dbt versions:

```bash
xbt --version
```

This will print:
1. The xbt version
2. The output of `dbt --version`

### Configuration

xbt supports YAML configuration files to control plugin loading and behavior.

#### Configuration File Locations

Configuration files are searched in this order (later takes precedence):

1. `~/.xbt.yml` - user home directory (applies to all projects)
2. `xbt.yml` - project root (project-specific configuration)

#### Plugin Management

Control which plugins are loaded using `enabled_plugins` (allow-list) or `disabled_plugins` (deny-list).

**Example: Disable specific plugins** (`~/.xbt.yml`):

```yaml
disabled_plugins:
  - example_builtin
  - some_external_plugin
```

**Example: Enable only specific plugins** (`xbt.yml`):

```yaml
enabled_plugins:
  - my_custom_plugin
  - logging_plugin
```

When `enabled_plugins` is specified, only those plugins will be loaded (and `disabled_plugins` is ignored).

When `enabled_plugins` is not specified, all plugins are loaded except those in `disabled_plugins`.

## Plugin Development

### Creating a Plugin

Plugins hook into xbt's execution at two points:

1. **before_dbt**: Called before dbt is executed
2. **after_dbt**: Called after dbt completes with access to artifacts

#### Example Plugin

Create a file `my_xbt_plugin.py`:

```python
import pluggy

__plugin_name__ = "my_custom_plugin"

hookimpl = pluggy.HookimplMarker("xbt")

@hookimpl
def before_dbt(command_args: list[str], context: dict) -> list[str] | None:
    """
    Hook called before dbt execution.
    
    Args:
        command_args: The dbt command arguments
        context: Dict with keys:
            - original_args: list - parsed dbt args
            - project_dir: str - directory containing dbt_project.yaml
            - project_name: str | None - project name from dbt_project.yaml
            - target_dir: str | None - dbt target directory
            - cwd: str - current working directory
    
    Returns:
        Modified command_args list, or None to use original args
    """
    project_name = context.get("project_name", "unknown")
    print(f"Running dbt for project: {project_name}")
    
    # Optionally modify arguments
    # return command_args + ["--select", "+tag:upstream"]
    
    # Or use original arguments
    return None

@hookimpl
def after_dbt(result, artifacts: dict, context: dict) -> None:
    """
    Hook called after dbt execution.
    
    Args:
        result: subprocess.CompletedProcess with:
            - returncode: int - dbt exit code
            - stdout: str - output (if captured)
            - stderr: str - errors (if captured)
        artifacts: Dict of dbt artifacts with keys like:
            - manifest: {"path": str, "content": dict}
            - run_results: {"path": str, "content": dict}
            - catalog: {"path": str, "content": dict}
            - semantic_manifest: {"path": str, "content": dict}
            - sources: {"path": str, "content": dict}
            - other *.json files in target/
            Each artifact value is {"path": str | None, "content": dict | None}
        context: Same context dict from before_dbt
    """
    if result.returncode == 0:
        # Process successful artifacts
        if "run_results" in artifacts:
            run_results = artifacts["run_results"]["content"]
            if run_results:
                print(f"dbt completed successfully")
                print(f"Total models: {len(run_results.get('results', []))}")
    else:
        # Handle failure
        print(f"dbt failed with exit code {result.returncode}")
```

### Artifact Access

Plugins receive access to dbt artifacts in the `after_dbt` hook. Each artifact entry has:

- `path`: File path to the artifact (or None if missing)
- `content`: Parsed JSON content (or None if missing or parse failed)

Plugins can choose to use the parsed content or reload the file:

```python
@hookimpl
def after_dbt(result, artifacts: dict, context: dict) -> None:
    # Use parsed content
    manifest = artifacts["manifest"]["content"]
    if manifest:
        nodes = manifest.get("nodes", {})
    
    # Or re-open the file if needed
    manifest_path = artifacts["manifest"]["path"]
    if manifest_path:
        with open(manifest_path) as f:
            manifest_data = json.load(f)
```

### Registering Plugins

#### Option 1: Built-in Plugins

Place your plugin in `src/xbt/plugins/`:

```bash
src/xbt/plugins/
  my_plugin.py
```

The plugin will be auto-discovered and loaded on xbt startup.

#### Option 2: Entry Points (External Packages)

Define an entry point in your `pyproject.toml`:

```toml
[project.entry-points."xbt.plugins"]
my_plugin = "my_package.my_plugin"
```

The entry point should point to a module (not a function) that implements the hooks.

#### Option 3: Manual Registration

Plugins can be manually registered by importing and registering them directly (less common, used for testing).

### Plugin Configuration

In `xbt.yml` or `~/.xbt.yml`:

```yaml
disabled_plugins:
  - my_plugin  # Use the value of __plugin_name__ from your plugin

enabled_plugins:
  - my_plugin  # Enable specific plugins only
```

## Built-in Plugins

### example_builtin

The `example_builtin` plugin demonstrates basic plugin functionality:

- Logs project name before dbt execution
- Logs exit code after dbt execution

Can be disabled via configuration:

```yaml
disabled_plugins:
  - example_builtin
```

## Development

### Running Tests

```bash
pytest
pytest -v
pytest tests/test_main.py -q
```

### Code Quality

```bash
ruff check .
ruff format .
```

## Architecture

```
xbt
├── main.py          # CLI entrypoint
├── hooks.py         # Pluggy hook specifications
├── plugins.py       # Plugin manager and utilities
└── plugins/         # Built-in plugins
    ├── __init__.py
    └── example_builtin.py
```

### Hook Execution Flow

1. User runs `xbt ...`
2. Parse arguments and determine project directory
3. Load configuration from `~/.xbt.yml` and/or `xbt.yml`
4. Create plugin manager and auto-load plugins
5. Call `before_dbt` hooks (plugins can modify arguments)
6. Execute dbt with (possibly modified) arguments
7. Collect dbt artifacts from target directory
8. Call `after_dbt` hooks (plugins can inspect artifacts)
9. Exit with dbt's exit code

## Context Dictionary

The `context` dict passed to plugin hooks contains:

```python
{
    "original_args": list[str],      # Original dbt arguments
    "project_dir": str,               # Directory with dbt_project.yaml
    "project_name": str | None,       # Project name from dbt_project.yaml
    "target_dir": str | None,         # dbt target directory
    "cwd": str,                       # Current working directory
}
```

## License

MIT
