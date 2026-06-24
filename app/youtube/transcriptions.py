import logging
import re
from html import unescape

from app.transcribe.transcription import LANG_CODE, WHISPER_RESPONSE_FORMAT
from app.utils.internet import download_file
from app.youtube.metadata import get_youtube_metadata


def _format_vtt_timestamp(timestamp: str) -> str:
    time_part = timestamp.split(".", 1)[0]
    parts = time_part.split(":")

    if len(parts) == 3 and parts[0] == "00":
        return f"{parts[1]}:{parts[2]}"

    return time_part


def _clean_vtt_text(text: str) -> str:
    without_tags = re.sub(r"<[^>]+>", "", text)
    return " ".join(unescape(without_tags).split())


def normalize_vtt_transcription(raw_vtt: str) -> str:
    segments = []
    current_start = None
    current_text_lines = []

    for line in raw_vtt.splitlines():
        stripped = line.strip()

        if not stripped:
            if current_start and current_text_lines:
                text = _clean_vtt_text(" ".join(current_text_lines))
                if text:
                    segments.append(f"[{current_start}] {text}")
            current_start = None
            current_text_lines = []
            continue

        if stripped == "WEBVTT" or stripped.startswith(("Kind:", "Language:", "NOTE", "STYLE", "REGION")):
            continue

        if "-->" in stripped:
            current_start = _format_vtt_timestamp(stripped.split("-->", 1)[0].strip())
            current_text_lines = []
            continue

        if current_start:
            current_text_lines.append(stripped)

    if current_start and current_text_lines:
        text = _clean_vtt_text(" ".join(current_text_lines))
        if text:
            segments.append(f"[{current_start}] {text}")

    return "\n".join(segments)


def download_transcription(url: str, lang: LANG_CODE, save_dir: str):
    logging.info(
        f" Using YT transcription: '{url}' for language '{lang}'")
    yt_details = get_youtube_metadata(url)

    if yt_details.subtitles and yt_details.subtitles[lang]:
        logging.info(
            f"YT video has subtitles for language '{lang}'")
        logging.debug(
            f"YT subtitles: {yt_details.subtitles[lang]}")
        logging.debug(
            yt_details.subtitles[lang][WHISPER_RESPONSE_FORMAT.VTT.value])

        subtitle_url = yt_details.subtitles[lang][WHISPER_RESPONSE_FORMAT.VTT.value].url
        if subtitle_url:
            logging.info(
                f"Downloading YT transcription: '{subtitle_url}' for language '{lang}' and video '{url}'")
            transcription_file = download_file(subtitle_url, save_dir)
            with open(transcription_file, "r", encoding="utf-8") as file:
                raw_transcription = file.read()
            transcription = normalize_vtt_transcription(raw_transcription)
            logging.debug(
                f"Downloaded transcription to file {transcription_file}")
            return transcription
        else:
            logging.info(
                f"No subtitles found for language '{lang}' for video '{url}'")
            return None
    else:
        logging.info(
            f"No subtitles found for language '{lang}' and video '{url}'")
        return None
