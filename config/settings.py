from decimal import Decimal
from pathlib import Path
import ipaddress
import os

from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured

from finanzas.product import edition_features, normalize_edition

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_list(name, default=""):
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


def env_bool(name, default=False):
    return os.getenv(name, "1" if default else "0").strip().lower() in {"1", "true", "yes", "on"}


def env_int(name, default):
    raw_value = os.getenv(name)
    if raw_value in (None, ""):
        return default
    try:
        return int(raw_value)
    except ValueError as exc:
        raise ImproperlyConfigured(f"{name} debe ser un numero entero.") from exc


DEBUG = env_bool("DJANGO_DEBUG", False)
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "dev-only-change-me"
    else:
        raise ImproperlyConfigured("Define DJANGO_SECRET_KEY cuando DJANGO_DEBUG=0.")
elif not DEBUG and (
    SECRET_KEY == "dev-only-change-me"
    or SECRET_KEY == "replace-this-with-a-unique-secret-key-of-at-least-50-random-characters"
    or len(SECRET_KEY) < 50
):
    raise ImproperlyConfigured("DJANGO_SECRET_KEY debe ser unica, privada y tener al menos 50 caracteres en produccion.")
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")
APP_EDITION = normalize_edition(os.getenv("SAAS_EDITION", "demo"))
APP_FEATURES = edition_features(APP_EDITION)
APP_NAME = os.getenv("SAAS_APP_NAME", "Moneta")
APP_DESCRIPTION_ES = os.getenv("SAAS_APP_DESCRIPTION_ES", "Moneta - finanzas personales, contabilidad y flujo de caja.")
APP_DESCRIPTION_EN = os.getenv("SAAS_APP_DESCRIPTION_EN", "Moneta - personal finance, accounting and cash flow.")
APP_FAVICON = os.getenv("SAAS_APP_FAVICON", "img/moneta_favicon.png")
APP_OG_IMAGE = os.getenv("SAAS_APP_OG_IMAGE", "img/moneta_logo.png")
APP_LOGO_LIGHT = os.getenv("SAAS_APP_LOGO_LIGHT", "img/moneta_icon_light.png")
APP_LOGO_DARK = os.getenv("SAAS_APP_LOGO_DARK", "img/moneta_icon_dark.png")
APP_LOGIN_TITLE_ES = os.getenv("SAAS_LOGIN_TITLE_ES", "Ingresar")
APP_LOGIN_TITLE_EN = os.getenv("SAAS_LOGIN_TITLE_EN", "Sign in")
APP_LOGIN_DESCRIPTION_ES = os.getenv(
    "SAAS_LOGIN_DESCRIPTION_ES",
    "Registra tus finanzas, deuda y capital desde un solo panel.",
)
APP_LOGIN_DESCRIPTION_EN = os.getenv(
    "SAAS_LOGIN_DESCRIPTION_EN",
    "Track finance, debt and capital from a single workspace.",
)
MONETA_FECI_ANNUAL_RATE_PERCENT = Decimal(os.getenv("MONETA_FECI_ANNUAL_RATE_PERCENT", "1.00"))
MONETA_TRUST_X_FORWARDED_FOR = env_bool("MONETA_TRUST_X_FORWARDED_FOR", False)
MONETA_TRUSTED_PROXY_CIDRS = env_list("MONETA_TRUSTED_PROXY_CIDRS")
try:
    for trusted_proxy_cidr in MONETA_TRUSTED_PROXY_CIDRS:
        ipaddress.ip_network(trusted_proxy_cidr, strict=False)
except ValueError as exc:
    raise ImproperlyConfigured("MONETA_TRUSTED_PROXY_CIDRS contiene una red no valida.") from exc
if MONETA_TRUST_X_FORWARDED_FOR and not MONETA_TRUSTED_PROXY_CIDRS:
    raise ImproperlyConfigured(
        "Define MONETA_TRUSTED_PROXY_CIDRS cuando MONETA_TRUST_X_FORWARDED_FOR=1."
    )
MONETA_WEB_SETUP_ENABLED = env_bool("MONETA_WEB_SETUP_ENABLED", False)
MONETA_SETUP_TOKEN = os.getenv("MONETA_SETUP_TOKEN", "")
if MONETA_WEB_SETUP_ENABLED and len(MONETA_SETUP_TOKEN) < 32:
    raise ImproperlyConfigured(
        "MONETA_SETUP_TOKEN debe tener al menos 32 caracteres cuando MONETA_WEB_SETUP_ENABLED=1."
    )
MONETA_LOGIN_MAX_ATTEMPTS = env_int("MONETA_LOGIN_MAX_ATTEMPTS", 10)
MONETA_LOGIN_LOCKOUT_SECONDS = env_int("MONETA_LOGIN_LOCKOUT_SECONDS", 900)
MONETA_RECURRING_BATCH_SIZE = env_int("MONETA_RECURRING_BATCH_SIZE", 100)
MONETA_RECURRING_MAX_CYCLES = env_int("MONETA_RECURRING_MAX_CYCLES", 24)
for setting_name, setting_value in (
    ("MONETA_LOGIN_MAX_ATTEMPTS", MONETA_LOGIN_MAX_ATTEMPTS),
    ("MONETA_LOGIN_LOCKOUT_SECONDS", MONETA_LOGIN_LOCKOUT_SECONDS),
    ("MONETA_RECURRING_BATCH_SIZE", MONETA_RECURRING_BATCH_SIZE),
    ("MONETA_RECURRING_MAX_CYCLES", MONETA_RECURRING_MAX_CYCLES),
):
    if setting_value < 1:
        raise ImproperlyConfigured(f"{setting_name} debe ser mayor que cero.")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "finanzas",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "config.middleware.SecurityHeadersMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "finanzas.context_processors.product_context",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": os.getenv("DB_ENGINE", "django.db.backends.sqlite3"),
        "NAME": os.getenv("DB_NAME", BASE_DIR / "db.sqlite3"),
        "USER": os.getenv("DB_USER", ""),
        "PASSWORD": os.getenv("DB_PASSWORD", ""),
        "HOST": os.getenv("DB_HOST", ""),
        "PORT": os.getenv("DB_PORT", ""),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es-pa"
LANGUAGES = [
    ("es", "Español"),
    ("en", "English"),
]
TIME_ZONE = "America/Panama"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

_cache_backend = os.getenv("DJANGO_CACHE_BACKEND", "locmem" if DEBUG else "file")
if _cache_backend == "db":
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.db.DatabaseCache",
            "LOCATION": "django_cache",
        }
    }
elif _cache_backend == "file":
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
            "LOCATION": BASE_DIR / ".cache",
        }
    }
elif _cache_backend == "redis":
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": os.getenv("DJANGO_CACHE_REDIS_URL", "redis://127.0.0.1:6379/1"),
        }
    }
# else: LocMemCache (Django default) — single-process only

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "structured": {
            "format": "{asctime} {levelname} {name} {message}",
            "style": "{",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "structured",
        }
    },
    "loggers": {
        "finanzas": {
            "handlers": ["console"],
            "level": os.getenv("MONETA_LOG_LEVEL", "INFO"),
            "propagate": False,
        }
    },
}

LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/accounts/login/"
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

if env_bool("DJANGO_SECURE_PROXY_SSL_HEADER", False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

if not DEBUG:
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
    SECURE_HSTS_SECONDS = env_int("DJANGO_SECURE_HSTS_SECONDS", 31536000)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
