#!/usr/bin/env python3
"""Update the site's Apple release data from official Apple sources."""

from __future__ import annotations

import argparse
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen


SECURITY_RELEASES_URL = "https://support.apple.com/en-us/100100"
DEVELOPER_RELEASES_URL = "https://developer.apple.com/news/releases/rss/releases.rss"
HOMEPOD_RELEASES_URL = "https://support.apple.com/en-us/108045"
USER_AGENT = "version-apple-page-release-checker/1.0"

STABLE_PATTERNS = {
    "ios": re.compile(r"\biOS (\d+(?:\.\d+){0,2})"),
    "ipados": re.compile(r"\biPadOS (\d+(?:\.\d+){0,2})"),
    "macos": re.compile(r"^macOS .+? (\d+(?:\.\d+){0,2})$"),
    "tvos": re.compile(r"^tvOS (\d+(?:\.\d+){0,2})$"),
    "watchos": re.compile(r"^watchOS (\d+(?:\.\d+){0,2})$"),
    "visionos": re.compile(r"^visionOS (\d+(?:\.\d+){0,2})$"),
    "safari": re.compile(r"^Safari (\d+(?:\.\d+){0,2})$"),
}
DISPLAY_NAMES = {
    "ios": "iOS",
    "ipados": "iPadOS",
    "tvos": "tvOS",
    "watchos": "watchOS",
    "visionos": "visionOS",
    "safari": "Safari",
    "xcode": "Xcode",
    "homepod": "HomePod software",
}
DEVELOPER_PRODUCTS = {
    "iOS": "ios",
    "iPadOS": "ipados",
    "macOS": "macos",
    "tvOS": "tvos",
    "watchOS": "watchos",
    "visionOS": "visionos",
    "Xcode": "xcode",
}


def version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


class ReleaseTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[tuple[str, str | None]]] = []
        self.row: list[tuple[str, str | None]] = []
        self.cell_parts: list[str] = []
        self.cell_href: str | None = None
        self.in_row = False
        self.in_cell = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self.in_row = True
            self.row = []
        elif self.in_row and tag in {"td", "th"}:
            self.in_cell = True
            self.cell_parts = []
            self.cell_href = None
        elif self.in_cell and tag == "a":
            self.cell_href = dict(attrs).get("href")

    def handle_data(self, data: str) -> None:
        if self.in_cell:
            self.cell_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self.in_cell and tag in {"td", "th"}:
            text = " ".join("".join(self.cell_parts).split())
            self.row.append((text, self.cell_href))
            self.in_cell = False
        elif self.in_row and tag == "tr":
            if self.row:
                self.rows.append(self.row)
            self.in_row = False


class HomePodParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.heading_parts: list[str] = []
        self.date_parts: list[str] = []
        self.headings: list[str] = []
        self.dates: list[str] = []
        self.in_heading = False
        self.in_time = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "h2":
            self.in_heading = True
            self.heading_parts = []
        elif tag == "time":
            self.in_time = True
            self.date_parts = []

    def handle_data(self, data: str) -> None:
        if self.in_heading:
            self.heading_parts.append(data)
        if self.in_time:
            self.date_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "h2" and self.in_heading:
            self.headings.append(" ".join("".join(self.heading_parts).split()))
            self.in_heading = False
        elif tag == "time" and self.in_time:
            self.dates.append(" ".join("".join(self.date_parts).split()))
            self.in_time = False


def parse_stable_releases(html: str) -> dict[str, dict[str, str]]:
    parser = ReleaseTableParser()
    parser.feed(html)
    releases: dict[str, dict[str, str]] = {}

    for row in parser.rows:
        if len(row) < 3:
            continue
        source_title, source = row[0]
        date = row[2][0]
        if not source or not re.fullmatch(r"\d{2} [A-Z][a-z]{2} \d{4}", date):
            continue
        for product, pattern in STABLE_PATTERNS.items():
            match = pattern.search(source_title)
            if not match:
                continue
            version = match.group(1)
            current = releases.get(product)
            if current and version_key(current["version"]) >= version_key(version):
                continue
            title = source_title if product == "macos" else f"{DISPLAY_NAMES[product]} {version}"
            releases[product] = {
                "title": title,
                "version": version,
                "date": date,
                "source": source,
            }

    missing = sorted(set(STABLE_PATTERNS) - set(releases))
    if missing:
        raise ValueError(f"Apple security page did not contain: {', '.join(missing)}")
    return releases


