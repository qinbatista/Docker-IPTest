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
Build:
```bash
docker build --platform linux/arm64 -t qinbatista/ip_test:latest ./ip_test_server
```

Pull:
```bash
docker pull --platform linux/arm64 qinbatista/ip_test:latest
```

Run:
```bash
docker rm -f ip_test && docker run -d --platform linux/arm64 --name ip_test --restart=always -p 8765:8765 qinbatista/ip_test:latest
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
