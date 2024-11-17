from settings import get_settings


def get_downloads_path():
    settings = get_settings()
    return settings.data_dir 