def parse_developer_releases(xml: str) -> tuple[dict[str, str], dict[str, dict[str, str]]]:
    root = ET.fromstring(xml)
    stable_xcode: dict[str, str] | None = None
    betas: dict[str, dict[str, str]] = {}
    beta_ranks: dict[str, tuple[tuple[int, ...], int]] = {}

    for item in root.findall("./channel/item"):
        title = item.findtext("title", "").strip()
        source = item.findtext("link", "").strip()
        published = item.findtext("pubDate", "").strip()
        if not source or not published:
            continue
        date = parsedate_to_datetime(published).strftime("%d %b %Y")

        stable_match = re.fullmatch(r"Xcode (\d+(?:\.\d+){0,2}) \([^)]+\)", title)
        if stable_match:
            version = stable_match.group(1)
            if not stable_xcode or version_key(version) > version_key(stable_xcode["version"]):
                stable_xcode = {
                    "title": f"Xcode {version}",
                    "version": version,
                    "date": date,
                    "source": source,
                }
            continue

        beta_match = re.fullmatch(
            r"(iOS|iPadOS|macOS|tvOS|watchOS|visionOS|Xcode) "
            r"(\d+(?:\.\d+){0,2}) beta(?: (\d+))? \([^)]+\)",
            title,
            re.IGNORECASE,
        )
        if not beta_match:
            continue
        product_name, version, beta_number = beta_match.groups()
        canonical_name = next(name for name in DEVELOPER_PRODUCTS if name.lower() == product_name.lower())
        product = DEVELOPER_PRODUCTS[canonical_name]
        rank = (version_key(version), int(beta_number or 0))
        if product in beta_ranks and beta_ranks[product] >= rank:
            continue
        beta_label = f"Beta {beta_number}" if beta_number else "Beta"
        betas[product] = {
            "title": f"{canonical_name} {version}",
            "version": version,
            "beta": beta_label,
            "date": date,
            "source": source,
        }
        beta_ranks[product] = rank

    if not stable_xcode:
        raise ValueError("Apple Developer feed did not contain a stable Xcode release")
    missing_betas = sorted(set(DEVELOPER_PRODUCTS.values()) - set(betas))
    if missing_betas:
        raise ValueError(f"Apple Developer feed did not contain betas for: {', '.join(missing_betas)}")
    return stable_xcode, betas


def parse_homepod_release(html: str) -> dict[str, str]:
    parser = HomePodParser()
    parser.feed(html)
    heading = next(
        (value for value in parser.headings if re.fullmatch(r"HomePod Software Version \d+(?:\.\d+){0,2}", value)),
        None,
    )
    if not heading or not parser.dates:
        raise ValueError("HomePod support page did not contain a current version and date")
    version = re.search(r"\d+(?:\.\d+){0,2}", heading).group(0)
    published = datetime.strptime(parser.dates[0], "%B %d, %Y")
    return {
        "title": f"HomePod software {version}",
        "version": version,
        "date": published.strftime("%d %b %Y"),
        "source": HOMEPOD_RELEASES_URL,
    }


def read_source(location: str) -> str:
    if location.startswith(("https://", "http://")):
        request = Request(location, headers={"User-Agent": USER_AGENT})
        with urlopen(request, timeout=30) as response:
            return response.read().decode("utf-8")
    return Path(location).read_text(encoding="utf-8")


def write_release_data(output: Path, stable: dict, betas: dict) -> None:
    dates = [
        datetime.strptime(release["date"], "%d %b %Y")
        for release in [*stable.values(), *betas.values()]
    ]
    payload = {
        "updated": max(dates).strftime("%d %b %Y"),
        "stable": dict(sorted(stable.items())),
        "betas": dict(sorted(betas.items())),
    }
    content = (
        "// Generated by scripts/check_releases.py. Do not edit manually.\n"
        f"window.APPLE_RELEASES = {json.dumps(payload, indent=2, ensure_ascii=True)};\n"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stable-source", default=SECURITY_RELEASES_URL)
    parser.add_argument("--developer-source", default=DEVELOPER_RELEASES_URL)
    parser.add_argument("--homepod-source", default=HOMEPOD_RELEASES_URL)
    parser.add_argument("--output", type=Path, default=Path("data/releases.js"))
    args = parser.parse_args()

    stable = parse_stable_releases(read_source(args.stable_source))
    stable_xcode, betas = parse_developer_releases(read_source(args.developer_source))
    stable["xcode"] = stable_xcode
    stable["homepod"] = parse_homepod_release(read_source(args.homepod_source))
    write_release_data(args.output, stable, betas)


if __name__ == "__main__":
    main()
