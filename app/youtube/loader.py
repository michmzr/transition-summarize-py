import logging
import random
from typing import Iterable, List

from langchain_community.document_loaders.blob_loaders import FileSystemBlobLoader
from langchain_community.document_loaders.blob_loaders.schema import Blob, BlobLoader


class YoutubeAudioLoader(BlobLoader):
    """Load YouTube urls as audio file(s)."""

    def __init__(self, urls: List[str], save_dir: str, proxy_servers: List[str] = None):

        if not isinstance(urls, list):
            raise TypeError("urls must be a list")

        self.urls = urls
        self.save_dir = save_dir
        self.proxy_servers = proxy_servers

    def random_proxy(self):
        return random.choice(self.proxy_servers)


    def yield_blobs(self) -> Iterable[Blob]:
        """Yield audio blobs for each url."""

        try:
            import yt_dlp
        except ImportError:
            raise ImportError(
                "yt_dlp package not found, please install it with "
                "`pip install yt_dlp`"
            )

        # Use yt_dlp to download audio given a YouTube url
        ydl_opts = {
            "format": "m4a/bestaudio/best",
            "noplaylist": True,
            "outtmpl": self.save_dir + "/%(title)s.%(ext)s",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "m4a",
                }
            ],
            'netrc': True,
            'verbose': True,
            "extractor_args": {"youtube": "youtube:player_skip=webpage"}
        }

        trial = 1
        max_trials = 3

        def contains_keywords(exception: Exception, keywords: list) -> bool:
            return any(keyword in str(exception).lower() for keyword in keywords)

        while trial < max_trials:
            logging.debug(f"Download youtube video {self.urls}, trial {trial}/{max_trials}")
            if (self.proxy_servers):
                ydl_opts["proxy"] = self.random_proxy()

            retcode = None
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    retcode = ydl.download(self.urls)

                break
            except Exception as e:
                logging.warning(
                    f"Got exception: {e} code={retcode}, trying to download again (trial: {trial}/{max_trials})")

                # Retry if exception message contains sign in error message
                keywords = ["sign in", "login", "login_required", "bot", "429"]
                if contains_keywords(e, keywords):
                    trial += 1
                    if trial == max_trials:
                        raise e
                else:
                    logging.warning(f"Exception '{e}' does not contain keywords: '{keywords}', raising exception higher")
                    raise e

        # Yield the written blobs
        loader = FileSystemBlobLoader(self.save_dir, glob="*.m4a")
        for blob in loader.yield_blobs():
            yield blob
