#!/usr/bin/env python3
"""Small concurrent load tester for local Datus API endpoints."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from typing import Any

import httpx

DEFAULT_BASE_URL = "http://127.0.0.1:8000"


@dataclass(frozen=True)
class EndpointCall:
    name: str
    method: str
    path: str
    json_body: dict[str, Any] | None = None
    params: dict[str, str] | None = None
    stream: bool = False


@dataclass
class CallResult:
    name: str
    ok: bool
    status_code: int | None
    latency_ms: float
    bytes_read: int = 0
    sse_events: int = 0
    first_event_ms: float | None = None
    error: str = ""


def _csv_or_repeated(values: list[str] | None) -> list[str]:
    if not values:
        return []
    items: list[str] = []
    for value in values:
        for part in value.split(","):
            item = part.strip()
            if item:
                items.append(item)
    return items


def _headers(args: argparse.Namespace) -> dict[str, str]:
    headers = {"Accept": "application/json"}
    token = args.bearer_token or os.getenv("DATUS_API_TOKEN") or os.getenv("VITE_DEV_ACCESS_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    for raw in _csv_or_repeated(args.header):
        if ":" not in raw:
            raise SystemExit(f"Invalid --header value {raw!r}; expected 'Name: value'.")
        key, value = raw.split(":", 1)
        headers[key.strip()] = value.strip()
    return headers


def _endpoint_for_request(args: argparse.Namespace, index: int) -> EndpointCall:
    scenario = args.scenario
    if scenario == "mixed":
        sequence = ["catalog", "sql", "status"]
        scenario = sequence[index % len(sequence)]

    if scenario == "status":
        return EndpointCall(name="status", method="GET", path="/api/v1/system/status")

    if scenario == "catalog":
        params = {"datasource_id": args.datasource} if args.datasource else None
        return EndpointCall(name="catalog", method="GET", path="/api/v1/catalog/list", params=params)

    if scenario == "sql":
        body: dict[str, Any] = {
            "sql_query": args.sql,
            "result_format": args.result_format,
            "execute_task_id": f"load-{index}-{uuid.uuid4().hex[:8]}",
        }
        if args.database:
            body["database_name"] = args.database
        return EndpointCall(name="sql", method="POST", path="/api/v1/sql/execute", json_body=body)

    if scenario == "chat":
        body = {
            "message": args.message,
            "session_id": args.session_id or f"load-{index}-{uuid.uuid4().hex[:8]}",
            "datasource": args.datasource or None,
            "stream_response": args.stream_response,
            "interactive": False,
            "max_turns": args.max_turns,
        }
        body = {key: value for key, value in body.items() if value is not None}
        return EndpointCall(name="chat", method="POST", path="/api/v1/chat/stream", json_body=body, stream=True)

    raise AssertionError(f"Unhandled scenario: {args.scenario}")


async def _run_json_call(client: httpx.AsyncClient, call: EndpointCall, timeout: float) -> CallResult:
    started = time.perf_counter()
    try:
        response = await client.request(
            call.method,
            call.path,
            params=call.params,
            json=call.json_body,
            timeout=timeout,
        )
        latency_ms = (time.perf_counter() - started) * 1000
        body = response.content
        ok = 200 <= response.status_code < 400
        error = ""
        if not ok:
            error = body[:300].decode("utf-8", errors="replace")
        return CallResult(
            name=call.name,
            ok=ok,
            status_code=response.status_code,
            latency_ms=latency_ms,
            bytes_read=len(body),
            error=error,
        )
    except Exception as exc:
        latency_ms = (time.perf_counter() - started) * 1000
        return CallResult(name=call.name, ok=False, status_code=None, latency_ms=latency_ms, error=repr(exc))


async def _run_sse_call(client: httpx.AsyncClient, call: EndpointCall, timeout: float) -> CallResult:
    started = time.perf_counter()
    bytes_read = 0
    event_count = 0
    first_event_ms: float | None = None
    try:
        async with client.stream(
            call.method,
            call.path,
            params=call.params,
            json=call.json_body,
            timeout=timeout,
        ) as response:
            async for chunk in response.aiter_bytes():
                if first_event_ms is None:
                    first_event_ms = (time.perf_counter() - started) * 1000
                bytes_read += len(chunk)
                event_count += chunk.count(b"\n\n")
            latency_ms = (time.perf_counter() - started) * 1000
            ok = 200 <= response.status_code < 400
            return CallResult(
                name=call.name,
                ok=ok,
                status_code=response.status_code,
                latency_ms=latency_ms,
                bytes_read=bytes_read,
                sse_events=event_count,
                first_event_ms=first_event_ms,
                error="" if ok else f"HTTP {response.status_code}",
            )
    except Exception as exc:
        latency_ms = (time.perf_counter() - started) * 1000
        return CallResult(
            name=call.name,
            ok=False,
            status_code=None,
            latency_ms=latency_ms,
            bytes_read=bytes_read,
            sse_events=event_count,
            first_event_ms=first_event_ms,
            error=repr(exc),
        )


async def _run_one(client: httpx.AsyncClient, args: argparse.Namespace, index: int) -> CallResult:
    call = _endpoint_for_request(args, index)
    if call.stream:
        return await _run_sse_call(client, call, args.timeout)
    return await _run_json_call(client, call, args.timeout)


async def _run_load(args: argparse.Namespace) -> list[CallResult]:
    queue: asyncio.Queue[int] = asyncio.Queue()
    for index in range(args.requests):
        queue.put_nowait(index)

    limits = httpx.Limits(max_connections=args.concurrency, max_keepalive_connections=args.concurrency)
    async with httpx.AsyncClient(base_url=args.base_url.rstrip("/"), headers=_headers(args), limits=limits) as client:
        results: list[CallResult] = []
        lock = asyncio.Lock()

        async def worker() -> None:
            while True:
                try:
                    index = queue.get_nowait()
                except asyncio.QueueEmpty:
                    return
                result = await _run_one(client, args, index)
                async with lock:
                    results.append(result)
                    if args.verbose:
                        status = result.status_code if result.status_code is not None else "ERR"
                        print(f"{len(results):>4}/{args.requests} {result.name:<7} {status} {result.latency_ms:8.1f} ms")
                queue.task_done()

        worker_count = min(args.concurrency, args.requests)
        await asyncio.gather(*(worker() for _ in range(worker_count)))
        return results


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    ordered = sorted(values)
    rank = (len(ordered) - 1) * percentile
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = rank - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _summarize(results: list[CallResult], elapsed_s: float) -> dict[str, Any]:
    total = len(results)
    failures = [result for result in results if not result.ok]
    latencies = [result.latency_ms for result in results]
    first_events = [result.first_event_ms for result in results if result.first_event_ms is not None]
    status_counts: dict[str, int] = {}
    for result in results:
        key = str(result.status_code) if result.status_code is not None else "exception"
        status_counts[key] = status_counts.get(key, 0) + 1
    return {
        "total": total,
        "success": total - len(failures),
        "failed": len(failures),
        "error_rate": (len(failures) / total) if total else 0.0,
        "elapsed_s": elapsed_s,
        "requests_per_second": (total / elapsed_s) if elapsed_s > 0 else 0.0,
        "status_counts": status_counts,
        "latency_ms": {
            "min": min(latencies) if latencies else 0.0,
            "mean": statistics.fmean(latencies) if latencies else 0.0,
            "p50": _percentile(latencies, 0.50),
            "p95": _percentile(latencies, 0.95),
            "p99": _percentile(latencies, 0.99),
            "max": max(latencies) if latencies else 0.0,
        },
        "first_sse_event_ms": {
            "p50": _percentile(first_events, 0.50),
            "p95": _percentile(first_events, 0.95),
        }
        if first_events
        else None,
        "bytes_read": sum(result.bytes_read for result in results),
        "sse_events": sum(result.sse_events for result in results),
        "sample_errors": [result.error for result in failures[:5]],
    }


def _print_summary(summary: dict[str, Any]) -> None:
    print()
    print("Datus API load test")
    print(f"  total:     {summary['total']}")
    print(f"  success:   {summary['success']}")
    print(f"  failed:    {summary['failed']} ({summary['error_rate'] * 100:.1f}%)")
    print(f"  elapsed:   {summary['elapsed_s']:.2f}s")
    print(f"  rps:       {summary['requests_per_second']:.2f}")
    print(f"  statuses:  {summary['status_counts']}")
    latency = summary["latency_ms"]
    print(
        "  latency:   "
        f"p50={latency['p50']:.1f}ms p95={latency['p95']:.1f}ms "
        f"p99={latency['p99']:.1f}ms max={latency['max']:.1f}ms"
    )
    if summary["first_sse_event_ms"]:
        first = summary["first_sse_event_ms"]
        print(f"  first SSE: p50={first['p50']:.1f}ms p95={first['p95']:.1f}ms")
    print(f"  bytes:     {summary['bytes_read']}")
    if summary["sse_events"]:
        print(f"  SSE events:{summary['sse_events']}")
    if summary["sample_errors"]:
        print("  sample errors:")
        for error in summary["sample_errors"]:
            print(f"    - {error}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Datus API base URL.")
    parser.add_argument(
        "--scenario",
        choices=["status", "catalog", "sql", "chat", "mixed"],
        default="catalog",
        help="Endpoint scenario to exercise.",
    )
    parser.add_argument("--requests", type=int, default=20, help="Total number of requests.")
    parser.add_argument("--concurrency", type=int, default=5, help="Number of concurrent workers.")
    parser.add_argument("--timeout", type=float, default=60.0, help="Per-request timeout in seconds.")
    parser.add_argument("--bearer-token", default="", help="Bearer token. Defaults to DATUS_API_TOKEN or VITE_DEV_ACCESS_TOKEN.")
    parser.add_argument("--header", action="append", help="Extra request header. Repeat or pass comma-separated values.")
    parser.add_argument("--datasource", default="", help="Datasource id for catalog, SQL context, or chat context.")
    parser.add_argument("--database", default="", help="Database name for SQL requests.")
    parser.add_argument("--sql", default="SELECT 1", help="SQL text for the sql scenario.")
    parser.add_argument("--result-format", default="json", choices=["json", "csv", "arrow"], help="SQL result format.")
    parser.add_argument("--message", default="请用一句话回复 ok", help="Message for the chat scenario.")
    parser.add_argument("--session-id", default="", help="Reuse one chat session id instead of creating one per request.")
    parser.add_argument("--stream-response", action="store_true", help="Ask chat to stream model deltas when supported.")
    parser.add_argument("--max-turns", type=int, default=6, help="max_turns value for chat requests.")
    parser.add_argument("--max-error-rate", type=float, default=0.0, help="Allowed failure ratio before exiting non-zero.")
    parser.add_argument("--json-output", action="store_true", help="Print JSON summary instead of text.")
    parser.add_argument("--verbose", action="store_true", help="Print one line per completed request.")
    return parser


def _validate_args(args: argparse.Namespace) -> None:
    if args.requests < 1:
        raise SystemExit("--requests must be at least 1.")
    if args.concurrency < 1:
        raise SystemExit("--concurrency must be at least 1.")
    if args.timeout <= 0:
        raise SystemExit("--timeout must be positive.")
    if not 0 <= args.max_error_rate <= 1:
        raise SystemExit("--max-error-rate must be between 0 and 1.")


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    _validate_args(args)
    started = time.perf_counter()
    results = asyncio.run(_run_load(args))
    elapsed_s = time.perf_counter() - started
    summary = _summarize(results, elapsed_s)
    if args.json_output:
        print(json.dumps({"summary": summary, "results": [asdict(result) for result in results]}, ensure_ascii=False, indent=2))
    else:
        _print_summary(summary)
    return 0 if summary["error_rate"] <= args.max_error_rate else 1


if __name__ == "__main__":
    sys.exit(main())
