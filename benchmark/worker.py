"""Subprocess benchmark worker with timing and resource sampling."""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap

from benchmark.config import BenchmarkCase, RunSample

_WORKER_SCRIPT = textwrap.dedent(
    """
    import json
    import os
    import sys
    import time

    import psutil

    payload = json.loads(sys.stdin.read())
    module_name = payload["module"]
    function_name = payload["function"]
    args = payload["args"]
    kwargs = payload["kwargs"]

    process = psutil.Process(os.getpid())
    process.cpu_percent(interval=None)

    started = time.perf_counter()
    module = __import__(module_name)
    fn = getattr(module, function_name)
    fn(*args, **kwargs)
    elapsed = time.perf_counter() - started

    cpu = process.cpu_percent(interval=0.01)
    rss = process.memory_info().rss

    print(json.dumps({
        "wall_seconds": elapsed,
        "peak_rss_bytes": rss,
        "avg_cpu_percent": cpu,
        "success": True,
    }))
    """
)


def run_case_once(
    case: BenchmarkCase,
    *,
    backend: str,
    run_index: int,
) -> RunSample:
    args = json.loads(case.args_json)
    kwargs = json.loads(case.kwargs_json)
    payload = {
        "backend": backend,
        "module": case.module,
        "function": case.function,
        "args": args,
        "kwargs": kwargs,
    }
    try:
        proc = subprocess.run(
            [sys.executable, "-c", _WORKER_SCRIPT],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            error = (proc.stderr or proc.stdout or "worker failed").strip()
            return RunSample(
                benchmark=case.name,
                backend=backend,
                input_size_tier=case.input_size_tier,
                run_index=run_index,
                wall_seconds=0.0,
                peak_rss_bytes=0,
                avg_cpu_percent=0.0,
                success=False,
                error=error[:500],
            )
        data = json.loads(proc.stdout.strip().splitlines()[-1])
        return RunSample(
            benchmark=case.name,
            backend=backend,
            input_size_tier=case.input_size_tier,
            run_index=run_index,
            wall_seconds=float(data["wall_seconds"]),
            peak_rss_bytes=int(data["peak_rss_bytes"]),
            avg_cpu_percent=float(data["avg_cpu_percent"]),
            success=bool(data.get("success", True)),
        )
    except (json.JSONDecodeError, KeyError, IndexError) as exc:
        return RunSample(
            benchmark=case.name,
            backend=backend,
            input_size_tier=case.input_size_tier,
            run_index=run_index,
            wall_seconds=0.0,
            peak_rss_bytes=0,
            avg_cpu_percent=0.0,
            success=False,
            error=str(exc),
        )
