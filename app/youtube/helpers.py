def proxy_servers():
    from main import get_settings
    settings = get_settings()
    return get_settings().proxy_servers.split(",") if settings.proxy_servers and settings.use_proxy else None
