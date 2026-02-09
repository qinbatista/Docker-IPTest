# Tool-IPTest

## Files
- `ip_test_server.py`: IP lookup HTTP server.
- `Dockerfile`: Docker image for server.
- `.github/workflows/docker-image-build.yml`: GitHub Action to build and push Docker image `qinbatista/ip_test:latest`.
- `ip_test.py`: macOS installer entrypoint. Running this always reinstalls commands.
- `iptest_client.py`: installer implementation (not runtime lookup client).
- `iptest_runtime.py`: runtime command logic used by installed `iptest` / `ip_test` command.
- `iptest.py`: backward-compatible runtime entrypoint.

## Server (Docker)
Build local image:
```bash
docker build -t ip_test:latest .
```

Run local container:
```bash
docker run --rm -p 8765:8765 ip_test:latest
```

Server endpoint:
- `POST /lookup`
- `GET /health`

## GitHub Action (Docker Push)
Workflow copied from your UDP project style and adapted for this repo:
- File: `.github/workflows/docker-image-build.yml`
- Trigger: push/pull_request on `master`
- Push tag: `qinbatista/ip_test:latest`
- Uses secrets:
  - `DOCKERHUB_USERNAME`
  - `DOCKERHUB_TOKEN`

## Installer (macOS)
Run:
```bash
python3 ip_test.py
```

Behavior:
- Each run reinstalls both commands:
  - `iptest`
  - `ip_test`
- Default install path:
  - `/usr/local/bin` if writable
  - otherwise `~/.local/bin`

## Runtime Command Usage
After install:
```bash
iptest
iptest 8.8.8.8
iptest www.google.com
```

Use custom server:
```bash
export IPTEST_SERVER_URL="http://your-server-host:8765"
```
