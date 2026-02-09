#!/usr/bin/env python3
import argparse
import ipaddress
import json
import os
import re
import socket
import subprocess
import threading
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path


class IPTestServerLogWriter:
    def __init__(self):
        configured_path = os.getenv("IP_TEST_LOG_FILE", "").strip()
        default_path = Path(__file__).resolve().parent / "log.txt"
        self.log_file_path = Path(configured_path).expanduser() if configured_path else default_path
        self.write_lock = threading.Lock()
        self.log_file_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_file_path.touch(exist_ok=True)

    def write(self, level_text, message_text):
        try:
            timestamp_text = datetime.now(timezone.utc).isoformat()
            log_line = f"{timestamp_text} [{level_text}] {message_text}"
            with self.write_lock:
                with self.log_file_path.open("a", encoding="utf-8") as log_file:
                    log_file.write(f"{log_line}\n")
            print(log_line, flush=True)
        except Exception:
            return


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


class IPTestUDPServer:
    def __init__(self, host_value, port_value, lookup_service, time_gap_service, server_logger):
        self.host_value = host_value
        self.port_value = port_value
        self.lookup_service = lookup_service
        self.time_gap_service = time_gap_service
        self.server_logger = server_logger

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

    def build_request_context(self, source_ip, client_context):
        return {
            "request_source_ip": source_ip,
            "client_hostname": str(client_context.get("client_hostname", "")),
            "client_local_ip": str(client_context.get("client_local_ip", "")),
            "client_public_ip_hint": str(client_context.get("client_public_ip_hint", "")),
            "client_platform": str(client_context.get("client_platform", "")),
            "protocol": "udp"
        }

    def process_lookup(self, source_ip, target_value, client_context):
        request_start_utc = datetime.now(timezone.utc)
        server_received_utc = datetime.now(timezone.utc)
        effective_target = target_value.strip() if target_value.strip() else self.choose_default_target(source_ip, client_context)
        if not effective_target:
            lookup_response = {"ok": False, "error": "Could not determine lookup target"}
        else:
            lookup_response = self.lookup_service.lookup_target(effective_target)
        lookup_response["timing"] = self.time_gap_service.build_timing_payload(client_context, server_received_utc)
        lookup_response["request_context"] = self.build_request_context(source_ip, client_context)
        status_code = 200 if lookup_response.get("ok", False) else 400
        duration_ms = int((datetime.now(timezone.utc) - request_start_utc).total_seconds() * 1000)
        self.server_logger.write("INFO", f"protocol=udp source_ip={source_ip} target={effective_target} status={status_code} duration_ms={duration_ms}")
        return lookup_response

    def process_health(self, source_ip, client_context):
        server_received_utc = datetime.now(timezone.utc)
        response_mapping = {"ok": True, "message": "ip test udp server is running"}
        response_mapping["timing"] = self.time_gap_service.build_timing_payload(client_context, server_received_utc)
        response_mapping["request_context"] = self.build_request_context(source_ip, client_context)
        self.server_logger.write("INFO", f"protocol=udp source_ip={source_ip} action=health status=200 duration_ms=0")
        return response_mapping

    def parse_payload(self, payload_bytes):
        try:
            payload_mapping = json.loads(payload_bytes.decode("utf-8"))
            if isinstance(payload_mapping, dict):
                return payload_mapping
            return {}
        except Exception as error_value:
            self.server_logger.write("WARNING", f"invalid_udp_payload error={error_value}")
            return {}

    def process_packet(self, payload_bytes, client_address):
        source_ip = client_address[0]
        payload_mapping = self.parse_payload(payload_bytes)
        if not payload_mapping:
            return {"ok": False, "error": "Invalid request payload", "request_context": {"request_source_ip": source_ip, "protocol": "udp"}}
        action_value = str(payload_mapping.get("action", "lookup")).strip().lower()
        client_context = payload_mapping.get("client_context", {}) if isinstance(payload_mapping.get("client_context", {}), dict) else {}
        target_value = str(payload_mapping.get("target", ""))
        match action_value:
            case "health":
                return self.process_health(source_ip, client_context)
            case _:
                return self.process_lookup(source_ip, target_value, client_context)

    def run(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_socket:
            udp_socket.bind((self.host_value, self.port_value))
            self.server_logger.write("INFO", f"server_start protocol=udp host={self.host_value} port={self.port_value} log_file={self.server_logger.log_file_path}")
            print(f"IP test UDP server listening on {self.host_value}:{self.port_value}")
            try:
                while True:
                    payload_bytes, client_address = udp_socket.recvfrom(65535)
                    response_mapping = self.process_packet(payload_bytes, client_address)
                    udp_socket.sendto(json.dumps(response_mapping).encode("utf-8"), client_address)
            except KeyboardInterrupt:
                self.server_logger.write("INFO", "server_stop reason=keyboard_interrupt")
            finally:
                self.server_logger.write("INFO", "server_stop reason=shutdown")


class IPTestServerApplication:
    def __init__(self):
        self.argument_parser = argparse.ArgumentParser(description="IP test lookup server")
        self.argument_parser.add_argument("--host", default="0.0.0.0")
        self.argument_parser.add_argument("--port", type=int, default=8000)
        self.server_logger = IPTestServerLogWriter()
        self.lookup_service = IPTestLookupService()
        self.time_gap_service = TimeGapService()

    def run(self):
        parsed_arguments = self.argument_parser.parse_args()
        udp_server = IPTestUDPServer(parsed_arguments.host, parsed_arguments.port, self.lookup_service, self.time_gap_service, self.server_logger)
        udp_server.run()


if __name__ == "__main__":
    IPTestServerApplication().run()
