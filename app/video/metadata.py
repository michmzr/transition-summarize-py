import logging
import random

import yt_dlp

from app.cache import conditional_lru_cache
from app.models import VideoMetadata, YoutubeTranscriptionMetadata
from app.settings import get_settings
from app.youtube.proxy import proxy_servers


@conditional_lru_cache
def get_video_metadata(video_url: str) -> VideoMetadata:
    info = extract_video_info(video_url)

    video_all_subtitles = info.get('subtitles', {})
    subtitles_metadata = {}
    if video_all_subtitles:
        for lang_code in video_all_subtitles:
            sub_lang_versions = {}

            for subtitle_version in video_all_subtitles[lang_code]:
                if hasattr(subtitle_version, "name"):
                    name = subtitle_version["name"]
                else:
                    name = subtitle_version.get("protocol", "N/A")

                sub_lang_versions[subtitle_version["ext"]] = YoutubeTranscriptionMetadata(
                    ext=subtitle_version["ext"],
                    url=subtitle_version["url"],
                    name=name
                )

            subtitles_metadata[lang_code] = sub_lang_versions

    metadata = VideoMetadata(
        title=info.get('title', ''),
        full_title=info.get('fulltitle', None),
        description=info.get('description', ''),
        duration=info.get('duration'),
        duration_string=info.get('duration_string'),
        uploader=info.get('uploader', None),
        uploader_url=info.get('uploader_url', None) or info.get('channel_url', None),
        platform=info.get('extractor_key', None) or info.get('extractor', None),
        original_url=info.get('original_url', video_url),
        upload_date=info.get('upload_date'),
        thumbnail=info.get('thumbnail', None),
        language=info.get('language', None),
        subtitles=subtitles_metadata,
        available_transcriptions=list(subtitles_metadata.keys()),
    )

    return metadata


def extract_video_info(video_url: str):
    logging.info(f"Extracting video info for {video_url}...")

    ydl_opts = {
        'skip_download': True,
        'quiet': True,
    }

    proxys = proxy_servers()
    if get_settings().use_proxy and proxys:
        proxy = random.choice(proxys)
        ydl_opts["proxy"] = proxy
        logging.debug(f"Using '{proxy}' to get video details.")

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url, download=False)

    return info
