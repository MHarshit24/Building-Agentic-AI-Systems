"""
Unit tests for main.py — the combined gRPC+gRPC-Web server entry point.

Coverage target: lines 23-71 (module-level imports + _start_grpc_thread + main).
grpc_web_server is stubbed in sys.modules before main is imported so no real
server sockets are created.
"""
import sys
import types
import pytest
from unittest.mock import MagicMock, patch

# ── Stub grpc_web_server before main.py is first imported ─────────────────────
# main.py does ``from grpc_web_server import serve as _grpc_web_serve`` at the
# module level.  We register a stub so that import succeeds without sonora.
_grpc_web_stub = types.ModuleType("grpc_web_server")
_grpc_web_stub.serve = MagicMock()
sys.modules.setdefault("grpc_web_server", _grpc_web_stub)


# ── _start_grpc_thread ────────────────────────────────────────────────────────

class TestStartGrpcThread:
    """Tests for the _start_grpc_thread() helper (lines 41-50)."""

    def test_returns_daemon_thread(self):
        with patch("main._grpc_serve", return_value=None):
            from main import _start_grpc_thread
            t = _start_grpc_thread(port=50051, workers=10)
        assert t.daemon is True
        t.join(timeout=2)

    def test_thread_is_named_grpc_server(self):
        with patch("main._grpc_serve", return_value=None):
            from main import _start_grpc_thread
            t = _start_grpc_thread(port=50051, workers=5)
        assert t.name == "grpc-server"
        t.join(timeout=2)

    def test_thread_passes_port_and_workers_kwargs(self):
        captured = {}

        def _fake_serve(**kwargs):
            captured.update(kwargs)

        with patch("main._grpc_serve", side_effect=_fake_serve):
            from main import _start_grpc_thread
            t = _start_grpc_thread(port=9999, workers=4)
            t.join(timeout=2)

        assert captured.get("port") == 9999
        assert captured.get("workers") == 4


# ── main() ────────────────────────────────────────────────────────────────────

class TestMain:
    """Tests for the main() entry-point function (lines 53-71)."""

    def test_calls_grpc_web_serve(self):
        with patch("main._grpc_serve"), \
             patch("main._grpc_web_serve") as mock_web, \
             patch("main.flush_langfuse"):
            mock_web.side_effect = KeyboardInterrupt()
            from main import main
            main()
        mock_web.assert_called_once()

    def test_keyboard_interrupt_is_handled_without_raising(self):
        with patch("main._grpc_serve"), \
             patch("main._grpc_web_serve", side_effect=KeyboardInterrupt()), \
             patch("main.flush_langfuse"):
            from main import main
            main()  # must not propagate KeyboardInterrupt

    def test_flushes_langfuse_after_keyboard_interrupt(self):
        with patch("main._grpc_serve"), \
             patch("main._grpc_web_serve", side_effect=KeyboardInterrupt()), \
             patch("main.flush_langfuse") as mock_flush:
            from main import main
            main()
        mock_flush.assert_called_once()

    def test_reads_grpc_port_from_env(self, monkeypatch):
        monkeypatch.setenv("GRPC_PORT", "9001")
        with patch("main._grpc_serve"), \
             patch("main._grpc_web_serve", side_effect=KeyboardInterrupt()), \
             patch("main.flush_langfuse"), \
             patch("main._start_grpc_thread") as mock_start:
            from main import main
            main()
        assert mock_start.call_args.kwargs["port"] == 9001

    def test_reads_grpc_web_port_from_env(self, monkeypatch):
        monkeypatch.setenv("GRPC_WEB_PORT", "8888")
        with patch("main._grpc_serve"), \
             patch("main._grpc_web_serve") as mock_web, \
             patch("main.flush_langfuse"):
            mock_web.side_effect = KeyboardInterrupt()
            from main import main
            main()
        assert mock_web.call_args.kwargs["port"] == 8888

    def test_reads_grpc_workers_from_env(self, monkeypatch):
        monkeypatch.setenv("GRPC_WORKERS", "20")
        with patch("main._grpc_serve"), \
             patch("main._grpc_web_serve", side_effect=KeyboardInterrupt()), \
             patch("main.flush_langfuse"), \
             patch("main._start_grpc_thread") as mock_start:
            from main import main
            main()
        assert mock_start.call_args.kwargs["workers"] == 20
