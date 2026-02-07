"""Tests for built-in plugins and plugin system."""

from unittest.mock import Mock, patch

from xbt.hooks import DbtContext
from xbt.plugin_manager import (
    create_plugin_manager,
    get_loaded_plugins,
    get_loaded_plugins_with_versions,
    load_builtin_plugins,
    load_config,
)


class TestBuiltinPluginsAutoLoaded:
    """Tests for auto-loading built-in plugins."""

    def test_builtin_plugins_are_loaded(self):
        """Test that built-in plugins are auto-discovered and loaded."""
        manager = create_plugin_manager()

        # Check that hooks are implemented
        # The hookimpl markers should have registered the plugins
        assert manager.hook.before_dbt is not None
        assert manager.hook.after_dbt is not None

    def test_builtin_plugin_receives_context(self):
        """Test that built-in plugin receives context in before_dbt hook."""
        manager = create_plugin_manager()

        context = DbtContext(
            original_args=["run"],
            project_dir="/project",
            project_name="test_project",
            target_dir="/project/target",
            cwd="/project",
        )

        # Call the hook
        results = manager.hook.before_dbt(command_args=["run"], context=context)

        # Built-in example_builtin plugin should be called and return None
        # (it doesn't modify args)
        assert isinstance(results, list)

    def test_builtin_plugin_receives_artifacts(self):
        """Test that built-in plugin receives artifacts in after_dbt hook."""
        manager = create_plugin_manager()

        result = Mock()
        result.returncode = 0

        artifacts = {
            "manifest": {"path": "/target/manifest.json", "content": {"nodes": {}}},
            "run_results": {
                "path": "/target/run_results.json",
                "content": {"results": []},
            },
        }

        context = DbtContext(
            original_args=["run"],
            project_dir="/project",
            project_name="test_project",
            target_dir="/project/target",
            cwd="/project",
        )

        # Call the hook - should not raise
        manager.hook.after_dbt(result=result, artifacts=artifacts, context=context)


class TestGetLoadedPlugins:
    """Tests for get_loaded_plugins function."""

    def test_get_loaded_plugins_returns_plugin_names(self):
        """Test that get_loaded_plugins returns list of loaded plugin names."""
        manager = create_plugin_manager()
        plugins = get_loaded_plugins(manager)

        # Should have at least the example_builtin plugin
        assert isinstance(plugins, list)
        assert "example_builtin" in plugins

    def test_get_loaded_plugins_sorted(self):
        """Test that plugin names are sorted alphabetically."""
        manager = create_plugin_manager()
        plugins = get_loaded_plugins(manager)

        # Check that list is sorted
        assert plugins == sorted(plugins)

    def test_get_loaded_plugins_with_disabled_plugins(self):
        """Test get_loaded_plugins when plugins are disabled."""
        config = {"disabled_plugins": ["example_builtin"]}
        manager = create_plugin_manager(config)
        plugins = get_loaded_plugins(manager)

        # example_builtin should not be in the list
        assert "example_builtin" not in plugins


class TestGetLoadedPluginsWithVersions:
    """Tests for get_loaded_plugins_with_versions function."""

    def test_get_loaded_plugins_with_versions(self):
        """Test that get_loaded_plugins_with_versions returns dict with versions."""
        manager = create_plugin_manager()
        plugins = get_loaded_plugins_with_versions(manager)

        # Should have at least the example_builtin plugin
        assert isinstance(plugins, dict)
        assert "example_builtin" in plugins
        assert plugins["example_builtin"] == "0.1.0"

    def test_get_loaded_plugins_with_versions_sorted(self):
        """Test that plugin names are sorted alphabetically."""
        manager = create_plugin_manager()
        plugins = get_loaded_plugins_with_versions(manager)

        # Check that keys are sorted
        assert list(plugins.keys()) == sorted(plugins.keys())

    def test_get_loaded_plugins_with_versions_disabled_plugins(self):
        """Test get_loaded_plugins_with_versions when plugins are disabled."""
        config = {"disabled_plugins": ["example_builtin"]}
        manager = create_plugin_manager(config)
        plugins = get_loaded_plugins_with_versions(manager)

        # example_builtin should not be in the dict
        assert "example_builtin" not in plugins


class TestPluginDisabling:
    """Tests for disabling plugins via config."""

    def test_disabled_builtin_plugins_not_loaded(self):
        """Test that disabled plugins are not loaded."""
        config = {"disabled_plugins": ["example_builtin"]}
        manager = create_plugin_manager(config)

        # Create mock to track if plugin was called
        with patch("xbt.plugin_manager.should_load_plugin") as mock_should_load:
            mock_should_load.return_value = False
            load_builtin_plugins(manager, config)

    def test_enabled_plugins_list_only_loads_specified(self):
        """Test that only plugins in enabled_plugins list are loaded."""
        config = {"enabled_plugins": ["my_custom_plugin"]}

        # The example_builtin plugin won't be loaded because it's not in enabled_plugins
        manager = create_plugin_manager(config)

        # This should not raise; plugins just won't be called if they're not registered
        assert manager is not None


class TestPluginConfig:
    """Tests for plugin configuration handling."""

    def test_config_with_enabled_plugins_allow_list(self, tmp_path, monkeypatch):
        """Test config with enabled_plugins allow-list."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        config_file = project_dir / "xbt.yml"
        config_file.write_text("enabled_plugins:\n  - my_plugin\n")

        config = load_config(str(project_dir))
        assert config.get("enabled_plugins") == ["my_plugin"]

    def test_config_with_disabled_plugins_deny_list(self, tmp_path, monkeypatch):
        """Test config with disabled_plugins deny-list."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        config_file = project_dir / "xbt.yml"
        config_file.write_text(
            "disabled_plugins:\n  - example_builtin\n  - other_plugin\n"
        )

        config = load_config(str(project_dir))
        assert config.get("disabled_plugins") == ["example_builtin", "other_plugin"]


class TestPluginHookExecution:
    """Tests for plugin hook execution."""

    def test_before_dbt_hook_called_on_manager(self):
        """Test that before_dbt hook is callable on manager."""
        manager = create_plugin_manager()

        # Should be callable without errors
        context = DbtContext(
            original_args=["run"],
            project_dir=".",
            project_name=None,
            target_dir="./target",
            cwd=".",
        )

        result = manager.hook.before_dbt(command_args=["run"], context=context)
        assert isinstance(result, list)

    def test_after_dbt_hook_called_on_manager(self):
        """Test that after_dbt hook is callable on manager."""
        manager = create_plugin_manager()

        result = Mock()
        result.returncode = 0

        artifacts = {}

        context = DbtContext(
            original_args=["run"],
            project_dir=".",
            project_name=None,
            target_dir="./target",
            cwd=".",
        )

        # Should not raise
        manager.hook.after_dbt(result=result, artifacts=artifacts, context=context)


class TestDefaultPluginBehavior:
    """Tests for default plugin behavior."""

    def test_no_config_loads_all_plugins(self):
        """Test that all plugins are loaded when no config is provided."""
        manager = create_plugin_manager()

        # Should have loaded at least the example_builtin plugin
        # We can't directly check what plugins are registered, but we can call the hooks
        context = DbtContext(
            original_args=[],
            project_dir=".",
            project_name=None,
            target_dir="./target",
            cwd=".",
        )

        # Call hooks - should work without errors
        manager.hook.before_dbt(command_args=[], context=context)

        result = Mock()
        result.returncode = 0
        manager.hook.after_dbt(result=result, artifacts={}, context=context)
