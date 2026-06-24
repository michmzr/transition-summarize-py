import logging
import random
from typing import Iterable, List

from langchain_community.document_loaders.blob_loaders import FileSystemBlobLoader
from langchain_community.document_loaders.blob_loaders.schema import Blob, BlobLoader


class VideoAudioLoader(BlobLoader):
    """Load video URLs from any yt-dlp-supported platform as audio file(s)."""

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
            "verbose": True,
        }

        trial = 1
        max_trials = 3

        def contains_keywords(exception: Exception, keywords: list) -> bool:
            return any(keyword in str(exception).lower() for keyword in keywords)

        while trial < max_trials:
            logging.debug(f"Download video {self.urls}, trial {trial}/{max_trials}")
            if self.proxy_servers:
                ydl_opts["proxy"] = self.random_proxy()

            retcode = None
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    retcode = ydl.download(self.urls)

                break
            except Exception as e:
                logging.warning(
                    f"Got exception: {e} code={retcode}, trying to download again (trial: {trial}/{max_trials})")

                keywords = ["sign in", "login", "login_required", "bot", "429", "rate limit", "forbidden"]
                if contains_keywords(e, keywords):
                    trial += 1
                    if trial == max_trials:
                        raise e
                else:
                    logging.warning(f"Exception '{e}' does not contain retryable keywords, raising exception higher")
                    raise e

        loader = FileSystemBlobLoader(self.save_dir, glob="*.m4a")
        for blob in loader.yield_blobs():
            yield blob
