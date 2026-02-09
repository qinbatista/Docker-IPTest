#!/usr/bin/env python3
import argparse
import json
import os
import platform
import socket
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


class IPTestRuntimeClient:
    def __init__(self):
        self.config_path = Path(__file__).resolve().parent / "client_config.json"
        self.server_url = self.load_server_url()
        self.public_ip_urls = ["http://ifconfig.me/ip", "http://api.ipify.org"]
        self.argument_parser = argparse.ArgumentParser(description="IP test runtime client")
        self.argument_parser.add_argument("target", nargs="?", default="")

    def load_server_url(self):
        configured_url = os.getenv("IPTEST_SERVER_URL", "").strip()
        if configured_url:
            return configured_url
        if self.config_path.exists():
            try:
                with self.config_path.open("r", encoding="utf-8") as config_file:
                    config_mapping = json.load(config_file)
                if isinstance(config_mapping, dict):
                    configured_value = str(config_mapping.get("server_url", "")).strip()
                    if configured_value:
                        return configured_value
            except Exception:
                pass
        return "127.0.0.1:8000"

    def fetch_text(self, request_url):
        try:
            with urllib.request.urlopen(request_url, timeout=8) as response_value:
                return response_value.read().decode("utf-8").strip()
        except Exception:
            return ""

    def is_ip_value(self, value):
        parts = value.split(".")
        if len(parts) != 4:
            return False
        for part in parts:
            if not part.isdigit() or int(part) < 0 or int(part) > 255:
                return False
        return True

    def detect_public_ip(self):
        for request_url in self.public_ip_urls:
            response_text = self.fetch_text(request_url)
            if response_text and self.is_ip_value(response_text):
                return response_text
        return ""

    def detect_local_ip(self):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as socket_value:
                socket_value.connect(("8.8.8.8", 80))
                return socket_value.getsockname()[0]
        except Exception:
            return ""

    def build_client_context(self):
        local_datetime = datetime.now().astimezone()
        utc_datetime = local_datetime.astimezone(timezone.utc)
        offset_minutes = int(local_datetime.utcoffset().total_seconds() / 60) if local_datetime.utcoffset() else 0
        return {
            "client_sent_epoch_ms": int(utc_datetime.timestamp() * 1000),
            "client_sent_at_utc_iso": utc_datetime.isoformat(),
            "client_sent_at_local_iso": local_datetime.isoformat(),
            "client_timezone_name": str(local_datetime.tzinfo),
            "client_utc_offset_minutes": offset_minutes,
            "client_hostname": socket.gethostname(),
            "client_local_ip": self.detect_local_ip(),
            "client_public_ip_hint": self.detect_public_ip(),
            "client_platform": platform.platform()
        }

    def parse_server_address(self):
        configured_server = self.server_url.strip()
        if "://" in configured_server:
            parsed_server = urllib.parse.urlparse(configured_server)
            host_value = parsed_server.hostname or "127.0.0.1"
            port_value = parsed_server.port or 8000
            return host_value, port_value
        if configured_server.count(":") == 1:
            host_value, port_text = configured_server.rsplit(":", 1)
            if port_text.isdigit():
                return host_value or "127.0.0.1", int(port_text)
        return configured_server or "127.0.0.1", 8000

    def lookup_target(self, target_value, client_context):
        host_value, port_value = self.parse_server_address()
        payload_mapping = {"action": "lookup", "target": target_value, "client_context": client_context}
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_socket:
                udp_socket.settimeout(18)
                udp_socket.sendto(json.dumps(payload_mapping).encode("utf-8"), (host_value, port_value))
                response_bytes, _ = udp_socket.recvfrom(65535)
            return json.loads(response_bytes.decode("utf-8"))
        except socket.timeout:
            return {"ok": False, "error": "UDP request timed out"}
        except Exception as error_value:
            return {"ok": False, "error": f"UDP request failed: {error_value}"}

    def print_time_gap(self, response_mapping):
        timing_mapping = response_mapping.get("timing", {}) if isinstance(response_mapping.get("timing", {}), dict) else {}
        if not timing_mapping:
            return
        print(f"Client Sent (UTC): {timing_mapping.get('client_sent_at_utc', '')}")
        print(f"Server Received (UTC): {timing_mapping.get('server_received_at_utc', '')}")
        print(f"Time Gap (ms): {timing_mapping.get('gap_ms', '')}")
        print(f"Time Gap (seconds): {timing_mapping.get('gap_seconds', '')}")
        print(f"Client Timezone: {timing_mapping.get('client_timezone_name', '')}")
        print(f"Client UTC Offset Minutes: {timing_mapping.get('client_utc_offset_minutes', '')}")
        if timing_mapping.get("clock_skew_detected", False):
            print("Clock Skew Detected: true")

    def print_request_context(self, response_mapping):
        context_mapping = response_mapping.get("request_context", {}) if isinstance(response_mapping.get("request_context", {}), dict) else {}
        if not context_mapping:
            return
        print(f"Request Source IP: {context_mapping.get('request_source_ip', '')}")
        print(f"Client Hostname: {context_mapping.get('client_hostname', '')}")
        print(f"Client Local IP: {context_mapping.get('client_local_ip', '')}")
        print(f"Client Public IP Hint: {context_mapping.get('client_public_ip_hint', '')}")

    def format_provider_attempts(self, provider_info):
        provider_attempts = provider_info.get("provider_attempts", []) if isinstance(provider_info.get("provider_attempts", []), list) else []
        if not provider_attempts:
            return ""
        summary_values = []
        for attempt_value in provider_attempts:
            if not isinstance(attempt_value, dict):
                continue
            provider_name = str(attempt_value.get("provider", ""))
            provider_ok = bool(attempt_value.get("ok", False))
            if provider_ok:
                summary_values.append(f"{provider_name}:ok")
            else:
                summary_values.append(f"{provider_name}:fail({attempt_value.get('error', '')})")
        return " | ".join(summary_values)

    def print_lookup_response(self, response_mapping):
        if not response_mapping.get("ok", False):
            print(response_mapping.get("error", "Unknown error"), file=sys.stderr)
            provider_info = response_mapping.get("provider_info", {}) if isinstance(response_mapping.get("provider_info", {}), dict) else {}
            provider_attempts = self.format_provider_attempts(provider_info)
            if provider_attempts:
                print(f"Provider Attempts: {provider_attempts}", file=sys.stderr)
            self.print_time_gap(response_mapping)
            self.print_request_context(response_mapping)
            return 1
        location_mapping = response_mapping.get("location", {}) if isinstance(response_mapping.get("location", {}), dict) else {}
        country_details = response_mapping.get("country_details", {}) if isinstance(response_mapping.get("country_details", {}), dict) else {}
        network_mapping = response_mapping.get("network", {}) if isinstance(response_mapping.get("network", {}), dict) else {}
        timezone_mapping = response_mapping.get("timezone", {}) if isinstance(response_mapping.get("timezone", {}), dict) else {}
        provider_info = response_mapping.get("provider_info", {}) if isinstance(response_mapping.get("provider_info", {}), dict) else {}
        provider_attempts = self.format_provider_attempts(provider_info)
        print(f"Input: {response_mapping.get('input', '')}")
        print(f"Type: {response_mapping.get('target_type', '')}")
        print(f"IP Type: {response_mapping.get('ip_type', '')}")
        print(f"Resolved Host: {response_mapping.get('resolved_host', '')}")
        print(f"Resolved IPs: {', '.join(response_mapping.get('resolved_ips', []))}")
        print(f"IP: {response_mapping.get('ip', '')}")
        print(f"Provider: {response_mapping.get('provider', '')}")
        print(f"Provider Chain: {provider_info.get('lookup_chain', '')}")
        print(f"Provider Used: {provider_info.get('used_provider', '')}")
        print(f"Fallback Provider: {provider_info.get('fallback_provider', '')}")
        print(f"Free Sources Only: {provider_info.get('free_sources_only', '')}")
        print(f"Provider Attempts: {provider_attempts}")
        print(f"Continent: {location_mapping.get('continent', '')}")
        print(f"Continent Code: {location_mapping.get('continent_code', '')}")
        print(f"Country: {location_mapping.get('country', '')}")
        print(f"Country Code: {location_mapping.get('country_code', '')}")
        print(f"Region: {location_mapping.get('region', '')}")
        print(f"Region Code: {location_mapping.get('region_code', '')}")
        print(f"City: {location_mapping.get('city', '')}")
        print(f"Capital: {country_details.get('capital', '')}")
        print(f"Country Calling Code: {country_details.get('calling_code', '')}")
        print(f"Country Borders: {country_details.get('borders', '')}")
        print(f"Country Is EU: {country_details.get('is_eu', '')}")
        print(f"Country District: {country_details.get('district', '')}")
        print(f"Currency: {country_details.get('currency', '')}")
        print(f"Flag Emoji: {country_details.get('flag_emoji', '')}")
        print(f"Flag Image URL: {country_details.get('flag_image_url', '')}")
        print(f"Postal: {location_mapping.get('postal', '')}")
        print(f"Latitude: {location_mapping.get('latitude', '')}")
        print(f"Longitude: {location_mapping.get('longitude', '')}")
        print(f"ASN: {network_mapping.get('asn', '')}")
        print(f"ASN Name: {network_mapping.get('asn_name', '')}")
        print(f"ISP: {network_mapping.get('isp', '')}")
        print(f"Organization: {network_mapping.get('organization', '')}")
        print(f"Domain: {network_mapping.get('domain', '')}")
        print(f"Reverse DNS: {network_mapping.get('reverse_dns', '')}")
        print(f"Mobile Network: {network_mapping.get('is_mobile', '')}")
        print(f"Proxy Network: {network_mapping.get('is_proxy', '')}")
        print(f"Hosting Network: {network_mapping.get('is_hosting', '')}")
        print(f"Timezone: {timezone_mapping.get('id', '')}")
        print(f"Timezone Abbr: {timezone_mapping.get('abbr', '')}")
        print(f"UTC Offset: {timezone_mapping.get('utc_offset', '')}")
        print(f"Timezone Offset Seconds: {timezone_mapping.get('offset_seconds', '')}")
        print(f"Timezone Current Time: {timezone_mapping.get('current_time', '')}")
        print(f"Timezone Is DST: {timezone_mapping.get('is_dst', '')}")
        self.print_time_gap(response_mapping)
        self.print_request_context(response_mapping)
        return 0

    def run(self):
        parsed_arguments = self.argument_parser.parse_args()
        lookup_target = parsed_arguments.target.strip()
        client_context = self.build_client_context()
        lookup_response = self.lookup_target(lookup_target, client_context)
        return self.print_lookup_response(lookup_response)


if __name__ == "__main__":
    sys.exit(IPTestRuntimeClient().run())
