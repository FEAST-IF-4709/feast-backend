from pathlib import Path
from datetime import timedelta
import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, []),
    CORS_ALLOWED_ORIGINS=(list, ["http://localhost:5173"]),
)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY")

ALLOWED_HOSTS = env("ALLOWED_HOSTS")

INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # 3rd party
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt",
    "drf_spectacular",
    "channels",

    # FEAST apps
    "apps.users",
    "apps.authentication",
    "apps.tenants",
    "apps.rbac",
    "apps.staff",
    "apps.customers",
    "apps.tables",
    "apps.catalog",
    "apps.orders",
    "apps.payments",
    "apps.kitchen",
    "apps.geolocation",
    "apps.recommendations",
    "apps.analytics",
    "apps.realtime",
]

MIDDLEWARE = [
    "core.middleware.request_id.RequestIdMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.tenant_context.TenantContextMiddleware",
]

AUTH_USER_MODEL = "users.BaseUser"

ROOT_URLCONF = "core.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

ASGI_APPLICATION = "core.asgi.application"

DATABASES = {
    "default": {
        **env.db("DATABASE_URL", default="postgres://postgres:postgres@127.0.0.1:5432/feast_db"),
        "CONN_MAX_AGE": env.int("CONN_MAX_AGE", default=60),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Django REST Framework ---
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.authentication.backends.FeastJWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "core.exceptions.handlers.custom_exception_handler",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}

# --- SimpleJWT ---
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": env("JWT_SIGNING_KEY", default=SECRET_KEY),
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_CLAIM": "user_id",
}

# --- Midtrans ---
MIDTRANS_SERVER_KEY = env("MIDTRANS_SERVER_KEY", default="")
MIDTRANS_CLIENT_KEY = env("MIDTRANS_CLIENT_KEY", default="")
MIDTRANS_IS_PRODUCTION = env.bool("MIDTRANS_IS_PRODUCTION", default=False)

# --- drf-spectacular ---
SPECTACULAR_SETTINGS = {
    "TITLE": "FEAST API",
    "DESCRIPTION": "FEAST F&B Multi-Tenant SaaS API",
    "VERSION": "1.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SECURITY": [{"BearerAuth": []}],
    "POSTPROCESSING_HOOKS": [
        "drf_spectacular.hooks.postprocess_schema_enums",
    ],
    "TAGS": [
        {"name": "Auth", "description": "Authentication and session management"},
        {"name": "Orders", "description": "Order creation and retrieval"},
        {"name": "Payments", "description": "Payment initiation and webhook handling"},
        {"name": "Kitchen", "description": "Kitchen Display System order management"},
        {"name": "Tables", "description": "Table and QR code management"},
        {"name": "RBAC", "description": "Role and permission management"},
        {"name": "Analytics", "description": "Dashboard and revenue analytics"},
        {"name": "Recommendations", "description": "Popular products and promotions"},
        {"name": "Geolocation", "description": "Nearby outlet discovery"},
        {"name": "Customers", "description": "Customer lookup"},
        {"name": "Health", "description": "Service health check"},
    ],
}

# --- Structured Logging ---
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(name)s %(levelname)s %(message)s %(request_id)s",
        },
    },
    "filters": {
        "request_id": {"()": "core.middleware.request_id.RequestIdFilter"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "filters": ["request_id"],
        },
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "django.db.backends": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "apps": {"handlers": ["console"], "level": "DEBUG", "propagate": False},
    },
}

CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGINS")

# --- Cache (Redis) ---
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env("REDIS_URL", default="redis://localhost:6379"),
    }
}

# --- Django Channels ---
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [env("REDIS_URL", default="redis://localhost:6379")],
            "capacity": 1500,
            "expiry": 60,
        },
    },
}

# --- Rate Limiting ---
REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = [
    "rest_framework.throttling.AnonRateThrottle",
    "rest_framework.throttling.UserRateThrottle",
]
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {
    "anon": "60/min",
    "user": "600/min",
    "table_resolve": "30/min",
    "auth_login": "10/min",
    "kitchen_status": "120/min",
    "webhook_midtrans": "1000/min",
}
