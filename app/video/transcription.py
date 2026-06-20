import logging

import langsmith as ls
from langchain_community.document_loaders.generic import GenericLoader

from app.cache import conditional_lru_cache
from app.settings import get_settings
from app.transcribe.transcription import LANG_CODE, WHISPER_RESPONSE_FORMAT, convert_response_format
from app.transcribe.OpenAIWhisperParser import OpenAIWhisperParser
from app.video.loader import VideoAudioLoader


@ls.traceable(
    run_type="llm",
    name="Video Transcription",
    tags=["video", "transcription"],
    metadata={"flow": "transcription"}
)
@conditional_lru_cache
def video_transcribe(url: str,
                     save_dir: str,
                     lang: LANG_CODE,
                     response_format: WHISPER_RESPONSE_FORMAT):
    logging.info(
        f"Processing video url: {url}, save_dir: {save_dir}, lang: {lang}, response_format: {response_format}")

    settings = get_settings()
    proxy_servers = settings.proxy_servers.split(
        ",") if settings.proxy_servers and settings.use_proxy else None

    logging.debug(
        f"Proxy servers: {proxy_servers} - using proxy: {settings.use_proxy}")

    loader = GenericLoader(VideoAudioLoader([url], save_dir, proxy_servers),
                           OpenAIWhisperParser(api_key=settings.openai_api_key,
                                               language=lang.value,
                                               response_format=convert_response_format(
                                                   response_format),
                                               temperature=0
                                               ))
    docs = loader.load()

    return " ".join([doc.page_content for doc in docs])
