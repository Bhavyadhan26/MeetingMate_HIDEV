FROM python:3.12-slim

WORKDIR /workspace
COPY . ./backend
RUN pip install --no-cache-dir -r backend/requirements.txt

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
