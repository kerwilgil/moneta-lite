from pathlib import Path
import os

from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured

from finanzas.product import edition_features, normalize_edition

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_list(name, default=""):
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


DEBUG = os.getenv("DJANGO_DEBUG", "1") == "1"
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "dev-only-change-me"
    else:
        raise ImproperlyConfigured("Define DJANGO_SECRET_KEY cuando DJANGO_DEBUG=0.")
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")
APP_EDITION = normalize_edition(os.getenv("SAAS_EDITION", "lite"))
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
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/accounts/login/"
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

if os.getenv("DJANGO_SECURE_PROXY_SSL_HEADER", "0") == "1":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

if not DEBUG:
    SECURE_SSL_REDIRECT = os.getenv("DJANGO_SECURE_SSL_REDIRECT", "1") == "1"
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
    SECURE_HSTS_SECONDS = int(os.getenv("DJANGO_SECURE_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
