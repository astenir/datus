from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load_tool():
    path = Path(__file__).resolve().parents[3] / "scripts" / "enterprise_local_api.py"
    spec = importlib.util.spec_from_file_location("enterprise_local_api", path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_signed_request_keeps_query_in_url_but_not_signature_path():
    tool = _load_tool()

    signed = tool.build_signed_request(
        base_url="http://api.local",
        method="get",
        path="/api/v1/catalog/list?datasource_id=ccks_fund",
        secret="local-secret",
        user="alice",
        project="enterprise",
        permissions=["module.datasource_catalog"],
        timestamp="1000",
    )
    headers = {name: signed.headers.get(name, "") for name in tool.SignedHeaderAuthProvider(secret="x")._signed_headers}
    expected_signature = tool.SignedHeaderAuthProvider(secret="local-secret").sign_request(
        method="GET",
        path="/api/v1/catalog/list",
        timestamp="1000",
        headers=headers,
    )

    assert signed.url == "http://api.local/api/v1/catalog/list?datasource_id=ccks_fund"
    assert signed.headers["X-Datus-Signature"] == f"sha256={expected_signature}"


def test_curl_command_includes_json_body_and_content_type():
    tool = _load_tool()

    signed = tool.build_signed_request(
        base_url="http://api.local",
        method="POST",
        path="/api/v1/sql/execute",
        secret="local-secret",
        user="alice",
        project="enterprise",
        permissions=["module.sql_executor"],
        body={"sql_query": "SELECT 1", "result_format": "json"},
        timestamp="1000",
    )
    command = tool._curl_command(signed)

    assert "-X POST" in command
    assert "Content-Type: application/json" in command
    assert "SELECT 1" in command
    assert "http://api.local/api/v1/sql/execute" in command


def test_request_command_sends_signed_json(monkeypatch, capsys):
    tool = _load_tool()
    sent = []

    def fake_send(signed_request, *, timeout):
        sent.append((signed_request, timeout))
        return 200, {}, json.dumps({"success": True, "data": {"ok": True}})

    monkeypatch.setattr(tool, "_send", fake_send)

    status = tool.main(
        [
            "request",
            "--secret",
            "local-secret",
            "--base-url",
            "http://api.local",
            "--method",
            "POST",
            "--path",
            "/api/v1/sql/execute",
            "--permission",
            "module.sql_executor",
            "--json",
            '{"sql_query":"SELECT 1","result_format":"json"}',
        ]
    )

    assert status == 0
    assert sent[0][0].method == "POST"
    assert sent[0][0].body == b'{"sql_query": "SELECT 1", "result_format": "json"}'
    assert "HTTP 200" in capsys.readouterr().out


def test_smoke_command_uses_identity_for_all_steps(monkeypatch):
    tool = _load_tool()
    requests = []

    def fake_send(signed_request, *, timeout):
        requests.append((signed_request, timeout))
        return 200, {}, json.dumps({"success": True})

    monkeypatch.setattr(tool, "_send", fake_send)

    status = tool.main(
        [
            "smoke",
            "--secret",
            "local-secret",
            "--base-url",
            "http://api.local",
            "--user",
            "bob",
            "--permission",
            "module.datasource_catalog,module.sql_executor",
            "--datasource",
            "ccks_fund",
            "--sql",
            "SELECT 1",
        ]
    )

    assert status == 0
    assert [item[0].method for item in requests] == ["GET", "GET", "GET", "GET", "POST"]
    assert requests[0][0].headers["X-Datus-User-Id"] == "bob"
    assert requests[3][0].url == "http://api.local/api/v1/catalog/list?datasource_id=ccks_fund"
    assert requests[4][0].body is not None
