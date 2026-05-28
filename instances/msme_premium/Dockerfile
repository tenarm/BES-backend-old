FROM python:3.10-slim

# Install system dependencies & PDM
RUN pip install --no-cache-dir pdm

WORKDIR /app

# Copy monorepo workspace configuration files
COPY pyproject.toml pdm.lock ./

# Copy core, extensions, and the specific client instance folder
COPY core ./core
COPY extensions ./extensions
COPY instances/msme_premium ./instances/msme_premium

# Install production dependencies (resolving workspace links)
RUN pdm install --prod --no-editable

EXPOSE 8000

# Set pythonpath so Uvicorn can resolve import paths correctly
ENV PYTHONPATH="/app"

CMD ["pdm", "run", "uvicorn", "instances.msme_premium.msme_premium.main:app", "--host", "0.0.0.0", "--port", "8000"]
