#!/usr/bin/env python3
import argparse
import ipaddress
import json
import math
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import urllib.parse
import urllib.request
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

try:
    from wcwidth import wcswidth
except Exception:
    wcswidth = None


class IPTestRuntimeClient:
    def __init__(self):
        self.config_path = Path(__file__).resolve().parent / "client_config.json"
        self.server_url = self.load_server_url()
        self.udp_timeout_seconds = self.parse_positive_int(os.getenv("IPTEST_UDP_TIMEOUT_SECONDS", "35"), 35)
        self.speed_test_expected_seconds = self.parse_positive_int(os.getenv("IPTEST_SPEED_TEST_EXPECTED_SECONDS", "12"), 12)
        self.public_ip_urls = ["http://ifconfig.me/ip", "http://api.ipify.org"]
        self.field_emoji_map = self.build_field_emoji_map()
        self.argument_parser = argparse.ArgumentParser(description="IP test runtime client")
        self.argument_parser.add_argument("target", nargs="?", default="")

    def build_field_emoji_map(self):
        return {
            "Lookup Target": "🎯",
            "My IP": "🌐",
            "Resolved IP": "🔎",
            "Provided IP": "📥",
            "Checked IP": "🧭",
            "ASN Name": "🏢",
            "IP Location": "📍",
            "Server-Client Gap": "🕒",
            "CLI Parameter": "💻",
            "Server Input": "📨",
            "Type": "🧾",
            "IP Type": "🧬",
            "Resolved Host": "🖥",
            "Resolved IPs": "🔗",
            "Provider": "🏭",
            "Provider Chain": "🔁",
            "Provider Used": "✅",
            "Fallback Provider": "🔄",
            "Provider Attempts": "🧪",
            "Free Sources Only": "🆓",
            "Continent": "🌍",
            "Continent Code": "🔠",
            "Country": "🌎",
            "Country Code": "🔤",
            "Region": "📌",
            "Region Code": "🔡",
            "City": "🏙",
            "Postal": "📮",
            "Coordinates": "🧭",
            "Capital": "🏛",
            "Calling Code": "📞",
            "Borders": "🧱",
            "Is EU": "🔷",
            "District": "📌",
            "Currency": "💱",
            "Flag Emoji": "🚩",
            "Flag Image URL": "🖼",
            "ASN": "🆔",
            "ISP": "📡",
            "Organization": "🏢",
            "Domain": "🌍",
            "Reverse DNS": "🔁",
            "Mobile Network": "📱",
            "Proxy Network": "🔒",
            "Hosting Network": "🏠",
            "Timezone": "🕒",
            "Timezone Abbr": "🕰",
            "UTC Offset": "🕒",
            "Timezone Offset Seconds": "⏳",
            "Timezone Current Time": "🕑",
            "Timezone Is DST": "🌞",
            "Client Sent (UTC)": "📤",
            "Server Received (UTC)": "📥",
            "Time Gap (ms)": "🕒",
            "Time Gap (seconds)": "⏳",
            "Client Timezone": "🕒",
            "Client UTC Offset Minutes": "🕒",
            "Clock Skew Detected": "⚠",
            "Request Source IP": "📌",
            "Client Hostname": "💻",
            "Client Local IP": "🏠",
            "Client Public IP Hint": "🌎",
            "Local Download": "📥",
            "Local Upload": "📤",
            "Network Mode": "🧵",
            "Network Note": "📝",
            "Speed Scope": "📏",
            "Speed Local IP": "🏠",
            "Local LAN IP": "🏘",
            "Local Public IP": "🌐",
            "Download Raw": "📉",
            "Upload Raw": "📈",
            "Speed Domain": "🌍",
            "Speed Remote IP": "🛰",
            "IP Path": "🛤",
            "IP Distance": "📏",
            "Distance Basis": "📚",
            "Server Location": "📍",
            "Speed Interface": "🔌",
            "Local Latency": "⚡",
            "Local Down Resp": "📉",
            "Local Up Resp": "📈",
            "Local Speed Note": "📌"
        }

    def parse_positive_int(self, value_text, default_value):
        try:
            parsed_value = int(str(value_text).strip())
            if parsed_value > 0:
                return parsed_value
        except Exception:
            pass
        return default_value

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

    def fetch_json(self, request_url):
        try:
            with urllib.request.urlopen(request_url, timeout=10) as response_value:
                return json.loads(response_value.read().decode("utf-8"))
        except Exception:
            return {}

    def is_ip_value(self, value):
        parts = value.split(".")
        if len(parts) != 4:
            return False
        for part in parts:
            if not part.isdigit() or int(part) < 0 or int(part) > 255:
                return False
        return True

    def is_public_ipv4(self, ip_value):
        try:
            parsed_ip = ipaddress.ip_address(str(ip_value))
            return parsed_ip.version == 4 and parsed_ip.is_global
        except Exception:
            return False

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
                udp_socket.settimeout(self.udp_timeout_seconds)
                udp_socket.sendto(json.dumps(payload_mapping).encode("utf-8"), (host_value, port_value))
                response_bytes, _ = udp_socket.recvfrom(65535)
            return json.loads(response_bytes.decode("utf-8"))
        except socket.timeout:
            return {"ok": False, "error": f"UDP request timed out after {self.udp_timeout_seconds}s (server: {host_value}:{port_value})"}
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
        cleaned_text = str(value_text).replace("\u200d", "").replace("\ufe0f", "").replace("\ufe0e", "")
        if wcswidth is not None:
            measured_width = wcswidth(cleaned_text)
            if measured_width >= 0:
                return measured_width
        width_value = 0
        for char_value in cleaned_text:
            if char_value == "\t":
                width_value += 4
                continue
            if self.is_emoji_char(char_value):
                width_value += 2
                continue
            if unicodedata.combining(char_value):
                continue
            if unicodedata.east_asian_width(char_value) in ("F", "W"):
                width_value += 2
            else:
                width_value += 1
        return width_value

    def is_emoji_char(self, char_value):
        code_value = ord(char_value)
        return (0x1F1E6 <= code_value <= 0x1F1FF) or (0x1F300 <= code_value <= 0x1FAFF) or (0x2600 <= code_value <= 0x26FF) or (0x2700 <= code_value <= 0x27BF)

    def label_has_emoji(self, label_text):
        cleaned_text = str(label_text).strip()
        if not cleaned_text:
            return False
        return self.is_emoji_char(cleaned_text[0])

    def emoji_label(self, label_text):
        cleaned_text = str(label_text).strip()
        if not cleaned_text:
            return cleaned_text
        if self.label_has_emoji(cleaned_text):
            return cleaned_text
        emoji_value = self.field_emoji_map.get(cleaned_text, "🔹")
        emoji_value = emoji_value.replace("\ufe0f", "").replace("\ufe0e", "").replace("\u200d", "")
        return f"{emoji_value} {cleaned_text}"

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
        normalized_text = re.sub(r"\s+", " ", str(value_text).replace("\r", " ").replace("\n", " ")).strip()
        if not normalized_text:
            return [""]
        if self.display_width(normalized_text) <= width_value:
            return [normalized_text]
        suffix_text = "..."
        suffix_width = self.display_width(suffix_text)
        allowed_width = max(0, width_value - suffix_width)
        clipped_text = ""
        for char_value in normalized_text:
            if self.display_width(clipped_text + char_value) > allowed_width:
                break
            clipped_text += char_value
        return [f"{clipped_text}{suffix_text}"]

    def join_parts(self, parts_list):
        cleaned_parts = [str(part_value).strip() for part_value in parts_list if str(part_value).strip()]
        return ", ".join(cleaned_parts)

    def parse_float(self, value):
        try:
            return float(value)
        except Exception:
            return None

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

    def extract_speed_value(self, output_text, label_pattern):
        matched_value = re.search(label_pattern, output_text, flags=re.IGNORECASE)
        if not matched_value:
            return "-"
        speed_number = matched_value.group(1).strip()
        speed_unit = matched_value.group(2).strip()
        return f"{speed_number} {speed_unit}"

    def extract_speed_text(self, output_text, label_pattern):
        matched_value = re.search(label_pattern, output_text, flags=re.IGNORECASE)
        if not matched_value:
            return "-"
        return matched_value.group(1).strip()

    def convert_to_mb_per_sec(self, speed_text):
        matched_value = re.search(r"([0-9.]+)\s*([A-Za-z/]+)", str(speed_text))
        if not matched_value:
            return "-"
        try:
            numeric_value = float(matched_value.group(1))
        except Exception:
            return "-"
        unit_text = matched_value.group(2).lower()
        if unit_text in ("mbps", "mbit/s", "mibps"):
            mbps_value = numeric_value
        elif unit_text in ("gbps", "gbit/s", "gibps"):
            mbps_value = numeric_value * 1000
        elif unit_text in ("kbps", "kbit/s", "kibps"):
            mbps_value = numeric_value / 1000
        else:
            return "-"
        return f"{mbps_value / 8:.2f} MB/s"

    def convert_bps_to_mbps_text(self, value_text):
        try:
            numeric_value = float(value_text)
        except Exception:
            return "-"
        if numeric_value <= 0:
            return "-"
        return f"{numeric_value / 1000000:.3f} Mbps"

    def resolve_host_ips(self, host_value):
        resolved_values = []
        try:
            for address_info in socket.getaddrinfo(str(host_value).strip(), None):
                resolved_ip = address_info[4][0]
                if resolved_ip and resolved_ip not in resolved_values:
                    resolved_values.append(resolved_ip)
        except Exception:
            return []
        return resolved_values

    def resolve_host_ips_public_dns(self, host_value):
        response_mapping = self.fetch_json(f"https://dns.google/resolve?name={urllib.parse.quote(str(host_value).strip())}&type=A")
        answer_values = response_mapping.get("Answer", []) if isinstance(response_mapping.get("Answer", []), list) else []
        output_values = []
        for answer_value in answer_values:
            if not isinstance(answer_value, dict):
                continue
            resolved_ip = str(answer_value.get("data", "")).strip()
            if self.is_ip_value(resolved_ip) and resolved_ip not in output_values:
                output_values.append(resolved_ip)
        return output_values

    def choose_ipv4(self, ip_values):
        for ip_value in ip_values:
            if self.is_ip_value(ip_value):
                return ip_value
        return ip_values[0] if ip_values else ""

    def choose_speed_server_ip(self, host_value, local_resolved_ips):
        combined_values = []
        for ip_value in local_resolved_ips + self.resolve_host_ips_public_dns(host_value):
            if ip_value and ip_value not in combined_values:
                combined_values.append(ip_value)
        for ip_value in combined_values:
            if self.is_public_ipv4(ip_value):
                return ip_value
        return self.choose_ipv4(combined_values)

    def resolve_interface_ipv4(self, interface_name):
        cleaned_name = str(interface_name).strip()
        if not cleaned_name or cleaned_name == "-":
            return ""
        try:
            command_result = subprocess.run(["ifconfig", cleaned_name], capture_output=True, text=True, timeout=6)
        except Exception:
            return ""
        output_text = f"{command_result.stdout}\n{command_result.stderr}"
        candidate_values = re.findall(r"\binet\s+(\d+\.\d+\.\d+\.\d+)", output_text)
        for ip_value in candidate_values:
            if self.is_ip_value(ip_value) and ip_value != "127.0.0.1":
                return ip_value
        for ip_value in candidate_values:
            if self.is_ip_value(ip_value):
                return ip_value
        return ""

    def lookup_ip_geo(self, ip_value):
        if not self.is_ip_value(str(ip_value)):
            return {}
        ipwho_payload = self.fetch_json(f"http://ipwho.is/{urllib.parse.quote(str(ip_value))}")
        if isinstance(ipwho_payload, dict) and ipwho_payload.get("success", False):
            return {
                "latitude": ipwho_payload.get("latitude", ""),
                "longitude": ipwho_payload.get("longitude", ""),
                "city": ipwho_payload.get("city", ""),
                "region": ipwho_payload.get("region", ""),
                "country": ipwho_payload.get("country", "")
            }
        ipapi_payload = self.fetch_json(f"http://ip-api.com/json/{urllib.parse.quote(str(ip_value))}?fields=status,lat,lon,city,regionName,country")
        if isinstance(ipapi_payload, dict) and ipapi_payload.get("status") == "success":
            return {
                "latitude": ipapi_payload.get("lat", ""),
                "longitude": ipapi_payload.get("lon", ""),
                "city": ipapi_payload.get("city", ""),
                "region": ipapi_payload.get("regionName", ""),
                "country": ipapi_payload.get("country", "")
            }
        return {}

    def haversine_km(self, lat1, lon1, lat2, lon2):
        lat1_value = self.parse_float(lat1)
        lon1_value = self.parse_float(lon1)
        lat2_value = self.parse_float(lat2)
        lon2_value = self.parse_float(lon2)
        if lat1_value is None or lon1_value is None or lat2_value is None or lon2_value is None:
            return None
        earth_radius_km = 6371.0
        delta_lat = math.radians(lat2_value - lat1_value)
        delta_lon = math.radians(lon2_value - lon1_value)
        lat1_radians = math.radians(lat1_value)
        lat2_radians = math.radians(lat2_value)
        a_value = math.sin(delta_lat / 2) ** 2 + math.cos(lat1_radians) * math.cos(lat2_radians) * math.sin(delta_lon / 2) ** 2
        c_value = 2 * math.atan2(math.sqrt(a_value), math.sqrt(1 - a_value))
        return earth_radius_km * c_value

    def format_distance_text(self, distance_km):
        if distance_km is None:
            return "-"
        distance_miles = distance_km * 0.621371
        return f"{distance_km:.1f} km ({distance_miles:.1f} mi)"

    def detect_network_mode(self, interface_name):
        cleaned_name = str(interface_name).strip().lower()
        if not cleaned_name or cleaned_name == "-":
            return "Unknown", "Interface is not reported"
        vpn_prefix_values = ("utun", "tun", "tap", "ppp", "ipsec", "wg", "tailscale", "zt")
        if cleaned_name.startswith(vpn_prefix_values):
            return "VPN/Tunnel", f"Interface {cleaned_name} looks like a tunnel interface"
        if cleaned_name in ("lo0", "lo"):
            return "Unclear", f"Interface {cleaned_name} is loopback; actual egress may be hidden by system routing/proxy"
        return "Direct/Local Network", f"Interface {cleaned_name} looks like a direct network adapter"

    def extract_speed_endpoint(self, output_text):
        matched_verbose = re.search(r"Test Endpoint:\s*([^\n]+)", str(output_text), flags=re.IGNORECASE)
        if matched_verbose:
            endpoint_text = matched_verbose.group(1).strip()
            if endpoint_text:
                return endpoint_text
        matched_json = re.search(r"\"test_endpoint\"\s*:\s*\"([^\"]+)\"", str(output_text), flags=re.IGNORECASE)
        if matched_json:
            endpoint_text = matched_json.group(1).strip()
            if endpoint_text:
                return endpoint_text
        return "Apple networkQuality auto endpoint (not exposed)"

    def build_speed_test_mapping_from_json(self, output_text, default_source):
        try:
            payload_mapping = json.loads(str(output_text))
        except Exception:
            return {}
        if not isinstance(payload_mapping, dict):
            return {}
        return {
            "download_speed": self.convert_bps_to_mbps_text(payload_mapping.get("dl_throughput", "")),
            "upload_speed": self.convert_bps_to_mbps_text(payload_mapping.get("ul_throughput", "")),
            "idle_latency": payload_mapping.get("base_rtt", "-"),
            "downlink_responsiveness": payload_mapping.get("dl_responsiveness", "-"),
            "uplink_responsiveness": payload_mapping.get("ul_responsiveness", "-"),
            "speed_server": str(payload_mapping.get("test_endpoint", "")).strip() or self.extract_speed_endpoint(output_text),
            "speed_interface": str(payload_mapping.get("interface_name", "")).strip() or "-",
            "source": default_source
        }

    def enrich_speed_test_mapping(self, speed_test_mapping, lookup_response, client_context):
        output_mapping = dict(speed_test_mapping)
        request_mapping = lookup_response.get("request_context", {}) if isinstance(lookup_response.get("request_context", {}), dict) else {}
        location_mapping = lookup_response.get("location", {}) if isinstance(lookup_response.get("location", {}), dict) else {}
        local_lan_ip = str(client_context.get("client_local_ip", "")).strip() or str(request_mapping.get("client_local_ip", "")).strip() or "-"
        local_public_ip = str(lookup_response.get("ip", "")).strip() or str(request_mapping.get("request_source_ip", "")).strip() or "-"
        speed_server_domain = str(output_mapping.get("speed_server", "")).strip() or "-"
        speed_server_ips = self.resolve_host_ips(speed_server_domain) if speed_server_domain not in ("", "-") else []
        speed_server_ip = self.choose_speed_server_ip(speed_server_domain, speed_server_ips) if speed_server_domain not in ("", "-") else "-"
        speed_interface = str(output_mapping.get("speed_interface", "")).strip() or "-"
        interface_ip = self.resolve_interface_ipv4(speed_interface) or "-"
        if interface_ip in ("", "-", "127.0.0.1"):
            local_speed_ip = local_lan_ip
        else:
            local_speed_ip = interface_ip
        speed_server_geo = self.lookup_ip_geo(speed_server_ip) if speed_server_ip != "-" else {}
        speed_server_location = self.join_parts([speed_server_geo.get("city", ""), speed_server_geo.get("region", ""), speed_server_geo.get("country", "")]) or "-"
        local_geo = self.lookup_ip_geo(local_public_ip) if self.is_ip_value(local_public_ip) else {}
        local_geo_latitude = local_geo.get("latitude", "") or location_mapping.get("latitude", "")
        local_geo_longitude = local_geo.get("longitude", "") or location_mapping.get("longitude", "")
        distance_km = self.haversine_km(local_geo_latitude, local_geo_longitude, speed_server_geo.get("latitude", ""), speed_server_geo.get("longitude", ""))
        network_mode, network_note = self.detect_network_mode(speed_interface)
        output_mapping["local_lan_ip"] = local_lan_ip
        output_mapping["local_public_ip"] = local_public_ip
        output_mapping["local_speed_ip"] = local_speed_ip
        output_mapping["speed_server_domain"] = speed_server_domain
        output_mapping["speed_server_ip"] = speed_server_ip
        output_mapping["speed_server_location"] = speed_server_location
        output_mapping["speed_route"] = f"{local_speed_ip} -> {speed_server_ip}" if local_speed_ip != "-" and speed_server_ip != "-" else "-"
        output_mapping["ip_distance"] = self.format_distance_text(distance_km)
        output_mapping["distance_basis"] = "Local public IP geolocation -> speed remote IP geolocation"
        output_mapping["network_mode"] = network_mode
        output_mapping["network_note"] = network_note
        output_mapping["speed_scope"] = "Speed is measured on your current active route (VPN included if active)"
        return output_mapping

    def build_speed_test_mapping_from_output(self, output_text, default_source):
        combined_responsiveness = self.extract_speed_text(output_text, r"Responsiveness:\s*([^\n]+)")
        downlink_responsiveness = self.extract_speed_text(output_text, r"(?:Downlink|Download|Downstream)\s+Responsiveness:\s*([^\n]+)")
        uplink_responsiveness = self.extract_speed_text(output_text, r"(?:Uplink|Upload|Upstream)\s+Responsiveness:\s*([^\n]+)")
        if downlink_responsiveness == "-" and combined_responsiveness != "-":
            downlink_responsiveness = combined_responsiveness
        if uplink_responsiveness == "-" and combined_responsiveness != "-":
            uplink_responsiveness = combined_responsiveness
        return {
            "download_speed": self.extract_speed_value(output_text, r"(?:Downlink|Download|Downstream)\s+capacity:\s*([0-9.]+)\s*([A-Za-z/]+)"),
            "upload_speed": self.extract_speed_value(output_text, r"(?:Uplink|Upload|Upstream)\s+capacity:\s*([0-9.]+)\s*([A-Za-z/]+)"),
            "idle_latency": self.extract_speed_text(output_text, r"Idle\s+Latency:\s*([^\n]+)"),
            "downlink_responsiveness": downlink_responsiveness,
            "uplink_responsiveness": uplink_responsiveness,
            "speed_server": self.extract_speed_endpoint(output_text),
            "speed_interface": self.extract_speed_text(output_text, r"Interface:\s*([^\n]+)"),
            "source": default_source
        }

    def strip_ansi_text(self, value_text):
        return re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", str(value_text))

    def extract_live_capacity_pair(self, value_text):
        cleaned_text = self.strip_ansi_text(value_text)
        download_speed = self.extract_speed_value(cleaned_text, r"Downlink:\s*(?:capacity\s*)?([0-9.]+)\s*([A-Za-z/]+)")
        upload_speed = self.extract_speed_value(cleaned_text, r"Uplink:\s*(?:capacity\s*)?([0-9.]+)\s*([A-Za-z/]+)")
        return download_speed, upload_speed

    def print_speed_test_progress(self, progress_percent, download_speed, upload_speed):
        bounded_percent = max(0, min(100, int(progress_percent)))
        download_mb_text = self.convert_to_mb_per_sec(download_speed) if str(download_speed).strip() not in ("", "-") else "-"
        upload_mb_text = self.convert_to_mb_per_sec(upload_speed) if str(upload_speed).strip() not in ("", "-") else "-"
        progress_text = f"Local speed test progress: {bounded_percent:3d}% | Download {download_mb_text} | Upload {upload_mb_text}"
        sys.stdout.write(f"\r{progress_text}   ")
        sys.stdout.flush()

    def run_local_speed_test(self):
        if platform.system() != "Darwin":
            return {"download_speed": "-", "upload_speed": "-", "idle_latency": "-", "downlink_responsiveness": "-", "uplink_responsiveness": "-", "speed_server": "-", "speed_interface": "-", "source": "Unavailable (macOS only for local speed test)"}
        try:
            speed_process = subprocess.run(["networkQuality", "-s", "-c"], capture_output=True, text=True, timeout=90)
        except FileNotFoundError:
            return {"download_speed": "-", "upload_speed": "-", "idle_latency": "-", "downlink_responsiveness": "-", "uplink_responsiveness": "-", "speed_server": "-", "speed_interface": "-", "source": "Unavailable (networkQuality command not found for local speed test)"}
        except subprocess.TimeoutExpired:
            return {"download_speed": "-", "upload_speed": "-", "idle_latency": "-", "downlink_responsiveness": "-", "uplink_responsiveness": "-", "speed_server": "-", "speed_interface": "-", "source": "Unavailable (local speed test timeout)"}
        except Exception:
            return {"download_speed": "-", "upload_speed": "-", "idle_latency": "-", "downlink_responsiveness": "-", "uplink_responsiveness": "-", "speed_server": "-", "speed_interface": "-", "source": "Unavailable (local speed test error)"}
        output_text = f"{speed_process.stdout}\n{speed_process.stderr}"
        speed_test_mapping = self.build_speed_test_mapping_from_json(speed_process.stdout, "General local network speed (not lookup target IP/domain)")
        if speed_test_mapping:
            return speed_test_mapping
        return self.build_speed_test_mapping_from_output(output_text, "General local network speed (not lookup target IP/domain)")

    def run_local_speed_test_with_progress(self):
        if platform.system() != "Darwin":
            return self.run_local_speed_test()
        try:
            import pty
            import select
            import time
        except Exception:
            return self.run_local_speed_test()
        master_fd = None
        try:
            master_fd, slave_fd = pty.openpty()
            speed_process = subprocess.Popen(["networkQuality", "-v"], stdin=subprocess.DEVNULL, stdout=slave_fd, stderr=slave_fd)
            os.close(slave_fd)
            output_values = []
            pending_text = ""
            latest_download = "-"
            latest_upload = "-"
            start_time = time.monotonic()
            expected_seconds = max(8, self.speed_test_expected_seconds)
            self.print_speed_test_progress(1, latest_download, latest_upload)
            while speed_process.poll() is None:
                ready_values, _, _ = select.select([master_fd], [], [], 0.3)
                if not ready_values:
                    elapsed_seconds = time.monotonic() - start_time
                    progress_percent = min(99, int((elapsed_seconds / expected_seconds) * 100))
                    self.print_speed_test_progress(progress_percent, latest_download, latest_upload)
                    continue
                try:
                    chunk_bytes = os.read(master_fd, 4096)
                except OSError as error_value:
                    if getattr(error_value, "errno", None) == 5:
                        break
                    raise
                if not chunk_bytes:
                    continue
                chunk_text = chunk_bytes.decode("utf-8", errors="ignore")
                output_values.append(chunk_text)
                pending_text += chunk_text
                line_values = re.split(r"[\r\n]", pending_text)
                pending_text = line_values.pop()
                for line_text in line_values:
                    cleaned_line = self.strip_ansi_text(line_text).strip()
                    if not cleaned_line:
                        continue
                    download_speed, upload_speed = self.extract_live_capacity_pair(cleaned_line)
                    if download_speed != "-":
                        latest_download = download_speed
                    if upload_speed != "-":
                        latest_upload = upload_speed
                    elapsed_seconds = time.monotonic() - start_time
                    progress_percent = min(99, int((elapsed_seconds / expected_seconds) * 100))
                    self.print_speed_test_progress(progress_percent, latest_download, latest_upload)
            while True:
                ready_values, _, _ = select.select([master_fd], [], [], 0.05)
                if not ready_values:
                    break
                try:
                    chunk_bytes = os.read(master_fd, 4096)
                except OSError as error_value:
                    if getattr(error_value, "errno", None) == 5:
                        break
                    raise
                if not chunk_bytes:
                    break
                output_values.append(chunk_bytes.decode("utf-8", errors="ignore"))
            os.close(master_fd)
            master_fd = None
            output_text = "".join(output_values)
            speed_test_mapping = self.build_speed_test_mapping_from_output(output_text, "General local network speed (not lookup target IP/domain)")
            if speed_test_mapping.get("download_speed", "-") == "-" and latest_download != "-":
                speed_test_mapping["download_speed"] = latest_download
            if speed_test_mapping.get("upload_speed", "-") == "-" and latest_upload != "-":
                speed_test_mapping["upload_speed"] = latest_upload
            self.print_speed_test_progress(100, speed_test_mapping.get("download_speed", "-"), speed_test_mapping.get("upload_speed", "-"))
            print()
            return speed_test_mapping
        except Exception:
            if master_fd is not None:
                try:
                    os.close(master_fd)
                except Exception:
                    pass
            print("\rLocal speed test progress: failed")
            return self.run_local_speed_test()

    def print_table_section(self, title_text, rows_list):
        normalized_rows = []
        for key_text, value in rows_list:
            normalized_value = self.normalize_value(value)
            normalized_rows.append((self.emoji_label(key_text), normalized_value))
        if not normalized_rows:
            return
        key_width = max(self.display_width("Field"), max(self.display_width(key_text) for key_text, _ in normalized_rows))
        max_value_size = max(self.display_width("Value"), max(self.display_width(value_text) for _, value_text in normalized_rows))
        terminal_columns = min(140, shutil.get_terminal_size(fallback=(140, 20)).columns)
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

    def print_compact_two_side_table(self, title_text, left_title, left_rows, right_title, right_rows):
        normalized_left_rows = [(self.emoji_label(key_text), self.normalize_value(value)) for key_text, value in left_rows]
        normalized_right_rows = [(self.emoji_label(key_text), self.normalize_value(value)) for key_text, value in right_rows]
        if not normalized_left_rows and not normalized_right_rows:
            return
        left_key_width = max(self.display_width(left_title), max((self.display_width(key_text) for key_text, _ in normalized_left_rows), default=0))
        right_key_width = max(self.display_width(right_title), max((self.display_width(key_text) for key_text, _ in normalized_right_rows), default=0))
        left_key_width = max(12, min(24, left_key_width))
        right_key_width = max(12, min(24, right_key_width))
        terminal_columns = min(180, shutil.get_terminal_size(fallback=(180, 20)).columns)
        fixed_width = 13
        available_value_width = terminal_columns - fixed_width - left_key_width - right_key_width
        if available_value_width < 48:
            available_value_width = 48
        desired_left_value_width = max(self.display_width("Value"), max((self.display_width(value_text) for _, value_text in normalized_left_rows), default=0))
        desired_right_value_width = max(self.display_width("Value"), max((self.display_width(value_text) for _, value_text in normalized_right_rows), default=0))
        total_desired_width = desired_left_value_width + desired_right_value_width
        if total_desired_width <= 0:
            left_value_width = available_value_width // 2
        else:
            left_value_width = int(available_value_width * desired_left_value_width / total_desired_width)
        right_value_width = available_value_width - left_value_width
        if left_value_width < 24:
            left_value_width = 24
            right_value_width = max(24, available_value_width - left_value_width)
        if right_value_width < 24:
            right_value_width = 24
            left_value_width = max(24, available_value_width - right_value_width)
        separator_text = f"+-{'-' * left_key_width}-+-{'-' * left_value_width}-+-{'-' * right_key_width}-+-{'-' * right_value_width}-+"
        print(f"\n{title_text}")
        print(separator_text)
        print(f"| {self.pad_display(left_title, left_key_width)} | {self.pad_display('Value', left_value_width)} | {self.pad_display(right_title, right_key_width)} | {self.pad_display('Value', right_value_width)} |")
        print(separator_text)
        row_count = max(len(normalized_left_rows), len(normalized_right_rows))
        for row_index in range(row_count):
            if row_index < len(normalized_left_rows):
                left_key_text, left_value_text = normalized_left_rows[row_index]
            else:
                left_key_text, left_value_text = "", ""
            if row_index < len(normalized_right_rows):
                right_key_text, right_value_text = normalized_right_rows[row_index]
            else:
                right_key_text, right_value_text = "", ""
            left_value_lines = self.split_lines(left_value_text, left_value_width)
            right_value_lines = self.split_lines(right_value_text, right_value_width)
            line_count = max(len(left_value_lines), len(right_value_lines))
            for line_index in range(line_count):
                left_key_cell = left_key_text if line_index == 0 else ""
                right_key_cell = right_key_text if line_index == 0 else ""
                left_value_cell = left_value_lines[line_index] if line_index < len(left_value_lines) else ""
                right_value_cell = right_value_lines[line_index] if line_index < len(right_value_lines) else ""
                if line_index > 0 and left_value_cell == "" and right_value_cell == "":
                    continue
                print(f"| {self.pad_display(left_key_cell, left_key_width)} | {self.pad_display(left_value_cell, left_value_width)} | {self.pad_display(right_key_cell, right_key_width)} | {self.pad_display(right_value_cell, right_value_width)} |")
        print(separator_text)

    def build_lookup_detail_rows(self, lookup_summary, response_mapping, provider_info, provider_attempts, location_mapping, country_details, network_mapping, timezone_mapping):
        return [
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
            ("Flag Emoji", self.flag_emoji_to_text(country_details.get("flag_emoji", ""))),
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
        ]

    def flag_emoji_to_text(self, flag_value):
        text_value = str(flag_value).strip()
        if not text_value:
            return "-"
        letters_value = []
        for char_value in text_value:
            code_value = ord(char_value)
            if 0x1F1E6 <= code_value <= 0x1F1FF:
                letters_value.append(chr(code_value - 0x1F1E6 + ord("A")))
        if len(letters_value) >= 2:
            return "".join(letters_value)
        return text_value

    def build_client_timing_rows(self, timing_mapping, request_mapping):
        return [
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
        ]

    def build_local_speed_detail_rows(self, speed_test_mapping):
        speed_server_domain = speed_test_mapping.get("speed_server_domain", speed_test_mapping.get("speed_server", "-"))
        return [
            ("Local Download", self.convert_to_mb_per_sec(speed_test_mapping.get("download_speed", "-"))),
            ("Local Upload", self.convert_to_mb_per_sec(speed_test_mapping.get("upload_speed", "-"))),
            ("Network Mode", speed_test_mapping.get("network_mode", "-")),
            ("Speed Local IP", speed_test_mapping.get("local_speed_ip", "-")),
            ("Local Public IP", speed_test_mapping.get("local_public_ip", "-")),
            ("Speed Domain", speed_server_domain),
            ("Speed Remote IP", speed_test_mapping.get("speed_server_ip", "-")),
            ("IP Path", speed_test_mapping.get("speed_route", "-")),
            ("IP Distance", speed_test_mapping.get("ip_distance", "-")),
            ("Server Location", speed_test_mapping.get("speed_server_location", "-")),
            ("Speed Interface", speed_test_mapping.get("speed_interface", "-")),
            ("Local Latency", speed_test_mapping.get("idle_latency", "-")),
            ("Local Down Resp", speed_test_mapping.get("downlink_responsiveness", "-")),
            ("Local Up Resp", speed_test_mapping.get("uplink_responsiveness", "-"))
        ]

    def print_lookup_response(self, response_mapping, user_target_text):
        if not response_mapping.get("ok", False):
            print(response_mapping.get("error", "Unknown error"), file=sys.stderr)
            provider_info = response_mapping.get("provider_info", {}) if isinstance(response_mapping.get("provider_info", {}), dict) else {}
            provider_attempts = self.format_provider_attempts(provider_info)
            if provider_attempts:
                print(f"Provider Attempts: {provider_attempts}", file=sys.stderr)
            self.print_time_gap(response_mapping)
            self.print_request_context(response_mapping)
            return 1, [], []
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
        lookup_rows = self.build_lookup_detail_rows(lookup_summary, response_mapping, provider_info, provider_attempts, location_mapping, country_details, network_mapping, timezone_mapping)
        timing_rows = self.build_client_timing_rows(timing_mapping, request_mapping)
        return 0, lookup_rows, timing_rows

    def run(self):
        parsed_arguments = self.argument_parser.parse_args()
        lookup_target = parsed_arguments.target.strip()
        client_context = self.build_client_context()
        lookup_response = self.lookup_target(lookup_target, client_context)
        response_status, lookup_rows, timing_rows = self.print_lookup_response(lookup_response, lookup_target)
        if response_status != 0:
            return response_status
        right_rows = list(timing_rows)
        if not lookup_target:
            print("\nRunning local speed test (general local machine network)...")
            speed_test_mapping = self.run_local_speed_test_with_progress()
            enriched_speed_mapping = self.enrich_speed_test_mapping(speed_test_mapping, lookup_response, client_context)
            right_rows.extend(self.build_local_speed_detail_rows(enriched_speed_mapping))
        self.print_compact_two_side_table("📚 Details", "🌍 Lookup Details", lookup_rows, "🧭 Client / ⚡ Local", right_rows)
        return response_status


if __name__ == "__main__":
    sys.exit(IPTestRuntimeClient().run())
