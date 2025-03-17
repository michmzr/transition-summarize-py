import requests
import os


def download_file(url: str, save_dir: str) -> str:
    """Download a file from URL, save it to the specified directory."""
    response = requests.get(url)
    response.raise_for_status()
    os.makedirs(save_dir, exist_ok=True)
    file_path = os.path.join(save_dir, "transcript.vtt")
    with open(file_path, "wb") as f:
        f.write(response.content)
    return file_path
