#!/usr/bin/env python3
"""Serve a local review UI for unresolved double-blank voice recordings."""

from __future__ import annotations

import argparse
import json
import os
import threading
import webbrowser
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse


REPORT_PATH = Path("migration-reports/gpt-transcribe-double-blank-review.json")
DECISIONS_PATH = Path("migration-reports/gpt-transcribe-double-blank-decisions.json")
UI_PATH = Path("tools/double_blank_review_ui")
VALID_STATUSES = {"transcript", "nonspeech", "hold"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_queue(report_path: Path) -> list[dict[str, Any]]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    held = report.get("held")
    if not isinstance(held, list):
        raise ValueError(f"{report_path} does not contain a held array")
    for row in held:
        if not isinstance(row, dict) or not isinstance(row.get("recordingId"), str):
            raise ValueError(f"{report_path} contains an invalid held row")
    return held


class DecisionStore:
    def __init__(self, path: Path, valid_recording_ids: list[str]) -> None:
        self.path = path
        self.recording_order = valid_recording_ids
        self.valid_recording_ids = set(valid_recording_ids)
        self.lock = threading.Lock()
        self.decisions: dict[str, dict[str, Any]] = {}
        self.updated_at: str | None = None
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        document = json.loads(self.path.read_text(encoding="utf-8"))
        for decision in document.get("decisions", []):
            recording_id = decision.get("recordingId")
            if recording_id in self.valid_recording_ids:
                self.decisions[recording_id] = decision
        self.updated_at = document.get("updatedAt")

    def document(self) -> dict[str, Any]:
        order = {recording_id: index for index, recording_id in enumerate(self.recording_order)}
        decisions = sorted(
            self.decisions.values(),
            key=lambda decision: order.get(decision["recordingId"], len(order)),
        )
        return {
            "schemaVersion": 1,
            "sourceReport": REPORT_PATH.as_posix(),
            "updatedAt": self.updated_at,
            "decisions": decisions,
        }

    def validate(self, recording_id: str, payload: Any) -> dict[str, Any]:
        if recording_id not in self.valid_recording_ids:
            raise ValueError("Unknown recordingId")
        if not isinstance(payload, dict):
            raise ValueError("Decision must be a JSON object")
        status = payload.get("status")
        if status not in VALID_STATUSES:
            raise ValueError("status must be transcript, nonspeech, or hold")
        text = payload.get("text", "")
        notes = payload.get("notes", "")
        preferred_hash = payload.get("preferredHash")
        if not isinstance(text, str) or not isinstance(notes, str):
            raise ValueError("text and notes must be strings")
        text = text.strip()
        notes = notes.strip()
        if status == "transcript" and not text:
            raise ValueError("A transcript decision requires nonblank text")
        if status == "nonspeech":
            text = ""
        if preferred_hash is not None and not isinstance(preferred_hash, str):
            raise ValueError("preferredHash must be a string or null")
        return {
            "recordingId": recording_id,
            "status": status,
            "text": text,
            "notes": notes,
            "preferredHash": preferred_hash,
            "reviewedAt": utc_now(),
        }

    def put(self, recording_id: str, payload: Any) -> dict[str, Any]:
        decision = self.validate(recording_id, payload)
        with self.lock:
            self.decisions[recording_id] = decision
            self.updated_at = decision["reviewedAt"]
            self._write()
        return decision

    def delete(self, recording_id: str) -> None:
        if recording_id not in self.valid_recording_ids:
            raise ValueError("Unknown recordingId")
        with self.lock:
            self.decisions.pop(recording_id, None)
            self.updated_at = utc_now()
            self._write()

    def _write(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(self.document(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        os.replace(temporary, self.path)


class ReviewServer(ThreadingHTTPServer):
    def __init__(
        self,
        address: tuple[str, int],
        handler: type[BaseHTTPRequestHandler],
        queue: list[dict[str, Any]],
        store: DecisionStore,
        ui_path: Path,
    ) -> None:
        super().__init__(address, handler)
        self.queue = queue
        self.store = store
        self.ui_path = ui_path


class ReviewHandler(BaseHTTPRequestHandler):
    server: ReviewServer

    def log_message(self, format: str, *args: Any) -> None:
        print(f"{self.address_string()} - {format % args}")

    def _json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _error(self, status: HTTPStatus, message: str) -> None:
        self._json({"error": message}, status)

    def _read_json(self) -> Any:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("Invalid Content-Length") from exc
        if length > 1_000_000:
            raise ValueError("Request body is too large")
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Request body must be valid JSON") from exc

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/state":
            self._json({"queue": self.server.queue, "review": self.server.store.document()})
            return
        if path == "/api/export":
            body = (json.dumps(self.server.store.document(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Disposition", 'attachment; filename="gpt-transcribe-double-blank-decisions.json"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self._serve_static(path)

    def do_PUT(self) -> None:
        prefix = "/api/decisions/"
        path = urlparse(self.path).path
        if not path.startswith(prefix):
            self._error(HTTPStatus.NOT_FOUND, "Not found")
            return
        recording_id = unquote(path[len(prefix) :])
        try:
            decision = self.server.store.put(recording_id, self._read_json())
        except ValueError as exc:
            self._error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self._json(decision)

    def do_DELETE(self) -> None:
        prefix = "/api/decisions/"
        path = urlparse(self.path).path
        if not path.startswith(prefix):
            self._error(HTTPStatus.NOT_FOUND, "Not found")
            return
        try:
            self.server.store.delete(unquote(path[len(prefix) :]))
        except ValueError as exc:
            self._error(HTTPStatus.BAD_REQUEST, str(exc))
            return
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

    def _serve_static(self, request_path: str) -> None:
        relative = "index.html" if request_path == "/" else unquote(request_path.lstrip("/"))
        target = (self.server.ui_path / relative).resolve()
        ui_root = self.server.ui_path.resolve()
        if target != ui_root and ui_root not in target.parents:
            self._error(HTTPStatus.NOT_FOUND, "Not found")
            return
        if not target.is_file():
            self._error(HTTPStatus.NOT_FOUND, "Not found")
            return
        content_types = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "text/javascript; charset=utf-8",
            ".svg": "image/svg+xml",
        }
        body = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_types.get(target.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    parser.add_argument("--decisions", type=Path, default=DECISIONS_PATH)
    parser.add_argument("--open", action="store_true", help="Open the reviewer in the default browser")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo = Path(__file__).resolve().parent.parent
    report_path = args.report if args.report.is_absolute() else repo / args.report
    decisions_path = args.decisions if args.decisions.is_absolute() else repo / args.decisions
    queue = load_queue(report_path)
    recording_ids = [row["recordingId"] for row in queue]
    store = DecisionStore(decisions_path, recording_ids)
    server = ReviewServer((args.host, args.port), ReviewHandler, queue, store, repo / UI_PATH)
    url = f"http://{args.host}:{server.server_port}/"
    print(f"Reviewing {len(queue)} recordings at {url}")
    print(f"Decisions save to {decisions_path}")
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping reviewer.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
