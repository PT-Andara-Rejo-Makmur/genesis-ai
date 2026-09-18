# syntax=docker/dockerfile:1.7

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    ALOS_CONTRACTS_PATH=/contracts

WORKDIR /app

RUN groupadd --system genesis && useradd --system --gid genesis --home-dir /app genesis

COPY pyproject.toml README.md ./
COPY src ./src
COPY --from=contracts schemas /contracts/schemas
COPY --from=contracts events /contracts/events
COPY --from=contracts VERSION /contracts/VERSION

RUN python -m pip install --upgrade pip && python -m pip install ".[frameworks]"

USER genesis
EXPOSE 8100

CMD ["uvicorn", "genesis.main:app", "--host", "0.0.0.0", "--port", "8100"]
