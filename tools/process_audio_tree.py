#!/usr/bin/env python3
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


AUDIO_EXTENSIONS = {
    ".aac",
    ".aif",
    ".aiff",
    ".flac",
    ".m4a",
    ".mp3",
    ".mp4",
    ".ogg",
    ".opus",
    ".wav",
    ".wma",
}

DEFAULT_BASE_URL = "https://summarizer.cybershu.eu"
MIME_TYPES = {
    ".aac": "audio/aac",
    ".aif": "audio/aiff",
    ".aiff": "audio/aiff",
    ".flac": "audio/flac",
    ".m4a": "audio/mp4",
    ".mp3": "audio/mpeg",
    ".mp4": "video/mp4",
    ".ogg": "audio/ogg",
    ".opus": "audio/ogg",
    ".wav": "audio/wav",
    ".wma": "audio/x-ms-wma",
}
TIMESTAMP_RE = re.compile(
    r"(?P<h>\d{2}):(?P<m>\d{2}):(?P<s>\d{2})[,.](?P<ms>\d{3})"
)


@dataclass
class Validation:
    ok: bool
    message: str
    details: dict


def eprint(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def discover_audio_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS
    )


def read_text(path: Path, limit: int | None = None) -> str:
    data = path.read_text(encoding="utf-8", errors="replace")
    if limit is None:
        return data
    return data[:limit]


def looks_like_api_error(path: Path) -> str | None:
    text = read_text(path, 4096).strip()
    if not text:
        return "empty response"
    if text.startswith("{"):
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return None
        for key in ("detail", "error", "message"):
            if key in payload:
                return f"API error: {payload[key]}"
    lowered = text.lower()
    if "unauthorized" in lowered or "not authenticated" in lowered:
        return "authentication error in response"
    if "internal server error" in lowered:
        return "server error in response"
    return None


def timestamp_to_seconds(match: re.Match[str]) -> float:
    return (
        int(match.group("h")) * 3600
        + int(match.group("m")) * 60
        + int(match.group("s"))
        + int(match.group("ms")) / 1000
    )


def audio_duration_seconds(path: Path) -> float | None:
    if not shutil.which("ffprobe"):
        return None
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        return None
    try:
        return float(result.stdout.strip())
    except ValueError:
        return None


def validate_srt(path: Path, audio_path: Path) -> Validation:
    api_error = looks_like_api_error(path)
    if api_error:
        return Validation(False, api_error, {})

    text = read_text(path)
    timestamp_lines = [line for line in text.splitlines() if "-->" in line]
    matches = list(TIMESTAMP_RE.finditer(text))
    if not timestamp_lines or len(matches) < 2:
        return Validation(False, "SRT has no valid timestamp cues", {})

    times = [timestamp_to_seconds(match) for match in matches]
    end_times = times[1::2]
    monotonic = all(a <= b + 0.001 for a, b in zip(end_times, end_times[1:]))
    duration = audio_duration_seconds(audio_path)
    max_end = max(end_times) if end_times else 0.0
    details = {
        "cue_count": len(timestamp_lines),
        "last_srt_second": round(max_end, 3),
    }
    if duration is not None:
        details["audio_duration_second"] = round(duration, 3)
        details["coverage_ratio"] = round(max_end / duration, 3) if duration > 0 else 0
        if max_end > duration + 90:
            return Validation(False, "SRT timestamps exceed audio duration by more than 90s", details)
        if duration > 60 and max_end < duration * 0.25:
            return Validation(False, "SRT covers less than 25% of audio duration", details)
    if not monotonic:
        return Validation(False, "SRT cue end timestamps are not monotonic", details)
    return Validation(True, "valid SRT", details)


def validate_markdown(path: Path) -> Validation:
    api_error = looks_like_api_error(path)
    if api_error:
        return Validation(False, api_error, {})
    text = read_text(path).strip()
    if len(text) < 80:
        return Validation(False, "summary is too short", {"char_count": len(text)})
    return Validation(True, "valid summary", {"char_count": len(text)})


def curl_config(token: str) -> bytes:
    return (
        f'header = "Authorization: Bearer {token}"\n'
        'header = "Accept: text/plain"\n'
    ).encode("utf-8")


