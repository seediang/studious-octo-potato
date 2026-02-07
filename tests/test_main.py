"""Tests for xbt main module."""

import json
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from xbt.main import (
    get_project_dir,
    get_target_dir,
    load_dbt_project_name,
    main,
    run_dbt,
)
from xbt.plugin_manager import collect_artifacts, load_config, should_load_plugin


class TestGetProjectDir:
    """Tests for get_project_dir function."""

    def test_get_project_dir_from_flag(self):
        """Test extracting project dir from --project-dir flag."""
        dbt_args = ["run", "--project-dir", "/path/to/project"]
        result = get_project_dir(dbt_args)
        assert result == "/path/to/project"

    def test_get_project_dir_defaults_to_cwd(self):
        """Test that cwd is used when no --project-dir flag."""
        dbt_args = ["run", "--models", "+tag"]
        result = get_project_dir(dbt_args)
        assert result == str(Path.cwd())

    def test_get_project_dir_empty_args(self):
        """Test with empty args."""
        result = get_project_dir([])
        assert result == str(Path.cwd())

    def test_get_project_dir_flag_at_end(self):
        """Test --project-dir flag at end of args (no value)."""
        dbt_args = ["run", "--project-dir"]
        result = get_project_dir(dbt_args)
        assert result == str(Path.cwd())


class TestLoadDbtProjectName:
    """Tests for load_dbt_project_name function."""

    def test_load_dbt_project_name_success(self, tmp_path):
        """Test successfully loading project name from dbt_project.yaml."""
        project_file = tmp_path / "dbt_project.yaml"
        project_file.write_text("name: my_project\nversion: 1.0.0\n")

        result = load_dbt_project_name(str(tmp_path))
        assert result == "my_project"

    def test_load_dbt_project_name_missing_file(self, tmp_path):
        """Test when dbt_project.yaml is missing."""
        result = load_dbt_project_name(str(tmp_path))
        assert result is None

    def test_load_dbt_project_name_invalid_yaml(self, tmp_path):
        """Test with invalid YAML file."""
        project_file = tmp_path / "dbt_project.yaml"
        project_file.write_text("invalid: yaml: content:")

        result = load_dbt_project_name(str(tmp_path))
        # Should return None for invalid YAML
        assert result is None

    def test_load_dbt_project_name_no_name_field(self, tmp_path):
        """Test YAML file without 'name' field."""
        project_file = tmp_path / "dbt_project.yaml"
        project_file.write_text("version: 1.0.0\n")

        result = load_dbt_project_name(str(tmp_path))
        assert result is None


