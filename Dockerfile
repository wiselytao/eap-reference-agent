FROM python:3.9-slim

WORKDIR /app
COPY pyproject.toml README.md /app/
COPY src /app/src
COPY config.yaml /app/
COPY tools/TOOLS.md /app/tools/TOOLS.md
COPY profiles /app/profiles

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

EXPOSE 8080
ENV REFERENCE_AGENT_CONFIG=/app/config.yaml
ENV REFERENCE_AGENT_TOOLS=/app/tools/TOOLS.md
ENV REFERENCE_AGENT_PROFILES=/app/profiles

CMD ["uvicorn", "reference_agent.main:app", "--host", "0.0.0.0", "--port", "8080"]
