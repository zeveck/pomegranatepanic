#!/usr/bin/env python3
"""Validate Anim8gen candidate JSONL and frame review records."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


CANDIDATE_REVIEW_STATUSES = {
    "candidate",
    "accepted",
    "rejected-pose",
    "rejected-identity",
    "rejected-background",
    "rejected-artifact",
    "accepted-with-warning",
}
DECISIONS = {
    "accepted",
    "accepted-with-warning",
    "rejected-pose",
    "rejected-identity",
    "rejected-background",
    "rejected-artifact",
}
PACKAGE_STATUSES = {"initialized", "complete", "partial", "blocked"}
REQUIRED_CANDIDATE_FIELDS = {
    "prompt",
    "frameIndex",
    "outputPath",
    "retry",
    "reviewStatus",
    "reviewNotes",
}
REQUIRED_REVIEW_FIELDS = {
    "frameIndex",
    "frameLabel",
    "candidatePath",
    "retry",
    "poseVerdict",
    "identityVerdict",
    "cameraVerdict",
    "hygieneVerdict",
    "backgroundVerdict",
    "decision",
    "notes",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", required=True, help="Path to manifests/candidates.jsonl.")
    parser.add_argument("--reviews", required=True, help="Path to review/frame-reviews.json.")
    return parser.parse_args()


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{path}: invalid JSON: {exc}") from exc


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"{path}:{line_number}: invalid JSON: {exc}") from exc
        if not isinstance(record, dict):
            raise SystemExit(f"{path}:{line_number}: candidate record must be an object")
        records.append(record)
    if not records:
        raise SystemExit(f"{path}: candidate manifest must contain at least one record")
    return records


def require_text(record: dict[str, Any], key: str, where: str) -> None:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SystemExit(f"{where}: {key} must be a non-empty string")


def validate_candidates(path: Path) -> list[dict[str, Any]]:
    records = load_jsonl(path)
    for index, record in enumerate(records):
        where = f"{path}:record {index}"
        missing = sorted(REQUIRED_CANDIDATE_FIELDS - record.keys())
        if missing:
            raise SystemExit(f"{where}: missing fields: {', '.join(missing)}")
        require_text(record, "prompt", where)
        require_text(record, "outputPath", where)
        require_text(record, "reviewNotes", where)
        if not isinstance(record["frameIndex"], int) or record["frameIndex"] < 0:
            raise SystemExit(f"{where}: frameIndex must be a non-negative integer")
        if not isinstance(record["retry"], int) or record["retry"] < 1:
            raise SystemExit(f"{where}: retry must be a positive integer")
        if record["reviewStatus"] not in CANDIDATE_REVIEW_STATUSES:
            raise SystemExit(f"{where}: invalid reviewStatus {record['reviewStatus']!r}")
    return records


def validate_reviews(path: Path, candidates: list[dict[str, Any]]) -> None:
    payload = load_json(path)
    if not isinstance(payload, dict):
        raise SystemExit(f"{path}: review payload must be an object")
    if payload.get("packageStatus") not in PACKAGE_STATUSES:
        raise SystemExit(f"{path}: packageStatus must be one of {sorted(PACKAGE_STATUSES)}")
    frames = payload.get("frames")
    if not isinstance(frames, list):
        raise SystemExit(f"{path}: frames must be an array")

    candidate_keys = {
        (record["frameIndex"], record["retry"], record["outputPath"])
        for record in candidates
    }
    for index, frame in enumerate(frames):
        where = f"{path}:frames[{index}]"
        if not isinstance(frame, dict):
            raise SystemExit(f"{where}: review frame must be an object")
        missing = sorted(REQUIRED_REVIEW_FIELDS - frame.keys())
        if missing:
            raise SystemExit(f"{where}: missing fields: {', '.join(missing)}")
        for key in (
            "frameLabel",
            "candidatePath",
            "poseVerdict",
            "identityVerdict",
            "cameraVerdict",
            "hygieneVerdict",
            "backgroundVerdict",
            "notes",
        ):
            require_text(frame, key, where)
        if not isinstance(frame["frameIndex"], int) or frame["frameIndex"] < 0:
            raise SystemExit(f"{where}: frameIndex must be a non-negative integer")
        if not isinstance(frame["retry"], int) or frame["retry"] < 1:
            raise SystemExit(f"{where}: retry must be a positive integer")
        if frame["decision"] not in DECISIONS:
            raise SystemExit(f"{where}: invalid decision {frame['decision']!r}")
        key = (frame["frameIndex"], frame["retry"], frame["candidatePath"])
        if key not in candidate_keys:
            raise SystemExit(f"{where}: no matching candidate record for {key!r}")


def main() -> None:
    args = parse_args()
    candidates = validate_candidates(Path(args.candidates))
    validate_reviews(Path(args.reviews), candidates)
    print("review records ok")


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        sys.exit(1)
