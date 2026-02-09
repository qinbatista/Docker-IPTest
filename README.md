# Docker-IPTest

## Project Structure
```text
.
├── ip_test_server/
│   ├── ip_test_server.py
│   ├── Dockerfile
│   ├── .dockerignore
│   └── log.txt
├── ip_test_client/
│   ├── ip_test_installer.py
│   └── iptest_runtime.py
└── .github/workflows/docker-image-build.yml
```

## Server
Build local image and run:
```bash
docker rm -f ip_test >/dev/null 2>&1 || true; docker build --pull -t ip_test:latest ./ip_test_server
docker run -d --name ip_test --restart=always -p 8000:8000/udp ip_test:latest
```

Pull and run published image (auto architecture):
```bash
docker rm -f ip_test >/dev/null 2>&1 || true; docker pull qinbatista/ip_test:latest
docker run -d --name ip_test --restart=always -p 8000:8000/udp qinbatista/ip_test:latest
```

Build and push multi-arch image (manual publish):
```bash
docker buildx build --platform linux/amd64,linux/arm64 -t qinbatista/ip_test:latest --push ./ip_test_server
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
  "server_url": "your-server-host:8000"
}
```

Priority order:
1. `IPTEST_SERVER_URL` environment variable
2. `ip_test_client/client_config.json`
3. default `127.0.0.1:8000`

## Runtime Command
After install:
```bash
iptest
iptest 8.8.8.8
iptest www.google.com
```

Custom server URL:
```bash
export IPTEST_SERVER_URL="your-server-host:8000"
```

## Server Log File
Read container log:
```bash
docker logs -f ip_test
```

Read log file inside container:
```bash
docker exec -it ip_test sh -c "tail -f /app/log.txt"
```

## Docker Push Workflow
`/.github/workflows/docker-image-build.yml` builds and pushes:
- `qinbatista/ip_test:latest`
- Required `BuildEnv` environment secrets:
  - `DOCKERHUB_USERNAME`
  - `DOCKERHUB_TOKEN`
