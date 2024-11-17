from config import get_settings

def proxy_servers():
    settings = get_settings()
    return get_settings().proxy_servers.split(",") if settings.proxy_servers and settings.use_proxy else None
