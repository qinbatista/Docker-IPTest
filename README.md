# Docker-IPTest

## Project Structure
```text
.
├── ip_test_server/
│   ├── ip_test_server.py
│   ├── Dockerfile
│   └── .dockerignore
├── ip_test_client/
│   ├── ip_test_installer.py
│   └── iptest_runtime.py
└── .github/workflows/docker-image-build.yml
```

## Server
Universal (recommended) - build and run on current machine:
```bash
docker build --pull --platform "linux/$(docker info --format '{{.Architecture}}')" -t ip_test:latest ./ip_test_server
docker rm -f ip_test >/dev/null 2>&1 || true; docker run -d --platform "linux/$(docker info --format '{{.Architecture}}')" --name ip_test --restart=always -p 8765:8765 ip_test:latest
```

Universal pull/run (auto-detect amd64 vs arm64):
```bash
PLATFORM="$(uname -m | awk '/arm64|aarch64/{print "linux/arm64"} !/arm64|aarch64/{print "linux/amd64"}')"; docker rm -f ip_test >/dev/null 2>&1 || true; docker image rm -f qinbatista/ip_test:latest >/dev/null 2>&1 || true; docker pull --platform "$PLATFORM" qinbatista/ip_test:latest && docker run -d --platform "$PLATFORM" --name ip_test --restart=always -p 8765:8765 qinbatista/ip_test:latest
```

If you need to force architecture:
```bash
# x86_64 host
docker rm -f ip_test || true && docker pull --platform linux/amd64 qinbatista/ip_test:latest && docker run -d --platform linux/amd64 --name ip_test --restart=always -p 8765:8765 qinbatista/ip_test:latest

# arm64 host
docker rm -f ip_test || true && docker pull --platform linux/arm64 qinbatista/ip_test:latest && docker run -d --platform linux/arm64 --name ip_test --restart=always -p 8765:8765 qinbatista/ip_test:latest
```

## Client Installer (macOS)
Run installer:
```bash
python3 ip_test_client/ip_test_installer.py
```

Installer behavior:
- Checks system is macOS (`Darwin`) before install.
- Reinstalls `iptest` and `ip_test` commands every run.
- Installs into `/usr/local/bin` if writable, otherwise `~/.local/bin`.

## Configure Server Domain
Set your real server domain in:
- `/Users/qin/QinProject/DockerProject/Docker-IPTest/ip_test_client/client_config.json`

Example:
```json
{
  "server_url": "https://your-domain.com"
}
```

Priority order:
1. `IPTEST_SERVER_URL` environment variable
2. `ip_test_client/client_config.json`
3. default `http://127.0.0.1:8765`

## Runtime Command
After install:
```bash
iptest
iptest 8.8.8.8
iptest www.google.com
```

Custom server URL:
```bash
export IPTEST_SERVER_URL="http://your-server-host:8765"
```

## Docker Push Workflow
`/.github/workflows/docker-image-build.yml` builds and pushes:
- `qinbatista/ip_test:latest`
- Required `BuildEnv` environment secrets:
  - `DOCKERHUB_USERNAME`
  - `DOCKERHUB_TOKEN`
