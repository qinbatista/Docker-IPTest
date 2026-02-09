#!/usr/bin/env python3
import argparse
import ipaddress
import json
import re
import socket
import subprocess
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class IPTestLookupService:
    def __init__(self):
        self.ipwho_url = "http://ipwho.is"
        self.ipapi_url = "http://ip-api.com/json"
        self.ipapi_fields = "status,message,continent,continentCode,country,countryCode,region,regionName,city,district,zip,lat,lon,timezone,offset,currency,isp,org,as,asname,reverse,mobile,proxy,hosting,query"
        self.dns_servers = ["8.8.8.8", "1.1.1.1"]

    def extract_lookup_target(self, target_value):
        cleaned_target = target_value.strip()
        if "://" not in cleaned_target:
            cleaned_target = f"//{cleaned_target}"
        parsed_target = urllib.parse.urlparse(cleaned_target)
        if parsed_target.hostname:
            return parsed_target.hostname
        return target_value.strip().split("/")[0].split(":")[0]

    def is_ip_value(self, target_value):
        try:
            ipaddress.ip_address(target_value)
            return True
        except ValueError:
            return False

    def is_public_ip(self, ip_value):
        try:
            parsed_ip = ipaddress.ip_address(ip_value)
            return not (parsed_ip.is_private or parsed_ip.is_loopback or parsed_ip.is_reserved or parsed_ip.is_link_local or parsed_ip.is_multicast or parsed_ip.is_unspecified)
        except ValueError:
            return False

    def detect_target_type(self, target_value):
        if self.is_ip_value(target_value):
            return "ip"
        return "domain"

    def unique_values(self, values_list):
        unique_list = []
        for value in values_list:
            if value and value not in unique_list:
                unique_list.append(value)
        return unique_list

    def contains_public_ip(self, ip_values):
        for ip_value in ip_values:
            if self.is_public_ip(ip_value):
                return True
        return False

    def parse_ip_tokens(self, text_value):
        extracted_values = []
        for token_value in re.split(r"[\s,;]+", text_value):
            cleaned_value = token_value.strip().strip("[]()")
            if "#" in cleaned_value:
                cleaned_value = cleaned_value.split("#", 1)[0]
            if cleaned_value.endswith("."):
                cleaned_value = cleaned_value[:-1]
            if self.is_ip_value(cleaned_value):
                extracted_values.append(cleaned_value)
        return self.unique_values(extracted_values)

    def resolve_domain_via_socket(self, domain_value):
        try:
            address_values = []
            for address_info in socket.getaddrinfo(domain_value, None):
                resolved_ip = address_info[4][0]
                if self.is_ip_value(resolved_ip) and resolved_ip not in address_values:
                    address_values.append(resolved_ip)
            return address_values
        except Exception:
            return []

    def resolve_domain_via_nslookup(self, domain_value, dns_server):
        try:
            command_result = subprocess.run(["nslookup", domain_value, dns_server], capture_output=True, text=True, timeout=6)
            parsed_values = self.parse_ip_tokens(f"{command_result.stdout}\n{command_result.stderr}")
            return [value for value in parsed_values if value != dns_server]
        except Exception:
            return []

    def resolve_domain(self, domain_value):
        resolved_values = self.resolve_domain_via_socket(domain_value)
        if self.contains_public_ip(resolved_values):
            return resolved_values
        for dns_server in self.dns_servers:
            resolved_values = self.unique_values(resolved_values + self.resolve_domain_via_nslookup(domain_value, dns_server))
            if self.contains_public_ip(resolved_values):
                return resolved_values
        return resolved_values

    def choose_lookup_ip(self, ip_values):
        for ip_value in ip_values:
            if self.is_public_ip(ip_value):
                return ip_value
        if ip_values:
            return ip_values[0]
        return ""

    def fetch_from_ipwho(self, ip_value):
        request_url = f"{self.ipwho_url}/{urllib.parse.quote(ip_value)}"
        try:
            with urllib.request.urlopen(request_url, timeout=12) as response_value:
                payload_mapping = json.loads(response_value.read().decode("utf-8"))
            if not payload_mapping.get("success", False):
                return {"ok": False, "provider": "ipwho.is", "error": payload_mapping.get("message", "Lookup failed")}
            return {"ok": True, "provider": "ipwho.is", "payload": payload_mapping}
        except Exception as error_value:
            return {"ok": False, "provider": "ipwho.is", "error": f"Lookup failed: {error_value}"}

    def fetch_from_ipapi(self, ip_value):
        request_url = f"{self.ipapi_url}/{urllib.parse.quote(ip_value)}?fields={self.ipapi_fields}"
        try:
            with urllib.request.urlopen(request_url, timeout=12) as response_value:
                payload_mapping = json.loads(response_value.read().decode("utf-8"))
            if payload_mapping.get("status") != "success":
                return {"ok": False, "provider": "ip-api.com", "error": payload_mapping.get("message", "Lookup failed")}
            return {"ok": True, "provider": "ip-api.com", "payload": payload_mapping}
        except Exception as error_value:
            return {"ok": False, "provider": "ip-api.com", "error": f"Lookup failed: {error_value}"}

    def format_utc_offset(self, offset_seconds):
        if not isinstance(offset_seconds, int):
            return ""
        sign_value = "+" if offset_seconds >= 0 else "-"
        absolute_seconds = abs(offset_seconds)
        hour_value = absolute_seconds // 3600
        minute_value = (absolute_seconds % 3600) // 60
        return f"{sign_value}{hour_value:02d}:{minute_value:02d}"

    def build_provider_attempt(self, provider_result):
        if provider_result.get("ok", False):
            return {"provider": provider_result.get("provider", ""), "ok": True}
        return {"provider": provider_result.get("provider", ""), "ok": False, "error": provider_result.get("error", "")}

    def map_ipwho_payload(self, target_metadata, provider_payload, provider_attempts):
        connection_mapping = provider_payload.get("connection", {})
        flag_mapping = provider_payload.get("flag", {})
        timezone_mapping = provider_payload.get("timezone", {})
        return {
            "ok": True,
            "input": target_metadata.get("input", ""),
            "target_type": target_metadata.get("target_type", ""),
            "resolved_host": target_metadata.get("resolved_host", ""),
            "resolved_ips": target_metadata.get("resolved_ips", []),
            "ip": provider_payload.get("ip", ""),
            "ip_type": provider_payload.get("type", ""),
            "provider": "ipwho.is",
            "provider_info": {
                "used_provider": "ipwho.is",
                "fallback_provider": "ip-api.com",
                "lookup_chain": "ipwho.is -> ip-api.com",
                "free_sources_only": True,
                "provider_attempts": provider_attempts
            },
            "location": {
                "continent": provider_payload.get("continent", ""),
                "continent_code": provider_payload.get("continent_code", ""),
                "country": provider_payload.get("country", ""),
                "country_code": provider_payload.get("country_code", ""),
                "region": provider_payload.get("region", ""),
                "region_code": provider_payload.get("region_code", ""),
                "city": provider_payload.get("city", ""),
                "latitude": provider_payload.get("latitude", ""),
                "longitude": provider_payload.get("longitude", ""),
                "postal": provider_payload.get("postal", "")
            },
            "country_details": {
                "is_eu": provider_payload.get("is_eu", ""),
                "calling_code": provider_payload.get("calling_code", ""),
                "capital": provider_payload.get("capital", ""),
                "borders": provider_payload.get("borders", ""),
                "flag_emoji": flag_mapping.get("emoji", ""),
                "flag_image_url": flag_mapping.get("img", ""),
                "district": "",
                "currency": ""
            },
            "network": {
                "asn": connection_mapping.get("asn", ""),
                "isp": connection_mapping.get("isp", ""),
                "organization": connection_mapping.get("org", ""),
                "domain": connection_mapping.get("domain", ""),
                "asn_name": connection_mapping.get("org", ""),
                "reverse_dns": "",
                "is_mobile": "",
                "is_proxy": "",
                "is_hosting": ""
            },
            "timezone": {
                "id": timezone_mapping.get("id", ""),
                "abbr": timezone_mapping.get("abbr", ""),
                "utc_offset": timezone_mapping.get("utc", ""),
                "offset_seconds": timezone_mapping.get("offset", ""),
                "current_time": timezone_mapping.get("current_time", ""),
                "is_dst": timezone_mapping.get("is_dst", "")
            }
        }

    def map_ipapi_payload(self, target_metadata, provider_payload, provider_attempts):
        as_value = provider_payload.get("as", "")
        asn_value = as_value.split(" ", 1)[0] if as_value.startswith("AS") else as_value
        offset_seconds = provider_payload.get("offset", "")
        return {
            "ok": True,
            "input": target_metadata.get("input", ""),
            "target_type": target_metadata.get("target_type", ""),
            "resolved_host": target_metadata.get("resolved_host", ""),
            "resolved_ips": target_metadata.get("resolved_ips", []),
            "ip": provider_payload.get("query", ""),
            "ip_type": "",
            "provider": "ip-api.com",
            "provider_info": {
                "used_provider": "ip-api.com",
                "fallback_provider": "",
                "lookup_chain": "ipwho.is -> ip-api.com",
                "free_sources_only": True,
                "provider_attempts": provider_attempts
            },
            "location": {
                "continent": provider_payload.get("continent", ""),
                "continent_code": provider_payload.get("continentCode", ""),
                "country": provider_payload.get("country", ""),
                "country_code": provider_payload.get("countryCode", ""),
                "region": provider_payload.get("regionName", ""),
                "region_code": provider_payload.get("region", ""),
                "city": provider_payload.get("city", ""),
                "latitude": provider_payload.get("lat", ""),
                "longitude": provider_payload.get("lon", ""),
                "postal": provider_payload.get("zip", "")
            },
            "country_details": {
                "is_eu": "",
                "calling_code": "",
                "capital": "",
                "borders": "",
                "flag_emoji": "",
                "flag_image_url": "",
                "district": provider_payload.get("district", ""),
                "currency": provider_payload.get("currency", "")
            },
            "network": {
                "asn": asn_value,
                "isp": provider_payload.get("isp", ""),
                "organization": provider_payload.get("org", ""),
                "domain": "",
                "asn_name": provider_payload.get("asname", ""),
                "reverse_dns": provider_payload.get("reverse", ""),
                "is_mobile": provider_payload.get("mobile", ""),
                "is_proxy": provider_payload.get("proxy", ""),
                "is_hosting": provider_payload.get("hosting", "")
            },
            "timezone": {
                "id": provider_payload.get("timezone", ""),
                "abbr": "",
                "utc_offset": self.format_utc_offset(offset_seconds),
                "offset_seconds": offset_seconds,
                "current_time": "",
                "is_dst": ""
            }
        }

    def lookup_ip(self, ip_value, target_metadata):
        provider_attempts = []
        ipwho_result = self.fetch_from_ipwho(ip_value)
        provider_attempts.append(self.build_provider_attempt(ipwho_result))
        if ipwho_result.get("ok", False):
            return self.map_ipwho_payload(target_metadata, ipwho_result.get("payload", {}), provider_attempts)
        ipapi_result = self.fetch_from_ipapi(ip_value)
        provider_attempts.append(self.build_provider_attempt(ipapi_result))
        if ipapi_result.get("ok", False):
            return self.map_ipapi_payload(target_metadata, ipapi_result.get("payload", {}), provider_attempts)
        return {
            "ok": False,
            "input": target_metadata.get("input", ""),
            "target_type": target_metadata.get("target_type", ""),
            "resolved_host": target_metadata.get("resolved_host", ""),
            "resolved_ips": target_metadata.get("resolved_ips", []),
            "error": "All free lookup providers failed",
            "provider_errors": [ipwho_result.get("error", ""), ipapi_result.get("error", "")],
            "provider_info": {
                "used_provider": "",
                "fallback_provider": "",
                "lookup_chain": "ipwho.is -> ip-api.com",
                "free_sources_only": True,
                "provider_attempts": provider_attempts
            }
        }

    def build_target_metadata(self, input_value, target_type, resolved_host, resolved_ips):
        return {"input": input_value, "target_type": target_type, "resolved_host": resolved_host, "resolved_ips": resolved_ips}

    def lookup_target(self, target_value):
        stripped_target = target_value.strip()
        if not stripped_target:
            return {"ok": False, "error": "Lookup target is required"}
        normalized_target = self.extract_lookup_target(stripped_target)
        if self.is_ip_value(normalized_target):
            target_metadata = self.build_target_metadata(stripped_target, "ip", normalized_target, [normalized_target])
            return self.lookup_ip(normalized_target, target_metadata)
        resolved_ips = self.resolve_domain(normalized_target)
        if not resolved_ips:
            return {"ok": False, "input": stripped_target, "target_type": "domain", "resolved_host": normalized_target, "error": "Could not resolve domain"}
        selected_ip = self.choose_lookup_ip(resolved_ips)
        target_metadata = self.build_target_metadata(stripped_target, "domain", normalized_target, resolved_ips)
        return self.lookup_ip(selected_ip, target_metadata)


