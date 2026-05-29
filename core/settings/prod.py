from .base import *  # noqa: F401, F403

DEBUG = False
CORS_ALLOW_ALL_ORIGINS = False

SPECTACULAR_SETTINGS.update({  # noqa: F405
    "SERVERS": [{"url": env("API_BASE_URL", default="https://api.feast.id")}],  # noqa: F405
})
