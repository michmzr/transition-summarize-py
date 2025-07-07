import requests
import os


def get_url_content(url: str) -> str:
    """Download a file from URL, save it to the specified directory."""

    response = requests.get(url)
    response.raise_for_status()

    # Return file content instead of saving it to the file system
    return response.content