class TimeGapService:
    def __init__(self):
        self.note_text = "Gap is calculated in UTC milliseconds to avoid timezone drift"

    def parse_integer(self, value):
        try:
            return int(float(value))
        except Exception:
            return None

    def parse_datetime_iso(self, datetime_value, offset_minutes):
        if not datetime_value:
            return None
        normalized_value = datetime_value.replace("Z", "+00:00")
        try:
            parsed_datetime = datetime.fromisoformat(normalized_value)
            if parsed_datetime.tzinfo is None and offset_minutes is not None:
                parsed_datetime = parsed_datetime.replace(tzinfo=timezone(timedelta(minutes=offset_minutes)))
            if parsed_datetime.tzinfo is None:
                parsed_datetime = parsed_datetime.replace(tzinfo=timezone.utc)
            return parsed_datetime.astimezone(timezone.utc)
        except Exception:
            return None

    def parse_client_sent_datetime(self, client_context):
        parsed_offset = self.parse_integer(client_context.get("client_utc_offset_minutes", ""))
        epoch_value = self.parse_integer(client_context.get("client_sent_epoch_ms", ""))
        if epoch_value is not None:
            return datetime.fromtimestamp(epoch_value / 1000, tz=timezone.utc)
        parsed_utc_datetime = self.parse_datetime_iso(str(client_context.get("client_sent_at_utc_iso", "")), parsed_offset)
        if parsed_utc_datetime:
            return parsed_utc_datetime
        return self.parse_datetime_iso(str(client_context.get("client_sent_at_local_iso", "")), parsed_offset)

    def build_timing_payload(self, client_context, server_received_utc):
        client_sent_datetime = self.parse_client_sent_datetime(client_context)
        server_received_epoch_ms = int(server_received_utc.timestamp() * 1000)
        if client_sent_datetime:
            client_sent_epoch_ms = int(client_sent_datetime.timestamp() * 1000)
            gap_ms = server_received_epoch_ms - client_sent_epoch_ms
            gap_seconds = round(gap_ms / 1000, 6)
        else:
            client_sent_epoch_ms = None
            gap_ms = None
            gap_seconds = None
        return {
            "client_sent_at_utc": client_sent_datetime.isoformat() if client_sent_datetime else "",
            "server_received_at_utc": server_received_utc.isoformat(),
            "client_sent_epoch_ms": client_sent_epoch_ms,
            "server_received_epoch_ms": server_received_epoch_ms,
            "gap_ms": gap_ms,
            "gap_seconds": gap_seconds,
            "client_timezone_name": str(client_context.get("client_timezone_name", "")),
            "client_utc_offset_minutes": self.parse_integer(client_context.get("client_utc_offset_minutes", "")),
            "clock_skew_detected": bool(gap_ms is not None and gap_ms < 0),
            "note": self.note_text
        }


