FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY --from=ghcr.io/astral-sh/uv:0.12.23 /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .

ENV PATH="/app/.venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=config.settings.prod

# Static files are collected at build time. Production settings refuse to load without their
# secrets, so placeholder values are passed to this one command only (never baked into the image).
RUN DJANGO_SECRET_KEY=build-only DJANGO_ALLOWED_HOSTS=localhost MAPBOX_ACCESS_TOKEN=build-only \
    python manage.py collectstatic --noinput

# Run as an unprivileged user.
RUN useradd --system --create-home app && chmod +x start.sh
USER app

EXPOSE 8000
CMD ["./start.sh"]
