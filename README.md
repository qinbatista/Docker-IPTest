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
docker build -t ip_test:latest ./ip_test_server
```

Run:
```bash
docker run --rm -p 8765:8765 ip_test:latest
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
