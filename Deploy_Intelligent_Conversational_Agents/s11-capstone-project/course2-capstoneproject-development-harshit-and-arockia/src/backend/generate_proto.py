#!/usr/bin/env python3
"""
Generate Python gRPC stubs from proto/job_agent.proto.

Usage (from src/backend/):
    python generate_proto.py

Prerequisites:
    pip install grpcio-tools
"""
import subprocess
import sys
from pathlib import Path


def main() -> None:
    backend_dir = Path(__file__).parent
    proto_dir   = backend_dir / "proto"
    proto_file  = proto_dir / "job_agent.proto"

    if not proto_file.exists():
        print(f"ERROR: proto file not found: {proto_file}", file=sys.stderr)
        sys.exit(1)

    # Generate message classes (job_agent_pb2.py) and service stubs
    # (job_agent_pb2_grpc.py) into the proto/ directory.
    cmd = [
        sys.executable, "-m", "grpc_tools.protoc",
        f"--proto_path={proto_dir}",
        f"--python_out={proto_dir}",
        f"--grpc_python_out={proto_dir}",
        str(proto_file),
    ]
    print("Running:", " ".join(str(c) for c in cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
        print(
            "\nHint: install grpcio-tools first:\n"
            "    pip install grpcio-tools",
            file=sys.stderr,
        )
        sys.exit(result.returncode)

    # protoc generates a bare `import job_agent_pb2` inside the grpc file.
    # Fix it to a package-relative import so it works when proto/ is a package.
    grpc_file = proto_dir / "job_agent_pb2_grpc.py"
    if grpc_file.exists():
        content = grpc_file.read_text(encoding="utf-8")
        patched = content.replace(
            "import job_agent_pb2 as job__agent__pb2",
            "from proto import job_agent_pb2 as job__agent__pb2",
        )
        if patched != content:
            grpc_file.write_text(patched, encoding="utf-8")
            print("Patched relative import in job_agent_pb2_grpc.py")

    print("\nGenerated files:")
    for f in sorted(proto_dir.glob("*_pb2*.py")):
        print(f"  {f.relative_to(backend_dir)}")
    print("\nDone. You can now start the gRPC server:")
    print("  python grpc_server.py")


if __name__ == "__main__":
    main()