class TestGetTargetDir:
    """Tests for get_target_dir function."""

    def test_get_target_dir_from_flag(self):
        """Test extracting target dir from --target-dir flag."""
        dbt_args = ["run", "--target-dir", "/path/to/target"]
        result = get_target_dir(dbt_args, "/project")
        assert result == "/path/to/target"

    def test_get_target_dir_defaults_to_project_target(self):
        """Test that project/target is used when no --target-dir flag."""
        dbt_args = ["run"]
        result = get_target_dir(dbt_args, "/project")
        assert result == str(Path("/project") / "target")

    def test_get_target_dir_empty_args(self):
        """Test with empty args."""
        result = get_target_dir([], "/project")
        assert result == str(Path("/project") / "target")


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_config_from_home_directory(self, tmp_path, monkeypatch):
        """Test loading config from home directory."""
        home_dir = tmp_path / "home"
        home_dir.mkdir()
        config_file = home_dir / ".xbt.yml"
        config_file.write_text("disabled_plugins:\n  - example_builtin\n")

        monkeypatch.setattr(Path, "home", lambda: home_dir)

        result = load_config()
        assert result.get("disabled_plugins") == ["example_builtin"]

    def test_load_config_from_project_root(self, tmp_path, monkeypatch):
        """Test loading config from project root."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        config_file = project_dir / "xbt.yml"
        config_file.write_text("enabled_plugins:\n  - my_plugin\n")

        result = load_config(str(project_dir))
        assert result.get("enabled_plugins") == ["my_plugin"]

    def test_project_config_takes_precedence(self, tmp_path, monkeypatch):
        """Test that project config takes precedence over home config."""
        home_dir = tmp_path / "home"
        home_dir.mkdir()
        home_config = home_dir / ".xbt.yml"
        home_config.write_text("disabled_plugins:\n  - example_builtin\n")

        project_dir = tmp_path / "project"
        project_dir.mkdir()
        project_config = project_dir / "xbt.yml"
        project_config.write_text("enabled_plugins:\n  - my_plugin\n")

        monkeypatch.setattr(Path, "home", lambda: home_dir)

        result = load_config(str(project_dir))
        assert result.get("enabled_plugins") == ["my_plugin"]
        # Home config disabled_plugins should be overridden
        assert "disabled_plugins" not in result

    def test_load_config_no_files(self, tmp_path):
        """Test when no config files exist."""
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        result = load_config(str(project_dir))
        assert result == {}


class TestShouldLoadPlugin:
    """Tests for should_load_plugin function."""

    def test_all_plugins_enabled_by_default(self):
        """Test that all plugins are enabled when no config."""
        assert should_load_plugin("example_builtin", {}) is True
        assert should_load_plugin("my_plugin", {}) is True

    def test_disabled_plugins_are_skipped(self):
        """Test that plugins in disabled_plugins list are skipped."""
        config = {"disabled_plugins": ["example_builtin"]}
        assert should_load_plugin("example_builtin", config) is False
        assert should_load_plugin("my_plugin", config) is True

    def test_enabled_plugins_allow_list(self):
        """Test that only plugins in enabled_plugins list are loaded."""
        config = {"enabled_plugins": ["my_plugin"]}
        assert should_load_plugin("my_plugin", config) is True
        assert should_load_plugin("example_builtin", config) is False

    def test_enabled_plugins_takes_precedence(self):
        """Test that enabled_plugins takes precedence over disabled_plugins."""
        config = {
            "enabled_plugins": ["my_plugin"],
            "disabled_plugins": ["example_builtin"],
        }
        # enabled_plugins should take full precedence
        assert should_load_plugin("my_plugin", config) is True
        assert should_load_plugin("example_builtin", config) is False


class TestCollectArtifacts:
    """Tests for collect_artifacts function."""

    def test_collect_artifacts_manifest_and_run_results(self, tmp_path):
        """Test collecting manifest and run_results artifacts."""
        target_dir = tmp_path / "target"
        target_dir.mkdir()

        manifest = {"nodes": {}, "metadata": {}}
        run_results = {"results": [], "elapsed_time": 0.5}

        (target_dir / "manifest.json").write_text(json.dumps(manifest))
        (target_dir / "run_results.json").write_text(json.dumps(run_results))

        artifacts = collect_artifacts(str(target_dir))

        assert "manifest" in artifacts
        assert artifacts["manifest"]["content"] == manifest
        assert artifacts["manifest"]["path"] == str(target_dir / "manifest.json")

        assert "run_results" in artifacts
        assert artifacts["run_results"]["content"] == run_results
        assert artifacts["run_results"]["path"] == str(target_dir / "run_results.json")

    def test_collect_artifacts_missing_files(self, tmp_path):
        """Test that missing artifacts are represented with None."""
        target_dir = tmp_path / "target"
        target_dir.mkdir()

        artifacts = collect_artifacts(str(target_dir))

        assert "manifest" in artifacts
        assert artifacts["manifest"]["path"] is None
        assert artifacts["manifest"]["content"] is None

    def test_collect_artifacts_nonexistent_target_dir(self, tmp_path):
        """Test with non-existent target directory."""
        target_dir = tmp_path / "nonexistent"
        artifacts = collect_artifacts(str(target_dir))
        assert artifacts == {}

    def test_collect_artifacts_invalid_json(self, tmp_path):
        """Test with invalid JSON in artifact file."""
        target_dir = tmp_path / "target"
        target_dir.mkdir()

        (target_dir / "manifest.json").write_text("invalid json {")

        artifacts = collect_artifacts(str(target_dir))

        assert "manifest" in artifacts
        assert artifacts["manifest"]["path"] == str(target_dir / "manifest.json")
        assert artifacts["manifest"]["content"] is None

    def test_collect_artifacts_additional_json_files(self, tmp_path):
        """Test that additional JSON files are collected."""
        target_dir = tmp_path / "target"
        target_dir.mkdir()

        catalog = {"sources": {}}
        (target_dir / "catalog.json").write_text(json.dumps(catalog))
        (target_dir / "custom.json").write_text(json.dumps({"custom": "data"}))

        artifacts = collect_artifacts(str(target_dir))

        assert "catalog" in artifacts
        assert artifacts["catalog"]["content"] == catalog
        assert "custom" in artifacts
        assert artifacts["custom"]["content"] == {"custom": "data"}


class TestRunDbt:
    """Tests for run_dbt function."""

    @patch("xbt.main.shutil.which")
    @patch("xbt.main.subprocess.Popen")
    def test_run_dbt_passthrough_invokes_dbt(self, mock_popen, mock_which):
        """Test that run_dbt invokes dbt with correct arguments."""
        mock_which.return_value = "/usr/bin/dbt"
        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.wait.return_value = None
        mock_popen.return_value = mock_process

        result = run_dbt(["run", "--models", "+tag"])

        mock_popen.assert_called_once()
        call_args = mock_popen.call_args[0][0]
        assert call_args == ["/usr/bin/dbt", "run", "--models", "+tag"]
        assert result.returncode == 0

    @patch("xbt.main.shutil.which")
    @patch("xbt.main.subprocess.Popen")
    def test_run_dbt_empty_args(self, mock_popen, mock_which):
        """Test run_dbt with no arguments."""
        mock_which.return_value = "/usr/bin/dbt"
        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.wait.return_value = None
        mock_popen.return_value = mock_process

        run_dbt([])

        call_args = mock_popen.call_args[0][0]
        assert call_args == ["/usr/bin/dbt"]

    @patch("xbt.main.shutil.which")
    def test_run_dbt_not_found(self, mock_which):
        """Test error when dbt is not found."""
        mock_which.return_value = None

        with pytest.raises(SystemExit):
            run_dbt(["--version"])


class TestMain:
    """Integration tests for main function."""

    @patch("xbt.main.run_dbt")
    @patch("xbt.main.create_plugin_manager")
    def test_main_no_args_runs_dbt(self, mock_pm, mock_run_dbt, tmp_path, monkeypatch):
        """Test that xbt with no args runs dbt with no args."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_run_dbt.return_value = mock_result

        mock_manager = Mock()
        mock_manager.hook.before_dbt.return_value = []
        mock_manager.hook.after_dbt.return_value = None
        mock_pm.return_value = mock_manager

        monkeypatch.setattr(sys, "argv", ["xbt"])
        monkeypatch.chdir(tmp_path)

        with pytest.raises(SystemExit) as exc_info:
            main()

        mock_run_dbt.assert_called_once_with([])
        assert exc_info.value.code == 0

    @patch("xbt.main.run_dbt")
    @patch("xbt.main.create_plugin_manager")
    def test_main_passthrough_args(self, mock_pm, mock_run_dbt, tmp_path, monkeypatch):
        """Test that xbt passes through dbt arguments."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_run_dbt.return_value = mock_result

        mock_manager = Mock()
        mock_manager.hook.before_dbt.return_value = []
        mock_manager.hook.after_dbt.return_value = None
        mock_pm.return_value = mock_manager

        monkeypatch.setattr(sys, "argv", ["xbt", "run", "--models", "+tag"])
        monkeypatch.chdir(tmp_path)

        with pytest.raises(SystemExit) as exc_info:
            main()

        mock_run_dbt.assert_called_once_with(["run", "--models", "+tag"])
        assert exc_info.value.code == 0

    @patch("xbt.main.run_dbt")
    def test_main_version_flag(self, mock_run_dbt, tmp_path, monkeypatch, capsys):
        """Test that --version runs dbt --version and lists plugins."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_run_dbt.return_value = mock_result

        monkeypatch.setattr(sys, "argv", ["xbt", "--version"])
        monkeypatch.chdir(tmp_path)

        main()

        # Should print xbt version, plugins, and call dbt --version
        captured = capsys.readouterr()
        assert "0.1.0" in captured.out  # xbt version
        assert "xbt-plugins:" in captured.out  # xbt-plugins section
        assert "example_builtin" in captured.out  # built-in plugin
        mock_run_dbt.assert_called_once_with(["--version"])

    @patch("xbt.main.run_dbt")
    @patch("xbt.main.create_plugin_manager")
    def test_main_before_hook_can_mutate_args(
        self, mock_pm, mock_run_dbt, tmp_path, monkeypatch
    ):
        """Test that before_dbt hook can modify arguments."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_run_dbt.return_value = mock_result

        mock_manager = Mock()
        modified_args = ["run", "--models", "+modified"]
        mock_manager.hook.before_dbt.return_value = [modified_args]
        mock_manager.hook.after_dbt.return_value = None
        mock_pm.return_value = mock_manager

        monkeypatch.setattr(sys, "argv", ["xbt", "run", "--models", "+tag"])
        monkeypatch.chdir(tmp_path)

        with pytest.raises(SystemExit):
            main()

        # Should use modified args
        mock_run_dbt.assert_called_once_with(modified_args)

    @patch("xbt.main.run_dbt")
    @patch("xbt.main.create_plugin_manager")
    def test_main_project_name_in_context(
        self, mock_pm, mock_run_dbt, tmp_path, monkeypatch
    ):
        """Test that project name is determined and passed to hooks."""
        project_file = tmp_path / "dbt_project.yaml"
        project_file.write_text("name: test_project\n")

        mock_result = Mock()
        mock_result.returncode = 0
        mock_run_dbt.return_value = mock_result

        mock_manager = Mock()
        mock_manager.hook.before_dbt.return_value = []
        mock_manager.hook.after_dbt.return_value = None
        mock_pm.return_value = mock_manager

        monkeypatch.setattr(sys, "argv", ["xbt", "run"])
        monkeypatch.chdir(tmp_path)

        with pytest.raises(SystemExit):
            main()

        # Check that before_dbt was called with correct context
        call_args = mock_manager.hook.before_dbt.call_args
        context = call_args.kwargs["context"]
        assert context["project_name"] == "test_project"

    @patch("xbt.main.run_dbt")
    @patch("xbt.main.create_plugin_manager")
    def test_main_after_hook_receives_artifacts(
        self, mock_pm, mock_run_dbt, tmp_path, monkeypatch
    ):
        """Test that after_dbt hook receives artifacts."""
        # Create target directory with artifacts
        target_dir = tmp_path / "target"
        target_dir.mkdir()
        (target_dir / "manifest.json").write_text('{"nodes": {}}')
        (target_dir / "run_results.json").write_text('{"results": []}')

        mock_result = Mock()
        mock_result.returncode = 0
        mock_run_dbt.return_value = mock_result

        mock_manager = Mock()
        mock_manager.hook.before_dbt.return_value = []
        mock_manager.hook.after_dbt.return_value = None
        mock_pm.return_value = mock_manager

        monkeypatch.setattr(sys, "argv", ["xbt", "run"])
        monkeypatch.chdir(tmp_path)

        with pytest.raises(SystemExit):
            main()

        # Check that after_dbt was called with artifacts
        call_args = mock_manager.hook.after_dbt.call_args
        artifacts = call_args.kwargs["artifacts"]
        assert "manifest" in artifacts
        assert artifacts["manifest"]["content"] == {"nodes": {}}
