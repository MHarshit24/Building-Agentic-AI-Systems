"""
gRPC-Web HTTP server for browser clients.
==========================================
Browsers cannot speak native gRPC (HTTP/2 + binary framing).  The gRPC-Web
protocol wraps protobuf messages in HTTP/1.1 so they can be fetched directly
with the browser Fetch API.

This module exposes the same JobAgentServicer over HTTP using the
`sonora` WSGI adapter, which handles the gRPC-Web framing translation.

Port  :  8080  (GRPC_WEB_PORT env var)
Protocol: HTTP/1.1 + application/grpc-web+proto

CORS is enabled so that any browser origin can reach this server.
Tighten the `allow_origin` parameter in production.

Usage:
    python grpc_web_server.py      # standalone
    # or imported by main.py for the combined-server startup
"""

import logging
from wsgiref.simple_server import make_server, WSGIServer
from socketserver import ThreadingMixIn

from sonora.wsgi import grpcWSGI
from proto import job_agent_pb2_grpc
from grpc_server import JobAgentServicer

logger = logging.getLogger(__name__)

# Headers the browser sends on gRPC-Web pre-flight and data requests.
_CORS_ALLOW_HEADERS = (
    "content-type,x-grpc-web,x-user-agent,grpc-timeout,authorization"
)


# ── CORS middleware ────────────────────────────────────────────────────────────

class CORSMiddleware:
    """
    Minimal WSGI CORS wrapper.

    Attaches Access-Control-* headers to every response and handles
    OPTIONS pre-flight requests so browsers can reach the gRPC-Web endpoint
    from any origin.
    """

    def __init__(self, app: object, allow_origin: str = "*") -> None:
        self._app    = app
        self._origin = allow_origin

    def __call__(self, environ, start_response):
        cors_headers = [
            ("Access-Control-Allow-Origin",   self._origin),
            ("Access-Control-Allow-Headers",  _CORS_ALLOW_HEADERS),
            ("Access-Control-Allow-Methods",  "POST, OPTIONS"),
            ("Access-Control-Expose-Headers", "grpc-status, grpc-message"),
        ]

        if environ["REQUEST_METHOD"] == "OPTIONS":
            # Browser pre-flight — respond immediately without forwarding.
            start_response("204 No Content", cors_headers + [("Content-Length", "0")])
            return [b""]

        def _cors_start(status, headers, exc_info=None):
            return start_response(status, headers + cors_headers, exc_info)

        return self._app(environ, _cors_start)


# ── Threading WSGI server ─────────────────────────────────────────────────────

class _ThreadingWSGIServer(ThreadingMixIn, WSGIServer):
    """Multi-threaded WSGI server so concurrent gRPC-Web calls don't block."""
    daemon_threads = True


# ── Factory & serve ───────────────────────────────────────────────────────────

def create_grpc_web_app(allow_origin: str = "*"):
    """
    Build the gRPC-Web WSGI application.

    Registers JobAgentServicer with a sonora grpcWSGI instance and wraps it
    in the CORS middleware.
    """
    app = grpcWSGI(None)  # None → no fallback WSGI app for non-gRPC-Web paths
    job_agent_pb2_grpc.add_JobAgentServiceServicer_to_server(JobAgentServicer(), app)
    return CORSMiddleware(app, allow_origin=allow_origin)


def serve(
    host: str = "0.0.0.0",
    port: int = 8080,
    allow_origin: str = "*",
) -> None:
    """
    Start the gRPC-Web HTTP server (blocking).

    Args:
        host:         Bind address.
        port:         Listening port (default 8080).
        allow_origin: Value for Access-Control-Allow-Origin header.
                      Use a specific origin in production.
    """
    from wsgiref.simple_server import WSGIRequestHandler

    app  = create_grpc_web_app(allow_origin=allow_origin)
    httpd = _ThreadingWSGIServer((host, port), WSGIRequestHandler)
    httpd.set_app(app)
    logger.info(
        "gRPC-Web server listening on %s:%d (CORS allow-origin: %s)",
        host, port, allow_origin,
    )
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("gRPC-Web server stopping…")
        httpd.shutdown()


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    load_dotenv()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    serve(port=int(os.getenv("GRPC_WEB_PORT", "8080")))
