from functools import lru_cache, wraps

from settings import get_settings


def conditional_lru_cache(func):
    if get_settings().disable_cache:
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        return wrapper
    else:
        return lru_cache()(func)
