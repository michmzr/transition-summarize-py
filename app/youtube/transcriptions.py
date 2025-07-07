from http import HTTPStatus
import json
import logging
from typing import List
from app.settings import get_settings
from app.transcribe.transcription import LANG_CODE, WHISPER_RESPONSE_FORMAT
from app.utils.internet import get_url_content
from app.youtube.metadata import get_youtube_metadata
import requests


@DeprecationWarning
def download_transcription(url: str, lang: LANG_CODE, transcription_format: WHISPER_RESPONSE_FORMAT) -> str | None:
    logging.info(
        f" Using YT transcription: '{url}' for language '{lang}' and transcription format '{transcription_format}'")
    yt_details = get_youtube_metadata(url)

    lang_code = lang.value
    if yt_details.subtitles and lang_code in yt_details.subtitles:
        logging.info(
            f"YT video has subtitles for language '{lang_code}'")
        logging.debug(
            f"YT available subtitles: {yt_details.subtitles[lang_code]}")

        if transcription_format.value in yt_details.subtitles[lang_code]:
            subtitle_url = yt_details.subtitles[lang_code][transcription_format.value].url

            if subtitle_url:
                logging.info(
                    f"Downloaded YT transcription: '{subtitle_url}' for language '{lang}' and video '{url}'")

                transcription = get_url_content(subtitle_url)
                logging.debug(
                    f"Downloaded transcription content - size: {len(transcription)}, format: {transcription_format}, url: {subtitle_url}")
                return transcription
            else:
                logging.info(
                    f"No subtitles found for language '{lang}' for video '{url}'")
                return None
    else:
        logging.info(
            f"No subtitles found for language '{lang}' and video '{url}'")
        return None


def download_transcription_from_yt(yt_url: str, lang: LANG_CODE) -> str | None:
    """
    Download transcription from YouTube video.
    """
    transcription = _supadata_transcription(yt_url, lang)
    if transcription:
        return transcription
    else:
        return None


def _supadata_transcription(yt_url: str, lang: LANG_CODE) -> str | None:
    """
    Use Supadata API to get the transcription of a YouTube video.

    Docs api: https://supadata.ai/documentation/youtube/get-transcript

    Example response:
    ```json
    {
    "lang": "pl",
    "availableLangs": [
        "pl"
    ],
    "content": "The world you see is not real –  you're not l...."
    }
    ```
    """

    logging.info(
        f"Getting transcription from Supadata API for YouTube video: '{yt_url}' and language: '{lang}'")

    url = get_settings().supadata_yt_transcription_host + "/v1/youtube/transcript"

    payload = {"url": yt_url, "lang": lang.value, "text": True}
    headers = {
        "x-api-key": get_settings().supadata_yt_transcription_api_key,
        "Content-Type": "application/json"
    }

    response = requests.get(url, params=payload, headers=headers)

    if (response.status_code == HTTPStatus.OK):
        response_data = response.json()

        logging.info(
            f"Supadata API response - lang: {response_data.get('lang')},available langs: {response_data.get('availableLangs')}")

        return json.dumps(response_data.get("content"))
    else:
        logging.error(
            f"Error getting transcription from Supadata API: {response.status_code} response: {response.text}, headers: {response.headers}")
        return None
