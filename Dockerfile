# STRETCH GOAL 4
FROM python:3.12-slim

WORKDIR /app
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements-dev.txt .
RUN python -m pip install --no-cache-dir -r requirements-dev.txt
COPY main.py claims.py db.py seed_claims.csv ./
COPY tests ./tests
COPY .codex/hooks/protect_tests.py ./.codex/hooks/protect_tests.py

ENTRYPOINT ["python"]
CMD ["main.py", "--help"]
