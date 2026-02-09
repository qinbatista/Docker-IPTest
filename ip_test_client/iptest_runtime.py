#!/usr/bin/env python3
import argparse
import json
import os
import platform
import shutil
import socket
import sys
import urllib.parse
import urllib.request
import unicodedata
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
        return "timov4.qinyupeng.com:8000"

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

    def normalize_value(self, value):
        if value is None:
            return "-"
        if isinstance(value, bool):
            return "yes" if value else "no"
        if isinstance(value, list):
            list_value = ", ".join(str(item_value) for item_value in value if str(item_value).strip())
            return list_value if list_value else "-"
        value_text = str(value).strip()
        return value_text if value_text else "-"

    def display_width(self, value_text):
        width_value = 0
        for char_value in str(value_text):
            if char_value == "\t":
                width_value += 4
                continue
            if unicodedata.combining(char_value):
                continue
            if unicodedata.east_asian_width(char_value) in ("F", "W"):
                width_value += 2
            else:
                width_value += 1
        return width_value

    def pad_display(self, value_text, width_value):
        text_value = str(value_text)
        fill_size = max(0, width_value - self.display_width(text_value))
        return text_value + (" " * fill_size)

    def split_long_word(self, word_text, width_value):
        output_lines = []
        chunk_value = ""
        for char_value in word_text:
            next_value = chunk_value + char_value
            if chunk_value and self.display_width(next_value) > width_value:
                output_lines.append(chunk_value)
                chunk_value = char_value
            else:
                chunk_value = next_value
        if chunk_value:
            output_lines.append(chunk_value)
        return output_lines if output_lines else [""]

    def split_lines(self, value_text, width_value):
        paragraph_values = str(value_text).splitlines()
        if not paragraph_values:
            return [""]
        wrapped_lines = []
        for paragraph_value in paragraph_values:
            if paragraph_value == "":
                wrapped_lines.append("")
                continue
            current_line = ""
            words_value = paragraph_value.split(" ")
            for word_value in words_value:
                if current_line:
                    candidate_line = f"{current_line} {word_value}"
                else:
                    candidate_line = word_value
                if self.display_width(candidate_line) <= width_value:
                    current_line = candidate_line
                    continue
                if current_line:
                    wrapped_lines.append(current_line)
                    current_line = ""
                if self.display_width(word_value) <= width_value:
                    current_line = word_value
                    continue
                long_word_lines = self.split_long_word(word_value, width_value)
                wrapped_lines.extend(long_word_lines[:-1])
                current_line = long_word_lines[-1]
            wrapped_lines.append(current_line if current_line else "")
        return wrapped_lines if wrapped_lines else [""]

    def join_parts(self, parts_list):
        cleaned_parts = [str(part_value).strip() for part_value in parts_list if str(part_value).strip()]
        return ", ".join(cleaned_parts)

    def build_lookup_target_summary(self, user_target_text, response_mapping):
        parameter_text = str(user_target_text).strip()
        target_type_text = str(response_mapping.get("target_type", "")).strip().lower()
        if not parameter_text:
            return {
                "lookup_target": "(auto from local machine)",
                "checked_ip_label": "My IP",
                "parameter_value": "(empty)"
            }
        if target_type_text == "domain":
            return {
                "lookup_target": f"{parameter_text} (domain)",
                "checked_ip_label": "Resolved IP",
                "parameter_value": parameter_text
            }
        if target_type_text == "ip":
            return {
                "lookup_target": f"{parameter_text} (ip)",
                "checked_ip_label": "Provided IP",
                "parameter_value": parameter_text
            }
        return {
            "lookup_target": parameter_text,
            "checked_ip_label": "Checked IP",
            "parameter_value": parameter_text
        }

    def print_table_section(self, title_text, rows_list):
        normalized_rows = []
        for key_text, value in rows_list:
            normalized_value = self.normalize_value(value)
            normalized_rows.append((key_text, normalized_value))
        if not normalized_rows:
            return
        key_width = max(self.display_width("Field"), max(self.display_width(key_text) for key_text, _ in normalized_rows))
        max_value_size = max(self.display_width("Value"), max(self.display_width(value_text) for _, value_text in normalized_rows))
        terminal_columns = shutil.get_terminal_size(fallback=(140, 20)).columns
        available_value_width = terminal_columns - key_width - 7
        if available_value_width < 36:
            available_value_width = 36
        preferred_width = max(64, min(120, max_value_size))
        value_width = min(preferred_width, available_value_width)
        separator_text = f"+-{'-' * key_width}-+-{'-' * value_width}-+"
        print(f"\n{title_text}")
        print(separator_text)
        print(f"| {self.pad_display('Field', key_width)} | {self.pad_display('Value', value_width)} |")
        print(separator_text)
        for key_text, value_text in normalized_rows:
            value_lines = self.split_lines(value_text, value_width)
            print(f"| {self.pad_display(key_text, key_width)} | {self.pad_display(value_lines[0], value_width)} |")
            for continuation_line in value_lines[1:]:
                print(f"| {self.pad_display('', key_width)} | {self.pad_display(continuation_line, value_width)} |")
        print(separator_text)

    def print_lookup_response(self, response_mapping, user_target_text):
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
        timing_mapping = response_mapping.get("timing", {}) if isinstance(response_mapping.get("timing", {}), dict) else {}
        request_mapping = response_mapping.get("request_context", {}) if isinstance(response_mapping.get("request_context", {}), dict) else {}
        lookup_summary = self.build_lookup_target_summary(user_target_text, response_mapping)
        my_location = self.join_parts([location_mapping.get("city", ""), location_mapping.get("region", ""), location_mapping.get("country", "")])
        asn_name_text = network_mapping.get("asn_name", "") or network_mapping.get("organization", "") or network_mapping.get("isp", "")
        time_gap_text = ""
        if timing_mapping.get("gap_ms", "") != "":
            time_gap_text = f"{timing_mapping.get('gap_ms', '')} ms ({timing_mapping.get('gap_seconds', '')} sec)"
        important_rows = [
            ("Lookup Target", lookup_summary.get("lookup_target", "")),
            (lookup_summary.get("checked_ip_label", "Checked IP"), response_mapping.get("ip", "")),
            ("ASN Name", asn_name_text),
            ("IP Location", my_location),
            ("Server-Client Gap", time_gap_text)
        ]
        self.print_table_section("⭐ Important", important_rows)
        self.print_table_section("📋 Lookup Details", [
            ("CLI Parameter", lookup_summary.get("parameter_value", "")),
            ("Server Input", response_mapping.get("input", "")),
            ("Type", response_mapping.get("target_type", "")),
            ("IP Type", response_mapping.get("ip_type", "")),
            ("Resolved Host", response_mapping.get("resolved_host", "")),
            ("Resolved IPs", response_mapping.get("resolved_ips", [])),
            ("Provider", response_mapping.get("provider", "")),
            ("Provider Chain", provider_info.get("lookup_chain", "")),
            ("Provider Used", provider_info.get("used_provider", "")),
            ("Fallback Provider", provider_info.get("fallback_provider", "")),
            ("Provider Attempts", provider_attempts),
            ("Free Sources Only", provider_info.get("free_sources_only", "")),
            ("Continent", location_mapping.get("continent", "")),
            ("Continent Code", location_mapping.get("continent_code", "")),
            ("Country", location_mapping.get("country", "")),
            ("Country Code", location_mapping.get("country_code", "")),
            ("Region", location_mapping.get("region", "")),
            ("Region Code", location_mapping.get("region_code", "")),
            ("City", location_mapping.get("city", "")),
            ("Postal", location_mapping.get("postal", "")),
            ("Coordinates", self.join_parts([location_mapping.get("latitude", ""), location_mapping.get("longitude", "")])),
            ("Capital", country_details.get("capital", "")),
            ("Calling Code", country_details.get("calling_code", "")),
            ("Borders", country_details.get("borders", "")),
            ("Is EU", country_details.get("is_eu", "")),
            ("District", country_details.get("district", "")),
            ("Currency", country_details.get("currency", "")),
            ("Flag Emoji", country_details.get("flag_emoji", "")),
            ("Flag Image URL", country_details.get("flag_image_url", "")),
            ("ASN", network_mapping.get("asn", "")),
            ("ISP", network_mapping.get("isp", "")),
            ("Organization", network_mapping.get("organization", "")),
            ("Domain", network_mapping.get("domain", "")),
            ("Reverse DNS", network_mapping.get("reverse_dns", "")),
            ("Mobile Network", network_mapping.get("is_mobile", "")),
            ("Proxy Network", network_mapping.get("is_proxy", "")),
            ("Hosting Network", network_mapping.get("is_hosting", "")),
            ("Timezone", timezone_mapping.get("id", "")),
            ("Timezone Abbr", timezone_mapping.get("abbr", "")),
            ("UTC Offset", timezone_mapping.get("utc_offset", "")),
            ("Timezone Offset Seconds", timezone_mapping.get("offset_seconds", "")),
            ("Timezone Current Time", timezone_mapping.get("current_time", "")),
            ("Timezone Is DST", timezone_mapping.get("is_dst", ""))
        ])
        self.print_table_section("🧭 Client & Timing", [
            ("Client Sent (UTC)", timing_mapping.get("client_sent_at_utc", "")),
            ("Server Received (UTC)", timing_mapping.get("server_received_at_utc", "")),
            ("Time Gap (ms)", timing_mapping.get("gap_ms", "")),
            ("Time Gap (seconds)", timing_mapping.get("gap_seconds", "")),
            ("Client Timezone", timing_mapping.get("client_timezone_name", "")),
            ("Client UTC Offset Minutes", timing_mapping.get("client_utc_offset_minutes", "")),
            ("Clock Skew Detected", timing_mapping.get("clock_skew_detected", "")),
            ("Request Source IP", request_mapping.get("request_source_ip", "")),
            ("Client Hostname", request_mapping.get("client_hostname", "")),
            ("Client Local IP", request_mapping.get("client_local_ip", "")),
            ("Client Public IP Hint", request_mapping.get("client_public_ip_hint", ""))
        ])
        return 0

    def run(self):
        parsed_arguments = self.argument_parser.parse_args()
        lookup_target = parsed_arguments.target.strip()
        client_context = self.build_client_context()
        lookup_response = self.lookup_target(lookup_target, client_context)
        return self.print_lookup_response(lookup_response, lookup_target)


if __name__ == "__main__":
    sys.exit(IPTestRuntimeClient().run())
