"""
app/win_loop.py

Windows-only dev-server concern: uvicorn's own built-in "asyncio" loop
factory (uvicorn.loops.asyncio.asyncio_loop_factory) hard-codes
asyncio.ProactorEventLoop on win32 (confirmed by reading its source) —
it constructs the loop directly via asyncio.run(..., loop_factory=...),
which bypasses asyncio.set_event_loop_policy() entirely (Python 3.12+
behavior), so the policy set in app/main.py has no effect on uvicorn's
own server loop, only on other entry points (pytest, plain scripts).

§40's checkpointer (psycopg's async driver) cannot run under
ProactorEventLoop — see app/main.py's own comment for the full
explanation and the MCP-fallback reasoning for why SelectorEventLoop is
safe here.

Usage — start the dev server with this loop factory explicitly:
    uvicorn app.main:app --loop app.win_loop:loop_factory

Not needed outside local Windows development: the real Stage 10 Docker
deployment runs on Linux, where this whole ProactorEventLoop/psycopg
conflict doesn't exist and uvicorn's default "asyncio" loop is fine.
"""

import asyncio

# A custom `--loop module:name` target is called with ZERO arguments and
# must return a loop INSTANCE directly (confirmed by reading
# Config.get_loop_factory(): unlike uvicorn's own built-in factory names
# — "asyncio"/"uvloop" — a dotted-path target is passed straight through
# to asyncio.run(loop_factory=...) without ever being called with
# use_subprocess=...). Returning the bare class here (as uvicorn's own
# asyncio_loop_factory does) would leave that class uncalled — asyncio.run
# would then treat the CLASS as the loop instance and fail on the first
# real method call.


def loop_factory() -> asyncio.AbstractEventLoop:
    return asyncio.SelectorEventLoop()
