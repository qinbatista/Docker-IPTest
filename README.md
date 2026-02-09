# Docker-IPTest

## Server Start Command
```bash
docker rm -f ip_test && docker pull --platform linux/arm64 qinbatista/ip_test && docker run -d --platform linux/arm64 --name ip_test --restart=always -p 8000:8000/udp qinbatista/ip_test
```
