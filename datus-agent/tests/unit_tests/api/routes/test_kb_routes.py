"""CI-level tests for datus/api/routes/kb_routes.py.

All external dependencies are mocked. Zero API keys, zero network access required.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from datus.api import deps
from datus.api.auth.context import AppContext
from datus.api.enterprise.defaults import (
    InMemorySessionOwnerStore,
    LocalAuthorizationProvider,
    NoopAuditSink,
    PassthroughConfigProjector,
)
from datus.api.enterprise.loader import EnterpriseExtensions
from datus.api.models.kb_models import BootstrapKbEvent
from datus.api.routes.kb_routes import router
from datus.api.utils import stream_cancellation
from datus.api.utils.stream_cancellation import cleanup_cancel_token, create_cancel_token
from datus.configuration.agent_config import DocumentConfig
from datus.utils.exceptions import DatusException, ErrorCode

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_datus_service():
    """Create a mock DatusService with agent_config and kb."""
    svc = MagicMock()
    svc.project_id = "proj"
    svc.agent_config = MagicMock()
    svc.agent_config.home = "/tmp/test_home"
    svc.agent_config.api_config = {}
    svc.agent_config.enterprise_config = {}
    svc.agent_config.document_configs = {}
    svc.kb = MagicMock()
    return svc


def _enterprise_extensions() -> EnterpriseExtensions:
    return EnterpriseExtensions(
        enabled=True,
        authorization_provider=LocalAuthorizationProvider(),
        config_projector=PassthroughConfigProjector(),
        session_owner_store=InMemorySessionOwnerStore(),
        audit_sink=NoopAuditSink(),
    )


def _override_app_context(app: FastAPI, ctx: AppContext) -> None:
    async def override_context(request: Request):
        request.state.app_context = ctx
        return ctx

    app.dependency_overrides[deps.get_request_app_context] = override_context


@pytest.fixture
def client(mock_datus_service):
    """Create a TestClient with mocked dependencies."""
    from datus.api.deps import get_datus_service

    app = FastAPI()
    app.include_router(router)
    ctx = AppContext(user_id="u1", project_id="proj")

    async def override_service(request: Request):
        request.state.app_context = ctx
        return mock_datus_service

    app.dependency_overrides[get_datus_service] = override_service
    _override_app_context(app, ctx)
    with TestClient(app) as c:
        yield c


def _client_with_context(mock_datus_service, ctx: AppContext):
    app = FastAPI()
    app.include_router(router)

    async def override_service(request: Request):
        request.state.app_context = ctx
        return mock_datus_service

    app.dependency_overrides[deps.get_datus_service] = override_service
    _override_app_context(app, ctx)
    return TestClient(app, raise_server_exceptions=False)


def _make_kb_events():
    """Return two sample BootstrapKbEvent instances."""
    return [
        BootstrapKbEvent(
            stream_id="s1",
            component="platform_doc",
            stage="task_started",
            timestamp="2025-01-01T00:00:00",
        ),
        BootstrapKbEvent(
            stream_id="s1",
            component="platform_doc",
            stage="task_completed",
            timestamp="2025-01-01T00:00:01",
        ),
    ]


@pytest.mark.parametrize(
    ("path", "json_body"),
    [
        ("/api/v1/kb/bootstrap", {"components": ["metadata"]}),
        ("/api/v1/kb/bootstrap/stream-1/cancel", None),
        ("/api/v1/kb/bootstrap-docs", {"platform": "snowflake"}),
        ("/api/v1/kb/bootstrap-docs/stream-1/cancel", None),
    ],
)
def test_kb_routes_require_module_kb(monkeypatch, mock_datus_service, path, json_body):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.chat"})

    with _client_with_context(mock_datus_service, ctx) as test_client:
        if json_body is None:
            response = test_client.post(path)
        else:
            response = test_client.post(path, json=json_body)

    assert response.status_code == 403
    mock_datus_service.kb.bootstrap_stream.assert_not_called()
    mock_datus_service.kb.bootstrap_doc_stream.assert_not_called()


@pytest.mark.parametrize(
    ("path", "json_body"),
    [
        ("/api/v1/kb/bootstrap", {"components": ["metadata"]}),
        ("/api/v1/kb/bootstrap/stream-1/cancel", None),
        ("/api/v1/kb/bootstrap-docs", {"platform": "snowflake"}),
        ("/api/v1/kb/bootstrap-docs/stream-1/cancel", None),
    ],
)
def test_kb_rbac_denial_does_not_resolve_datus_service(monkeypatch, path, json_body):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.chat"})
    app = FastAPI()
    app.include_router(router)

    async def reject_service(request: Request):
        raise AssertionError("RBAC denial resolved DatusService")

    async def override_context(request: Request):
        request.state.app_context = ctx
        return ctx

    app.dependency_overrides[deps.get_datus_service] = reject_service
    app.dependency_overrides[deps.get_request_app_context] = override_context

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(path, json=json_body) if json_body is not None else client.post(path)

    assert response.status_code == 403


@pytest.mark.parametrize("path", ["/api/v1/kb/bootstrap", "/api/v1/kb/bootstrap-docs"])
def test_kb_invalid_body_does_not_resolve_datus_service(monkeypatch, path):
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.kb"})
    app = FastAPI()
    app.include_router(router)

    async def reject_service(request: Request):
        raise AssertionError("Invalid body resolved DatusService")

    async def override_context(request: Request):
        request.state.app_context = ctx
        return ctx

    app.dependency_overrides[deps.get_datus_service] = reject_service
    app.dependency_overrides[deps.get_request_app_context] = override_context

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(path, json=[])

    assert response.status_code == 422


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/kb/bootstrap/owned-stream/cancel",
        "/api/v1/kb/bootstrap-docs/owned-stream/cancel",
    ],
)
def test_kb_cancel_routes_do_not_resolve_datus_service(monkeypatch, path):
    """Cancel only needs the authenticated context and token ownership metadata."""
    monkeypatch.setattr(deps, "_enterprise_extensions", _enterprise_extensions())
    ctx = AppContext(user_id="u1", project_id="proj", permissions={"module.kb"})
    create_cancel_token("owned-stream", owner_user_id="u1", project_id="proj")
    app = FastAPI()
    app.include_router(router)

    async def reject_service(request: Request):
        raise AssertionError("cancel route resolved DatusService")

    async def override_context(request: Request):
        request.state.app_context = ctx
        return ctx

    app.dependency_overrides[deps.get_datus_service] = reject_service
    app.dependency_overrides[deps.get_request_app_context] = override_context

    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.post(path)
    finally:
        cleanup_cancel_token("owned-stream")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"] == {"stream_id": "owned-stream", "cancelled": True}


# ---------------------------------------------------------------------------
# /api/v1/kb/uploads
# ---------------------------------------------------------------------------


class TestKbUploads:
    def test_upload_success_story_csv_success(self, mock_datus_service, tmp_path):
        mock_datus_service.agent_config.home = str(tmp_path)
        ctx = AppContext(user_id="alice", project_id="proj", permissions={"module.kb"})

        with _client_with_context(mock_datus_service, ctx) as test_client:
            response = test_client.post(
                "/api/v1/kb/uploads",
                data={"purpose": "success_story_csv"},
                files=[("files", ("success_story.csv", b"question,sql\nq,select 1\n", "text/csv"))],
            )

        assert response.status_code == 200
        body = response.json()
        assert body["purpose"] == "success_story_csv"
        assert body["owner_user_id"] == "alice"
        assert body["project_id"] == "proj"
        assert body["files"][0]["filename"] == "success_story.csv"
        assert body["files"][0]["relative_path"].startswith("uploads/proj/alice/")
        assert not body["files"][0]["relative_path"].startswith("/")
        assert (tmp_path / "files" / body["files"][0]["relative_path"]).is_file()

    def test_upload_reference_sql_multiple_files_success(self, mock_datus_service, tmp_path):
        mock_datus_service.agent_config.home = str(tmp_path)
        ctx = AppContext(user_id="alice", project_id="proj", permissions={"module.kb"})

        with _client_with_context(mock_datus_service, ctx) as test_client:
            response = test_client.post(
                "/api/v1/kb/uploads",
                data={"purpose": "reference_sql"},
                files=[
                    ("files", ("a.sql", b"select 1", "text/plain")),
                    ("files", ("b.sql", b"select 2", "text/plain")),
                ],
            )

        assert response.status_code == 200
        body = response.json()
        assert body["purpose"] == "reference_sql"
        assert [file["filename"] for file in body["files"]] == ["a.sql", "b.sql"]
        assert all((tmp_path / "files" / file["relative_path"]).is_file() for file in body["files"])

    def test_upload_invalid_extension_fails(self, mock_datus_service, tmp_path):
        mock_datus_service.agent_config.home = str(tmp_path)
        ctx = AppContext(user_id="alice", project_id="proj", permissions={"module.kb"})

        with _client_with_context(mock_datus_service, ctx) as test_client:
            response = test_client.post(
                "/api/v1/kb/uploads",
                data={"purpose": "success_story_csv"},
                files=[("files", ("story.exe", b"not csv", "application/octet-stream"))],
            )

        assert response.status_code == 415
        assert response.json()["detail"] == "KB_UPLOAD_INVALID_FILE_TYPE"

    def test_upload_empty_file_fails_and_cleans_up(self, mock_datus_service, tmp_path):
        mock_datus_service.agent_config.home = str(tmp_path)
        ctx = AppContext(user_id="alice", project_id="proj", permissions={"module.kb"})

        with _client_with_context(mock_datus_service, ctx) as test_client:
            response = test_client.post(
                "/api/v1/kb/uploads",
                data={"purpose": "success_story_csv"},
                files=[("files", ("empty.csv", b"", "text/csv"))],
            )

        assert response.status_code == 422
        assert response.json()["detail"] == "KB_UPLOAD_EMPTY"
        uploads_root = tmp_path / "files" / "uploads"
        assert not uploads_root.exists() or not any(uploads_root.rglob("*"))

    def test_upload_filename_with_path_separator_cannot_escape(self, mock_datus_service, tmp_path):
        mock_datus_service.agent_config.home = str(tmp_path)
        ctx = AppContext(user_id="alice", project_id="proj", permissions={"module.kb"})

        with _client_with_context(mock_datus_service, ctx) as test_client:
            response = test_client.post(
                "/api/v1/kb/uploads",
                data={"purpose": "success_story_csv"},
                files=[("files", ("../story.csv", b"question,sql\nq,select 1\n", "text/csv"))],
            )

        assert response.status_code == 200
        file_info = response.json()["files"][0]
        assert file_info["filename"] == "story.csv"
        saved_path = (tmp_path / "files" / file_info["relative_path"]).resolve()
        assert saved_path.is_relative_to((tmp_path / "files").resolve())

    def test_user_cannot_read_or_delete_another_users_upload(self, mock_datus_service, tmp_path):
        mock_datus_service.agent_config.home = str(tmp_path)
        alice_ctx = AppContext(user_id="alice", project_id="proj", permissions={"module.kb"})
        bob_ctx = AppContext(user_id="bob", project_id="proj", permissions={"module.kb"})

        with _client_with_context(mock_datus_service, alice_ctx) as test_client:
            upload = test_client.post(
                "/api/v1/kb/uploads",
                data={"purpose": "success_story_csv"},
                files=[("files", ("story.csv", b"question,sql\nq,select 1\n", "text/csv"))],
            ).json()

        with _client_with_context(mock_datus_service, bob_ctx) as test_client:
            get_response = test_client.get(f"/api/v1/kb/uploads/{upload['upload_id']}")
            delete_response = test_client.delete(f"/api/v1/kb/uploads/{upload['upload_id']}")

        assert get_response.status_code == 403
        assert get_response.json()["detail"] == "KB_UPLOAD_FORBIDDEN"
        assert delete_response.status_code == 403
        assert delete_response.json()["detail"] == "KB_UPLOAD_FORBIDDEN"

    def test_deleted_upload_cannot_be_used_for_build(self, mock_datus_service, tmp_path):
        mock_datus_service.agent_config.home = str(tmp_path)
        ctx = AppContext(user_id="alice", project_id="proj", permissions={"module.kb"})

        with _client_with_context(mock_datus_service, ctx) as test_client:
            upload = test_client.post(
                "/api/v1/kb/uploads",
                data={"purpose": "success_story_csv"},
                files=[("files", ("story.csv", b"question,sql\nq,select 1\n", "text/csv"))],
            ).json()
            delete_response = test_client.delete(f"/api/v1/kb/uploads/{upload['upload_id']}")
            build_response = test_client.post(
                "/api/v1/kb/bootstrap",
                json={"components": ["semantic_model"], "upload_id": upload["upload_id"]},
            )

        assert delete_response.status_code == 200
        assert build_response.status_code == 404
        assert build_response.json()["detail"] == "KB_UPLOAD_NOT_FOUND"
        mock_datus_service.kb.bootstrap_stream.assert_not_called()

    def test_semantic_model_can_bootstrap_from_upload_id(self, mock_datus_service, tmp_path):
        mock_datus_service.agent_config.home = str(tmp_path)
        ctx = AppContext(user_id="alice", project_id="proj", permissions={"module.kb"})
        captured_requests = []

        async def mock_stream(request, stream_id, cancel_event, project_files_root):  # noqa: ARG001
            captured_requests.append((request, project_files_root))
            yield BootstrapKbEvent(
                stream_id=stream_id,
                component="semantic_model",
                stage="task_completed",
                timestamp="2025-01-01T00:00:00",
            )

        mock_datus_service.kb.bootstrap_stream = mock_stream
        with _client_with_context(mock_datus_service, ctx) as test_client:
            upload = test_client.post(
                "/api/v1/kb/uploads",
                data={"purpose": "success_story_csv"},
                files=[("files", ("story.csv", b"question,sql\nq,select 1\n", "text/csv"))],
            ).json()
            response = test_client.post(
                "/api/v1/kb/bootstrap",
                json={"components": ["semantic_model"], "upload_id": upload["upload_id"]},
            )

        assert response.status_code == 200
        request, project_files_root = captured_requests[0]
        assert request.success_story == upload["files"][0]["relative_path"]
        assert project_files_root == str(tmp_path / "files")

    def test_reference_sql_can_bootstrap_from_upload_id(self, mock_datus_service, tmp_path):
        mock_datus_service.agent_config.home = str(tmp_path)
        ctx = AppContext(user_id="alice", project_id="proj", permissions={"module.kb"})
        captured_requests = []

        async def mock_stream(request, stream_id, cancel_event, project_files_root):  # noqa: ARG001
            captured_requests.append(request)
            yield BootstrapKbEvent(
                stream_id=stream_id,
                component="reference_sql",
                stage="task_completed",
                timestamp="2025-01-01T00:00:00",
            )

        mock_datus_service.kb.bootstrap_stream = mock_stream
        with _client_with_context(mock_datus_service, ctx) as test_client:
            upload = test_client.post(
                "/api/v1/kb/uploads",
                data={"purpose": "reference_sql"},
                files=[
                    ("files", ("a.sql", b"select 1", "text/plain")),
                    ("files", ("b.sql", b"select 2", "text/plain")),
                ],
            ).json()
            response = test_client.post(
                "/api/v1/kb/bootstrap",
                json={"components": ["reference_sql"], "upload_id": upload["upload_id"]},
            )

        assert response.status_code == 200
        assert captured_requests[0].sql_dir == Path(upload["files"][0]["relative_path"]).parent.as_posix()

    def test_bootstrap_docs_can_use_upload_id(self, mock_datus_service, tmp_path):
        mock_datus_service.agent_config.home = str(tmp_path)
        mock_datus_service.agent_config.document_configs = {}
        ctx = AppContext(user_id="alice", project_id="proj", permissions={"module.kb"})
        captured_requests = []

        async def mock_stream(request, stream_id, cancel_event):  # noqa: ARG001
            captured_requests.append(request)
            yield BootstrapKbEvent(
                stream_id=stream_id,
                component="platform_doc",
                stage="task_completed",
                timestamp="2025-01-01T00:00:00",
            )

        mock_datus_service.kb.bootstrap_doc_stream = mock_stream
        with _client_with_context(mock_datus_service, ctx) as test_client:
            upload = test_client.post(
                "/api/v1/kb/uploads",
                data={"purpose": "platform_docs", "platform": "duckdb"},
                files=[("files", ("README.md", b"# Docs", "text/markdown"))],
            ).json()
            response = test_client.post(
                "/api/v1/kb/bootstrap-docs",
                json={"platform": "duckdb", "source_type": "local", "upload_id": upload["upload_id"]},
            )

        assert response.status_code == 200
        assert captured_requests[0].source_type == "local"
        assert captured_requests[0].source.startswith(str(tmp_path / "files"))
        assert upload["upload_id"] in captured_requests[0].source

    def test_upload_openapi_is_multipart_form_data(self):
        app = FastAPI()
        app.include_router(router)

        request_body = app.openapi()["paths"]["/api/v1/kb/uploads"]["post"]["requestBody"]

        assert "multipart/form-data" in request_body["content"]


# ---------------------------------------------------------------------------
# POST /api/v1/kb/bootstrap-docs
# ---------------------------------------------------------------------------


class TestBootstrapDocs:
    def test_bootstrap_docs_returns_sse_stream(self, client, mock_datus_service):
        """SSE stream is returned with correct media type and event lines."""
        events = _make_kb_events()

        async def mock_stream(*args, **kwargs):
            for event in events:
                yield event

        mock_datus_service.kb.bootstrap_doc_stream = mock_stream
        mock_datus_service.agent_config.document_configs = {"myplatform": MagicMock(type="github")}

        response = client.post(
            "/api/v1/kb/bootstrap-docs",
            json={"platform": "myplatform"},
        )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        body = response.text
        assert "task_started" in body
        assert "task_completed" in body
        # Each SSE block starts with "event:"
        assert body.count("event:") == 2

    def test_bootstrap_docs_unknown_platform_no_source_returns_422(self, client, mock_datus_service):
        """Unknown platform with no source → 422 because config is missing."""
        mock_datus_service.agent_config.document_configs = {}
        stream_id = "docs-validation-error"

        try:
            with patch("datus.api.routes.kb_routes.uuid.uuid4", return_value=stream_id):
                response = client.post(
                    "/api/v1/kb/bootstrap-docs",
                    json={"platform": "unknown"},
                )

            assert response.status_code == 422
            assert "unknown" in response.json()["detail"]
            assert stream_id not in stream_cancellation._tokens
        finally:
            cleanup_cancel_token(stream_id)

    def test_bootstrap_docs_known_platform_succeeds(self, client, mock_datus_service):
        """Platform present in document_configs → 200 SSE response."""
        events = _make_kb_events()

        async def mock_stream(*args, **kwargs):
            for event in events:
                yield event

        mock_datus_service.kb.bootstrap_doc_stream = mock_stream
        doc_cfg = MagicMock()
        doc_cfg.type = "website"
        mock_datus_service.agent_config.document_configs = {"snowflake": doc_cfg}

        response = client.post(
            "/api/v1/kb/bootstrap-docs",
            json={"platform": "snowflake"},
        )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

    def test_bootstrap_docs_local_path_traversal_returns_422(self, client, mock_datus_service):
        """Local source with path traversal → safe_resolve raises DatusException → 422."""
        # Platform must exist so we pass the first validation check
        doc_cfg = MagicMock()
        doc_cfg.type = "local"
        mock_datus_service.agent_config.document_configs = {"myplatform": doc_cfg}

        with patch(
            "datus.api.routes.kb_routes.safe_resolve",
            side_effect=DatusException(
                ErrorCode.COMMON_VALIDATION_FAILED,
                message="Path '../../../etc/passwd' escapes the project root",
            ),
        ):
            response = client.post(
                "/api/v1/kb/bootstrap-docs",
                json={
                    "platform": "myplatform",
                    "source": "../../../etc/passwd",
                    "source_type": "local",
                },
            )

        assert response.status_code == 422
        assert "escapes" in response.json()["detail"]

    def test_bootstrap_docs_local_source_from_config_validates_path(self, client, mock_datus_service):
        """Local source type from config triggers path validation → DatusException → 422."""
        doc_cfg = MagicMock()
        doc_cfg.type = "local"
        mock_datus_service.agent_config.document_configs = {"testplatform": doc_cfg}

        with patch(
            "datus.api.routes.kb_routes.safe_resolve",
            side_effect=DatusException(
                ErrorCode.COMMON_VALIDATION_FAILED,
                message="escapes the project root",
            ),
        ):
            response = client.post(
                "/api/v1/kb/bootstrap-docs",
                json={
                    "platform": "testplatform",
                    "source": "../secret",
                },
            )

        assert response.status_code == 422

    def test_bootstrap_docs_local_config_source_traversal_returns_422(self, client, mock_datus_service):
        """Configured local sources use the same project-root sandbox as request overrides."""
        stream_id = "docs-config-validation-error"
        mock_datus_service.agent_config.document_configs = {
            "testplatform": DocumentConfig(type="local", source="../../../etc")
        }

        try:
            with patch("datus.api.routes.kb_routes.uuid.uuid4", return_value=stream_id):
                response = client.post(
                    "/api/v1/kb/bootstrap-docs",
                    json={"platform": "testplatform"},
                )

            assert response.status_code == 422
            assert "escapes" in response.json()["detail"]
            assert stream_id not in stream_cancellation._tokens
            mock_datus_service.kb.bootstrap_doc_stream.assert_not_called()
        finally:
            cleanup_cancel_token(stream_id)


class TestCancelDocBootstrap:
    def test_cancel_doc_bootstrap_success(self, client):
        """cancel_stream returns True → response success=True."""
        with patch("datus.api.routes.kb_routes.cancel_stream", return_value=True):
            response = client.post("/api/v1/kb/bootstrap-docs/my-stream-id/cancel")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["stream_id"] == "my-stream-id"
        assert data["data"]["cancelled"] is True

    def test_cancel_doc_bootstrap_unknown_stream(self, client):
        """cancel_stream returns False → response success=False."""
        with patch("datus.api.routes.kb_routes.cancel_stream", return_value=False):
            response = client.post("/api/v1/kb/bootstrap-docs/nonexistent-stream/cancel")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["data"]["cancelled"] is False


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/kb/bootstrap/{stream_id}/cancel",
        "/api/v1/kb/bootstrap-docs/{stream_id}/cancel",
    ],
)
def test_kb_cancel_routes_reject_foreign_stream_owner(mock_datus_service, path):
    """A user with module.kb still cannot cancel another user's stream."""
    stream_id = "owned-stream"
    event = create_cancel_token(stream_id, owner_user_id="alice", project_id="proj")
    try:
        bob_ctx = AppContext(user_id="bob", project_id="proj", permissions={"module.kb"})
        with _client_with_context(mock_datus_service, bob_ctx) as test_client:
            response = test_client.post(path.format(stream_id=stream_id))

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["data"]["cancelled"] is False
        assert not event.is_set()

        alice_ctx = AppContext(user_id="alice", project_id="proj", permissions={"module.kb"})
        with _client_with_context(mock_datus_service, alice_ctx) as test_client:
            response = test_client.post(path.format(stream_id=stream_id))

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["cancelled"] is True
        assert event.is_set()
    finally:
        cleanup_cancel_token(stream_id)


