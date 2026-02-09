# Docker-IPTest

## Server Start Command
```bash
docker rm -f ip_test && docker pull qinbatista/ip_test && docker run -d --name ip_test --restart=always -p 8000:8000/udp qinbatista/ip_test
```
