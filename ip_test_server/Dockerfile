ARG TARGETPLATFORM
FROM --platform=$TARGETPLATFORM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends dnsutils ca-certificates && rm -rf /var/lib/apt/lists/*

COPY ip_test_server.py /app/ip_test_server.py

EXPOSE 8000/udp

CMD ["python3", "/app/ip_test_server.py", "--host", "0.0.0.0", "--port", "8000"]