# ---------------------------------------------------------------------------
# POST /api/v1/kb/bootstrap
# ---------------------------------------------------------------------------


class TestBootstrapKb:
    def _valid_bootstrap_payload(self):
        return {"components": ["metadata"]}

    def test_bootstrap_kb_returns_sse_stream(self, client, mock_datus_service):
        """bootstrap_stream async generator → 200 SSE with event lines."""
        events = _make_kb_events()

        async def mock_stream(*args, **kwargs):
            for event in events:
                yield event

        mock_datus_service.kb.bootstrap_stream = mock_stream

        response = client.post(
            "/api/v1/kb/bootstrap",
            json=self._valid_bootstrap_payload(),
        )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        body = response.text
        assert "task_started" in body
        assert "task_completed" in body

    def test_bootstrap_kb_retries_stream_id_collision(self, client, mock_datus_service):
        """A UUID collision must not overwrite another active stream token."""
        old_event = create_cancel_token("dup-stream", owner_user_id="u1", project_id="proj")
        seen_stream_ids = []

        async def mock_stream(request, stream_id, cancel_event, project_files_root):
            seen_stream_ids.append(stream_id)
            yield BootstrapKbEvent(
                stream_id=stream_id,
                component="metadata",
                stage="task_completed",
                timestamp="2025-01-01T00:00:00",
            )

        mock_datus_service.kb.bootstrap_stream = mock_stream

        try:
            with patch("datus.api.routes.kb_routes.uuid.uuid4", side_effect=["dup-stream", "fresh-stream"]):
                response = client.post(
                    "/api/v1/kb/bootstrap",
                    json=self._valid_bootstrap_payload(),
                )

            assert response.status_code == 200
            assert seen_stream_ids == ["fresh-stream"]
            assert "id: fresh-stream" in response.text
            assert stream_cancellation._tokens["dup-stream"] is old_event
        finally:
            cleanup_cancel_token("dup-stream")
            cleanup_cancel_token("fresh-stream")

    def test_bootstrap_kb_path_validation_error(self, client, mock_datus_service):
        """safe_resolve raises DatusException for success_story path → 422."""
        stream_id = "kb-validation-error"
        try:
            with (
                patch("datus.api.routes.kb_routes.uuid.uuid4", return_value=stream_id),
                patch(
                    "datus.api.routes.kb_routes.safe_resolve",
                    side_effect=DatusException(
                        ErrorCode.COMMON_VALIDATION_FAILED,
                        message="Path '../../etc/passwd' escapes the project root",
                    ),
                ),
            ):
                response = client.post(
                    "/api/v1/kb/bootstrap",
                    json={
                        "components": ["semantic_model"],
                        "success_story": "../../etc/passwd",
                    },
                )

            assert response.status_code == 422
            assert "escapes" in response.json()["detail"]
            assert stream_id not in stream_cancellation._tokens
        finally:
            cleanup_cancel_token(stream_id)

    def test_bootstrap_kb_missing_components_returns_422(self, client):
        """components field is required with min_length=1; empty list → 422."""
        response = client.post(
            "/api/v1/kb/bootstrap",
            json={"components": []},
        )

        assert response.status_code == 422

    def test_bootstrap_kb_invalid_strategy_returns_422(self, client):
        """strategy must be one of overwrite/check/incremental → 422 for invalid."""
        response = client.post(
            "/api/v1/kb/bootstrap",
            json={"components": ["metadata"], "strategy": "invalid_strategy"},
        )

        assert response.status_code == 422

    def test_bootstrap_kb_sse_format_contains_id_and_event(self, client, mock_datus_service):
        """Each yielded event produces SSE lines with id:, event:, data: prefixes."""
        events = _make_kb_events()

        async def mock_stream(*args, **kwargs):
            for event in events:
                yield event

        mock_datus_service.kb.bootstrap_stream = mock_stream

        response = client.post(
            "/api/v1/kb/bootstrap",
            json=self._valid_bootstrap_payload(),
        )

        assert response.status_code == 200
        body = response.text
        assert "id:" in body
        assert "event:" in body
        assert "data:" in body


class TestCancelBootstrap:
    def test_cancel_bootstrap_success(self, client):
        """cancel_stream returns True → success=True."""
        with patch("datus.api.routes.kb_routes.cancel_stream", return_value=True):
            response = client.post("/api/v1/kb/bootstrap/active-stream-id/cancel")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["stream_id"] == "active-stream-id"
        assert data["data"]["cancelled"] is True

    def test_cancel_bootstrap_unknown_stream(self, client):
        """cancel_stream returns False → success=False."""
        with patch("datus.api.routes.kb_routes.cancel_stream", return_value=False):
            response = client.post("/api/v1/kb/bootstrap/ghost-stream/cancel")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["data"]["cancelled"] is False
