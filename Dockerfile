FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

RUN groupadd --gid 1000 producthunt \
    && useradd --uid 1000 --gid 1000 --create-home producthunt \
    && mkdir -p /app/data /app/output \
    && chown -R producthunt:producthunt /app/data /app/output
USER producthunt

ENTRYPOINT ["producthunt"]
CMD ["run"]