def run_curl(
    token: str,
    base_url: str,
    endpoint: str,
    fields: Iterable[tuple[str, str]],
    uploaded_file: Path | None,
    output_path: Path,
) -> None:
    url = f"{base_url.rstrip('/')}{endpoint}"
    cmd = [
        "curl",
        "--max-time",
        "0",
        "--no-buffer",
        "--show-error",
        "--fail-with-body",
        "-X",
        "POST",
        url,
        "--config",
        "-",
        "-o",
        str(output_path),
        "--write-out",
        "%{http_code}",
    ]
    if uploaded_file is not None:
        mime_type = MIME_TYPES.get(uploaded_file.suffix.lower(), "application/octet-stream")
        cmd.extend(["-F", f"uploaded_file=@{uploaded_file};type={mime_type}"])
    for key, value in fields:
        cmd.extend(["-F", f"{key}={value}"])

    result = subprocess.run(
        cmd,
        input=curl_config(token),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    status_text = result.stdout.decode("utf-8", errors="replace").strip()
    try:
        status_code = int(status_text[-3:])
    except ValueError:
        status_code = 0
    if result.returncode != 0 or status_code < 200 or status_code >= 300:
        body = read_text(output_path, 2000) if output_path.exists() else ""
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(
            f"curl failed for {endpoint}; status={status_code}; stderr={stderr}; body={body[:500]}"
        )


def run_health(token: str, base_url: str) -> None:
    with tempfile.NamedTemporaryFile() as tmp:
        cmd = [
            "curl",
            "--max-time",
            "30",
            "--show-error",
            "--fail-with-body",
            f"{base_url.rstrip('/')}/health",
            "--config",
            "-",
            "-o",
            tmp.name,
            "--write-out",
            "%{http_code}",
        ]
        result = subprocess.run(
            cmd,
            input=curl_config(token),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        status_text = result.stdout.decode("utf-8", errors="replace").strip()
        try:
            status_code = int(status_text[-3:])
        except ValueError:
            status_code = 0
        if result.returncode != 0 or status_code < 200 or status_code >= 300:
            body = Path(tmp.name).read_text(encoding="utf-8", errors="replace")
            stderr = result.stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(
                f"health check failed; status={status_code}; stderr={stderr}; body={body[:500]}"
            )


def atomic_api_write(
    token: str,
    base_url: str,
    endpoint: str,
    fields: Iterable[tuple[str, str]],
    uploaded_file: Path,
    final_path: Path,
    validator,
) -> Validation:
    tmp_path = final_path.with_name(f".{final_path.name}.tmp.{os.getpid()}")
    try:
        run_curl(token, base_url, endpoint, fields, uploaded_file, tmp_path)
        validation = validator(tmp_path)
        if not validation.ok:
            raise RuntimeError(validation.message)
        tmp_path.replace(final_path)
        return validation
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        raise


def process_file(
    token: str,
    base_url: str,
    audio_path: Path,
    lang: str,
    transcribe_format_field: str,
) -> dict:
    srt_path = audio_path.with_suffix(".srt")
    md_path = audio_path.with_suffix(".md")
    result = {
        "audio": str(audio_path),
        "transcript": str(srt_path),
        "summary": str(md_path),
        "transcript_validation": None,
        "summary_validation": None,
    }

    transcript_validation = atomic_api_write(
        token,
        base_url,
        "/audio/transcribe",
        (("lang", lang), (transcribe_format_field, "srt")),
        audio_path,
        srt_path,
        lambda candidate: validate_srt(candidate, audio_path),
    )
    result["transcript_validation"] = transcript_validation.details

    summary_validation = atomic_api_write(
        token,
        base_url,
        "/audio/summary",
        (("lang", lang), ("type", "detailed")),
        audio_path,
        md_path,
        validate_markdown,
    )
    result["summary_validation"] = summary_validation.details
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--lang", default="pl")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--transcribe-format-field", default="response_format")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--from-index", type=int, default=1)
    parser.add_argument("--health-only", action="store_true")
    args = parser.parse_args()

    token = os.environ.get("AVSUMMARIZER_TOKEN")
    if not token:
        eprint("AVSUMMARIZER_TOKEN is not set")
        return 2

    root = Path(args.root).expanduser()
    if not root.is_dir():
        eprint(f"Root directory does not exist: {root}")
        return 2

    run_health(token, args.base_url)
    if args.health_only:
        print("HEALTH_OK", flush=True)
        return 0

    audio_files = discover_audio_files(root)
    if args.from_index > 1:
        audio_files = audio_files[args.from_index - 1 :]
    if args.limit > 0:
        audio_files = audio_files[: args.limit]
    print(f"FOUND_AUDIO_FILES {len(audio_files)}", flush=True)

    successes: list[dict] = []
    failures: list[dict] = []
    for index, audio_path in enumerate(audio_files, start=1):
        print(f"START {index}/{len(audio_files)} {audio_path}", flush=True)
        try:
            result = process_file(
                token,
                args.base_url,
                audio_path,
                args.lang,
                args.transcribe_format_field,
            )
        except Exception as exc:
            failures.append({"audio": str(audio_path), "error": str(exc)})
            print(f"FAIL {index}/{len(audio_files)} {audio_path}: {exc}", flush=True)
            continue
        successes.append(result)
        print(
            "OK "
            f"{index}/{len(audio_files)} "
            f"srt_cues={result['transcript_validation'].get('cue_count')} "
            f"summary_chars={result['summary_validation'].get('char_count')} "
            f"{audio_path}",
            flush=True,
        )

    print("RESULT_JSON_BEGIN", flush=True)
    print(
        json.dumps(
            {
                "success_count": len(successes),
                "failure_count": len(failures),
                "successes": successes,
                "failures": failures,
            },
            ensure_ascii=False,
            indent=2,
        ),
        flush=True,
    )
    print("RESULT_JSON_END", flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