class IPTestRequestHandler(BaseHTTPRequestHandler):
    lookup_service = IPTestLookupService()
    time_gap_service = TimeGapService()

    def write_json(self, status_code, response_mapping):
        encoded_payload = json.dumps(response_mapping).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded_payload)))
        self.end_headers()
        self.wfile.write(encoded_payload)

    def read_json_body(self):
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0:
            return {}
        body_value = self.rfile.read(content_length)
        if not body_value:
            return {}
        try:
            parsed_body = json.loads(body_value.decode("utf-8"))
            if isinstance(parsed_body, dict):
                return parsed_body
            return {}
        except Exception:
            return {}

    def extract_source_ip(self):
        forwarded_for_value = self.headers.get("X-Forwarded-For", "")
        forwarded_ip = forwarded_for_value.split(",", 1)[0].strip() if forwarded_for_value else ""
        if forwarded_ip:
            return forwarded_ip
        return self.client_address[0]

    def choose_default_target(self, source_ip, client_context):
        public_hint = str(client_context.get("client_public_ip_hint", "")).strip()
        local_ip = str(client_context.get("client_local_ip", "")).strip()
        if public_hint and self.lookup_service.is_ip_value(public_hint):
            return public_hint
        if source_ip and self.lookup_service.is_public_ip(source_ip):
            return source_ip
        if local_ip and self.lookup_service.is_ip_value(local_ip):
            return local_ip
        if source_ip and self.lookup_service.is_ip_value(source_ip):
            return source_ip
        return ""

    def process_lookup(self, target_value, client_context):
        server_received_utc = datetime.now(timezone.utc)
        source_ip = self.extract_source_ip()
        effective_target = target_value.strip() if target_value.strip() else self.choose_default_target(source_ip, client_context)
        if not effective_target:
            lookup_response = {"ok": False, "error": "Could not determine lookup target"}
        else:
            lookup_response = self.lookup_service.lookup_target(effective_target)
        timing_payload = self.time_gap_service.build_timing_payload(client_context, server_received_utc)
        request_context = {
            "request_source_ip": source_ip,
            "x_forwarded_for": self.headers.get("X-Forwarded-For", ""),
            "client_hostname": str(client_context.get("client_hostname", "")),
            "client_local_ip": str(client_context.get("client_local_ip", "")),
            "client_public_ip_hint": str(client_context.get("client_public_ip_hint", "")),
            "client_platform": str(client_context.get("client_platform", ""))
        }
        lookup_response["timing"] = timing_payload
        lookup_response["request_context"] = request_context
        if lookup_response.get("ok", False):
            return 200, lookup_response
        return 400, lookup_response

    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        match parsed_path.path:
            case "/health":
                self.write_json(200, {"ok": True, "message": "ip test server is running"})
            case "/lookup":
                query_mapping = urllib.parse.parse_qs(parsed_path.query)
                target_value = query_mapping.get("target", [""])[0]
                status_code, lookup_response = self.process_lookup(target_value, {})
                self.write_json(status_code, lookup_response)
            case _:
                self.write_json(404, {"ok": False, "error": "Route not found"})

    def do_POST(self):
        parsed_path = urllib.parse.urlparse(self.path)
        match parsed_path.path:
            case "/lookup":
                parsed_body = self.read_json_body()
                target_value = str(parsed_body.get("target", ""))
                client_context = parsed_body.get("client_context", {}) if isinstance(parsed_body.get("client_context", {}), dict) else {}
                status_code, lookup_response = self.process_lookup(target_value, client_context)
                self.write_json(status_code, lookup_response)
            case _:
                self.write_json(404, {"ok": False, "error": "Route not found"})

    def log_message(self, message_format, *format_values):
        return


class IPTestServerApplication:
    def __init__(self):
        self.argument_parser = argparse.ArgumentParser(description="IP test lookup server")
        self.argument_parser.add_argument("--host", default="127.0.0.1")
        self.argument_parser.add_argument("--port", type=int, default=8765)

    def run(self):
        parsed_arguments = self.argument_parser.parse_args()
        http_server = ThreadingHTTPServer((parsed_arguments.host, parsed_arguments.port), IPTestRequestHandler)
        print(f"IP test server listening on http://{parsed_arguments.host}:{parsed_arguments.port}")
        try:
            http_server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            http_server.server_close()


if __name__ == "__main__":
    IPTestServerApplication().run()
