"""Production settings. Every secret and host must be provided via the environment."""

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403
from .base import DATABASES, MAPBOX_ACCESS_TOKEN, MIDDLEWARE, REST_FRAMEWORK, env

DEBUG = False

# WhiteNoise serves collected static files directly after SecurityMiddleware.
MIDDLEWARE = [MIDDLEWARE[0], "whitenoise.middleware.WhiteNoiseMiddleware", *MIDDLEWARE[1:]]
SECRET_KEY = env("DJANGO_SECRET_KEY")

# Render provides the service's public hostname; other hosts can be added explicitly.
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])
if render_host := env("RENDER_EXTERNAL_HOSTNAME", default=""):
    ALLOWED_HOSTS.append(render_host)
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("Set DJANGO_ALLOWED_HOSTS (or deploy on Render).")

CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
# Optional, e.g. preview deployments: r"^https://your-app-[a-z0-9-]+\.vercel\.app$"
CORS_ALLOWED_ORIGIN_REGEXES = env.list("CORS_ALLOWED_ORIGIN_REGEXES", default=[])
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

# The API is useless without routing; fail at startup rather than on the first request.
if not MAPBOX_ACCESS_TOKEN:
    raise ImproperlyConfigured("Set MAPBOX_ACCESS_TOKEN.")

# Reuse connections between requests and drop ones the database closed while idle.
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", default=60)
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True

# Behind the platform proxy every request comes from the proxy's address. Rate limits must use
# the client address from X-Forwarded-For instead, counting this many trusted proxies.
REST_FRAMEWORK = {**REST_FRAMEWORK, "NUM_PROXIES": env.int("NUM_PROXIES", default=1)}

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
# The platform's health checker calls over plain HTTP inside its network.
SECURE_REDIRECT_EXEMPT = [r"^api/v1/health/$"]
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=3600)
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# HSTS includeSubDomains/preload only make sense on a domain we own; on a shared platform domain
# (e.g. *.onrender.com) they are neither ours to set nor accepted for preload.
SILENCED_SYSTEM_CHECKS = ["security.W005", "security.W021"]
