import random

import yt_dlp

from models import YoutubeTranscriptionMetadata, YoutubeMetadata
from youtube.helpers import proxy_servers


def get_youtube_metadata(video_url: str):
    info = extract_yt_info(video_url)

    video_all_subtitles = info.get('subtitles', {})
    # if subtitles is not empty, we need to get the transcription metadata
    subtitles_metadata = {}
    if video_all_subtitles:
        for lang_code in video_all_subtitles:
            sub_lang_versions = {}

            for subtitle_version in video_all_subtitles[lang_code]:
                name = ""
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

    channel_url = info.get("channel_url")
    metadata = YoutubeMetadata(
        title=info.get('title', None),
        full_title=info.get('fulltitle', None),
        filesize=info.get('filesize', None),
        duration=info.get("duration"),
        duration_string=info.get("duration_string"),
        description=info.get('description'),
        channel_url=channel_url,
        language=info.get('language', None),
        subtitles=subtitles_metadata,
        available_transcriptions=list(subtitles_metadata.keys()),
        upload_date=info.get("upload_date"),
        thumbnail=info.get("thumbnail", None)
    )

    return metadata


def extract_yt_info(video_url):
    ydl_opts = {
        'skip_download': True,  # We don't want to download the video
        'quiet': True,  # Suppress yt-dlp output
    }

    proxys = proxy_servers()
    if proxys:
        ydl_opts["proxy"] = random.choice(proxys)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url, download=False)

    return info
