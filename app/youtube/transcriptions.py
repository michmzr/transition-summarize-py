import logging
from app.transcribe.transcription import LANG_CODE, WHISPER_RESPONSE_FORMAT
from app.utils.internet import download_file
from app.youtube.metadata import get_youtube_metadata


def download_transcription(
        url: str, lang: LANG_CODE,
        transcription_format: WHISPER_RESPONSE_FORMAT,
        save_dir: str):

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
                transcription_file = download_file(subtitle_url, save_dir)

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
