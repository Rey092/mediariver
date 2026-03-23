"""Tests for CLI commands."""

from typer.testing import CliRunner

from mediariver.cli import app

runner = CliRunner()


class TestCLI:
    def test_validate_valid_workflows(self, tmp_path):
        wf = tmp_path / "test.yaml"
        wf.write_text("""
name: test
connections:
  local:
    type: local
watch:
  connection: local
  path: /tmp
  extensions: [.mp4]
flow:
  - id: probe
    action: video.info
    input: "{{file.path}}"
""")
        result = runner.invoke(app, ["validate", "--workflows-dir", str(tmp_path)])
        assert result.exit_code == 0

    def test_validate_empty_dir(self, tmp_path):
        result = runner.invoke(app, ["validate", "--workflows-dir", str(tmp_path)])
        assert result.exit_code == 0
