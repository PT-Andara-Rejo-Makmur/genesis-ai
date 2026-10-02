# syntax=docker/dockerfile:1.7

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=5 \
    ALOS_CONTRACTS_PATH=/contracts

WORKDIR /app

RUN groupadd --system genesis && useradd --system --gid genesis --home-dir /app genesis

COPY pyproject.toml README.md ./
RUN --mount=type=cache,target=/root/.cache/pip python -c "import subprocess, tomllib; project = tomllib.load(open('pyproject.toml', 'rb')); subprocess.check_call(['python', '-m', 'pip', 'install', *project['build-system']['requires'], *project['project']['dependencies'], *project['project']['optional-dependencies']['frameworks']])"
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/pip python -m pip install --no-deps --no-build-isolation .
COPY --from=contracts schemas /contracts/schemas
COPY --from=contracts events /contracts/events
COPY --from=contracts VERSION /contracts/VERSION

USER genesis
EXPOSE 8100

CMD ["uvicorn", "genesis.main:app", "--host", "0.0.0.0", "--port", "8100"]
