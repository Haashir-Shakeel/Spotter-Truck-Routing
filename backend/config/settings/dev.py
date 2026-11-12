"""Local development settings."""

from .base import *  # noqa: F403
from .base import env

DEBUG = env.bool("DJANGO_DEBUG", default=True)
SECRET_KEY = env("DJANGO_SECRET_KEY", default="dev-only-insecure-secret-key")
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1", "0.0.0.0"])
CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS", default=["http://localhost:5173", "http://127.0.0.1:5173"]
)
