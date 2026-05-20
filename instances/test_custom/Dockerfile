FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml .
# Assuming pip for now, can be changed to pdm if preferred
RUN pip install .

# Copy application code
COPY . .

CMD ["uvicorn", "test_custom.main:app", "--host", "0.0.0.0", "--port", "8000"]
