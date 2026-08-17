"""
Job Placement Agent — Server Entry Point
=========================================
Starts two servers in parallel:

  gRPC server   :50051  — binary protobuf over TCP for Python clients (Streamlit)
  gRPC-Web      :8080   — protobuf over HTTP/1.1 for browser clients (index.html)

Both servers share the same JobAgentServicer so all business logic
is implemented once and exposed on both transports.

Environment variables (all optional):
    GRPC_PORT       gRPC server port        default 50051
    GRPC_WEB_PORT   gRPC-Web server port    default 8080
    GRPC_WORKERS    gRPC thread-pool size   default 10

Usage:
    cd src/backend
    python generate_proto.py   # one-time stub generation
    python main.py             # start both servers
"""

import os
import threading
import logging

from dotenv import load_dotenv
load_dotenv()  # Must be first — before any module that reads env vars

from grpc_server import serve as _grpc_serve
from grpc_web_server import serve as _grpc_web_serve
from observability.langfuse_config import flush_langfuse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


def _start_grpc_thread(port: int, workers: int) -> threading.Thread:
    """Launch the native gRPC server in a daemon background thread."""
    t = threading.Thread(
        target=_grpc_serve,
        kwargs={"port": port, "workers": workers},
        name="grpc-server",
        daemon=True,  # exits automatically when the main thread exits
    )
    t.start()
    return t


def main() -> None:
    grpc_port = int(os.getenv("GRPC_PORT",     "50051"))
    web_port  = int(os.getenv("GRPC_WEB_PORT", "8080"))
    workers   = int(os.getenv("GRPC_WORKERS",  "10"))

    logger.info("=== Job Placement Agent ===")
    logger.info("  gRPC     → 0.0.0.0:%d  (Python / Streamlit clients)", grpc_port)
    logger.info("  gRPC-Web → 0.0.0.0:%d  (browser / index.html clients)", web_port)

    # gRPC runs in a background thread; gRPC-Web blocks the main thread.
    _start_grpc_thread(port=grpc_port, workers=workers)

    try:
        _grpc_web_serve(port=web_port)
    except KeyboardInterrupt:
        logger.info("Shutdown requested — stopping servers…")
    finally:
        flush_langfuse()
        logger.info("Shutdown complete.")


if __name__ == "__main__":
    main()
