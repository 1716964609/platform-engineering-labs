FROM python:3.12-alpine

RUN pip install --no-cache-dir PyYAML==6.0.3

COPY render.py /app/render.py

CMD ["python", "/app/render.py"]
