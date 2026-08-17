# gRPC + FastAPI “Hello World” (Python) — End‑to‑End with `uv` 


> 1.  create a `uv` project,
> 2.  define a `.proto`,
> 3.  generate Python gRPC code,
> 4.  run an **async gRPC server**, and
> 5.  call it via a **FastAPI** HTTP gateway.

***

## What You’ll Build

    grpc-fastapi-hello/
    ├─ proto/
    │  └─ hello.proto
    ├─ generated/                  # auto-generated from .proto
    │  ├─ __init__.py
    │  ├─ hello_pb2.py
    │  └─ hello_pb2_grpc.py
    ├─ greeter_server.py           # gRPC server (async)
    ├─ api_gateway.py              # FastAPI gateway that calls gRPC
    ├─ pyproject.toml              # managed by uv
    ├─ uv.lock
    └─ README.md                   # (this file)

***

## Prerequisites

*   **Python 3.10+**
*   **uv** installed (cross‑platform, super fast).
    *   Install:
        *   macOS/Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
        *   Windows (PowerShell): `iwr https://astral.sh/uv/install.ps1 -UseBasicParsing | iex`

> `uv` will create and use a **project‑local virtual environment** automatically. No need to run `python -m venv` manually.

***

## 1) Create a New Project with `uv init`

```bash
# Create & enter your project
mkdir grpc-fastapi-hello
cd grpc-fastapi-hello

# Initialize the project
uv init --package
or
uv init
```

This creates `pyproject.toml`, `README.md`, and a local `.venv` (by default).  
You can inspect `pyproject.toml` to see project metadata.

***

## 2) Add Dependencies with `uv add`

Add gRPC, tooling, and FastAPI stack:

```bash
uv add grpcio grpcio-tools protobuf fastapi uvicorn
```

> `uv add` writes dependencies to `pyproject.toml` and resolves versions into `uv.lock`.  
> No `pip install …` required; `uv` does the install for you.

## pyproject.toml

```toml

[project]
name = "grpc-fastapi-hello"
version = "0.1.0"
description = "Add your description here"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.135.1",
    "grpcio>=1.78.0",
    "grpcio-tools>=1.78.0",
    "protobuf>=6.33.5",
    "uvicorn>=0.41.0",
]

```

***


## 3) Create the `.proto` Definition

Create the folder and file:

```bash
mkdir -p proto
```

**`proto/hello.proto`**

```proto

syntax = "proto3";

package hello;

// The request message containing the user's name.
message HelloRequest {
  string name = 1;
}

// The response message containing the greeting
message HelloReply {
  string message = 1;
}

// The Hello service definition.
service Greeter {
  rpc SayHello (HelloRequest) returns (HelloReply);
}

```

**What it means (quick recap):**

*   **message** types are your request/response shapes.
*   **service** groups RPC methods. We define one: `SayHello`.

***


## 4) Generate Python gRPC Code

Create the output directory for generated files:

```bash
mkdir -p generated
touch generated/__init__.py
```

Compile the `.proto` file to generate Python code:

```bash

uv run python -m grpc_tools.protoc \
  -I ./proto \
  --python_out=./generated \
  --grpc_python_out=./generated \
  ./proto/hello.proto
```

This will create:

*   `generated/hello_pb2.py` (messages)
*   `generated/hello_pb2_grpc.py` (service base & client stubs)

***


## 5) Implement the **gRPC Server**

**`greeter_server.py`**

```python

import asyncio
import os
import sys
import grpc

# Ensure we can import from ./generated
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
GENERATED_DIR = os.path.join(CURRENT_DIR, "generated")
if GENERATED_DIR not in sys.path:
    sys.path.insert(0, GENERATED_DIR)

from generated import hello_pb2, hello_pb2_grpc


class GreeterServicer(hello_pb2_grpc.GreeterServicer):
    async def SayHello(self, request, context):
        name = request.name or "World"
        message = f"Hello, {name} from gRPC!"
        return hello_pb2.HelloReply(message=message)


async def serve(host: str = "0.0.0.0", port: int = 50051):
    server = grpc.aio.server()
    hello_pb2_grpc.add_GreeterServicer_to_server(GreeterServicer(), server)
    server.add_insecure_port(f"{host}:{port}")
    print(f"[gRPC] Serving on {host}:{port}")
    await server.start()
    await server.wait_for_termination()


if __name__ == "__main__":
    asyncio.run(serve())


```
***

## 6) Create the **FastAPI Gateway**

**`api_gateway.py`**

```python

import os
import sys
from typing import Optional

import grpc
from fastapi import FastAPI, Query, HTTPException

# Ensure we can import from ./generated
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
GENERATED_DIR = os.path.join(CURRENT_DIR, "generated")
if GENERATED_DIR not in sys.path:
    sys.path.insert(0, GENERATED_DIR)

from generated import hello_pb2, hello_pb2_grpc

app = FastAPI(title="FastAPI → gRPC Gateway", version="1.0.0")

GRPC_TARGET = os.getenv("GRPC_TARGET", "localhost:50051")


@app.on_event("startup")
async def startup():
    # Create and reuse a single channel/stub (better performance)
    app.state.grpc_channel = grpc.aio.insecure_channel(GRPC_TARGET)
    app.state.grpc_stub = hello_pb2_grpc.GreeterStub(app.state.grpc_channel)


@app.on_event("shutdown")
async def shutdown():
    if getattr(app.state, "grpc_channel", None) is not None:
        await app.state.grpc_channel.close()


@app.get("/hello")
async def hello(name: Optional[str] = Query(default="World", min_length=1, description="Your name")):
    try:
        response = await app.state.grpc_stub.SayHello(
            hello_pb2.HelloRequest(name=name),
            timeout=3.0
        )
        return {"message": response.message, "via": "FastAPI → gRPC"}
    except grpc.aio.AioRpcError as e:
        raise HTTPException(status_code=502, detail=f"gRPC error: {e.code().name}") from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


```



## 7) Run the server:

Run it (in one terminal):

```bash
uv run python greeter_server.py
```

You should see:

    [gRPC] Serving on 0.0.0.0:50051

Keep it running.

***

## 8) Run the client:

Run FastAPI (in a **second terminal**):

```bash
uv run uvicorn api_gateway:app --host 0.0.0.0 --port 8000 --reload
```

You should see:

    Uvicorn running on http://0.0.0.0:8000 (Reloading)

***

## 9) Test End‑to‑End

With both processes running:

*   gRPC server → `localhost:50051`
*   FastAPI → `http://localhost:8000`

**Test via curl:**

```bash
curl "http://localhost:8000/hello?name=Saravanan"
```

Expected:

```json
{
  "message": "Hello, Saravanan from gRPC!",
  "via": "FastAPI → gRPC"
}
```

**Or open docs:**

*   Swagger UI → <http://localhost:8000/docs>
*   ReDoc → <http://localhost:8000/redoc>

***

