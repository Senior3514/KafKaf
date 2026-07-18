import httpx
import pytest
from typer.testing import CliRunner

from kafkaf.clients.cli.main import app

runner = CliRunner()


def _response(status_code, json_body):
    request = httpx.Request("GET", "http://localhost:8420/x")
    return httpx.Response(status_code, json=json_body, request=request)


class TestAutonomyCommand:
    def test_show_current_level(self, monkeypatch):
        monkeypatch.setattr(
            httpx,
            "get",
            lambda url, timeout=None: _response(
                200, {"level": "assisted", "skills_allowed": True, "description": "some description"}
            ),
        )
        result = runner.invoke(app, ["autonomy"])
        assert result.exit_code == 0
        assert "level: assisted" in result.output
        assert "skills allowed: True" in result.output

    def test_set_level(self, monkeypatch):
        captured = {}

        def fake_post(url, json=None, timeout=None):
            captured["url"] = url
            captured["json"] = json
            return _response(200, {"level": "observe", "skills_allowed": False, "description": "locked down"})

        monkeypatch.setattr(httpx, "post", fake_post)
        result = runner.invoke(app, ["autonomy", "--set", "observe"])
        assert result.exit_code == 0
        assert captured["url"].endswith("/autonomy")
        assert captured["json"] == {"level": "observe"}
        assert "level: observe" in result.output

    def test_set_unknown_level_reports_error(self, monkeypatch):
        def fake_post(url, json=None, timeout=None):
            request = httpx.Request("POST", url)
            return httpx.Response(400, json={"detail": "Unknown autonomy level 'bogus'."}, request=request)

        monkeypatch.setattr(httpx, "post", fake_post)
        result = runner.invoke(app, ["autonomy", "--set", "bogus"])
        assert result.exit_code != 0


class TestWorkspaceCommand:
    def test_show_current_workspace(self, monkeypatch):
        monkeypatch.setattr(
            httpx, "get", lambda url, timeout=None: _response(200, {"skills_workspace_dir": "/home/user/kafkaf-workspace"})
        )
        result = runner.invoke(app, ["workspace"])
        assert result.exit_code == 0
        assert "workspace: /home/user/kafkaf-workspace" in result.output

    def test_set_workspace(self, monkeypatch, tmp_path):
        captured = {}

        def fake_post(url, json=None, timeout=None):
            captured["url"] = url
            captured["json"] = json
            return _response(200, {"skills_workspace_dir": str(tmp_path)})

        monkeypatch.setattr(httpx, "post", fake_post)
        result = runner.invoke(app, ["workspace", "--set", str(tmp_path)])
        assert result.exit_code == 0
        assert captured["url"].endswith("/skills/workspace")
        assert captured["json"] == {"path": str(tmp_path)}
        assert f"workspace: {tmp_path}" in result.output
