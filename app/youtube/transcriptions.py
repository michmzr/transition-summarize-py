
import logging
from app.transcribe.transcription import LANG_CODE, WHISPER_RESPONSE_FORMAT
from app.utils.internet import download_file
from app.youtube.metadata import get_youtube_metadata


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
            # read transcription file and convert to text
            transcription = open(transcription_file, "r").read()
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
