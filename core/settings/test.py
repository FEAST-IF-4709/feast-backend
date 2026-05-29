from .base import *  # noqa: F401, F403

DEBUG = True
ALLOWED_HOSTS = ["*"]

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}

REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = []

LOGGING = {"version": 1, "disable_existing_loggers": True, "handlers": {}, "root": {"handlers": []}}
