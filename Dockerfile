FROM python:3.12-alpine AS base

FROM base AS build

ENV POETRY_VERSION=1.8.3 \
    POETRY_VIRTUALENVS_IN_PROJECT=1

RUN pip install poetry==$POETRY_VERSION

WORKDIR /build
COPY pyproject.toml poetry.lock ./
RUN poetry install --no-root

FROM base AS final

WORKDIR /app

COPY --from=build /build/.venv .venv
COPY ./khinsider_bot.py ./khinsider_bot.py

CMD [".venv/bin/python", "-m", "khinsider_bot"]