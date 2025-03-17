import logging

from app.settings import get_settings

def proxy_servers():
    settings = get_settings()
    logging.debug(
        f"getting proxies list - proxy usage flag is { settings.proxy_servers }")
    return get_settings().proxy_servers.split(",") if settings.proxy_servers and settings.use_proxy else None

