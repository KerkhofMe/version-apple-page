import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "check_releases.py"
SPEC = importlib.util.spec_from_file_location("check_releases", SCRIPT)
check_releases = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_releases)


class ReleaseParserTests(unittest.TestCase):
    def test_stable_parser_chooses_newest_product_versions(self):
        rows = [
            ("macOS Current 26.6.1", "06 Aug 2026"),
            ("iOS 18.7.9 and iPadOS 18.7.9", "06 Aug 2026"),
            ("iOS 26.6 and iPadOS 26.6", "27 Jul 2026"),
            ("tvOS 26.6", "27 Jul 2026"),
            ("watchOS 26.6", "27 Jul 2026"),
            ("visionOS 26.6", "27 Jul 2026"),
            ("Safari 26.6", "27 Jul 2026"),
        ]
        html = "<table>" + "".join(
            f'<tr><td><a href="https://example.com/{index}">{title}</a></td>'
            f"<td>Devices</td><td>{date}</td></tr>"
            for index, (title, date) in enumerate(rows)
        ) + "</table>"

        releases = check_releases.parse_stable_releases(html)

        self.assertEqual("26.6", releases["ios"]["version"])
        self.assertEqual("26.6", releases["ipados"]["version"])
        self.assertEqual("26.6.1", releases["macos"]["version"])

    def test_developer_parser_extracts_stable_xcode_and_latest_betas(self):
        xml = """<rss><channel>
          <item><title>Xcode 26.6 (17F113)</title><link>https://example.com/xcode</link><pubDate>Thu, 25 Jun 2026 15:00:00 PDT</pubDate></item>
          <item><title>iOS 27.0 beta 4 (24A1)</title><link>https://example.com/ios</link><pubDate>Mon, 20 Jul 2026 10:00:00 PDT</pubDate></item>
          <item><title>iPadOS 27.0 beta 4 (24A1)</title><link>https://example.com/ipad</link><pubDate>Mon, 20 Jul 2026 10:00:00 PDT</pubDate></item>
          <item><title>macOS 27.0 beta 4 (26A1)</title><link>https://example.com/mac</link><pubDate>Mon, 20 Jul 2026 10:00:00 PDT</pubDate></item>
          <item><title>tvOS 27.0 beta 4 (24J1)</title><link>https://example.com/tv</link><pubDate>Mon, 20 Jul 2026 10:00:00 PDT</pubDate></item>
          <item><title>watchOS 27.0 beta 4 (24R1)</title><link>https://example.com/watch</link><pubDate>Mon, 20 Jul 2026 10:00:00 PDT</pubDate></item>
          <item><title>visionOS 27.0 beta 4 (24M1)</title><link>https://example.com/vision</link><pubDate>Mon, 20 Jul 2026 10:00:00 PDT</pubDate></item>
          <item><title>Xcode 27 beta 4 (27A1)</title><link>https://example.com/xcode-beta</link><pubDate>Mon, 20 Jul 2026 10:00:00 PDT</pubDate></item>
          <item><title>iOS 26.6 beta 5 (23G1)</title><link>https://example.com/old-ios</link><pubDate>Tue, 21 Jul 2026 10:00:00 PDT</pubDate></item>
        </channel></rss>"""

        stable_xcode, betas = check_releases.parse_developer_releases(xml)

        self.assertEqual("26.6", stable_xcode["version"])
        self.assertEqual("27.0", betas["ios"]["version"])
        self.assertEqual("Beta 4", betas["xcode"]["beta"])
        self.assertEqual(7, len(betas))

    def test_homepod_parser_reads_current_heading_and_article_date(self):
        html = """
          <time>July 30, 2026</time>
          <h2>HomePod Software Version 26.6</h2>
          <h2>HomePod Software Version 26.5</h2>
        """

        release = check_releases.parse_homepod_release(html)

        self.assertEqual("26.6", release["version"])
        self.assertEqual("30 Jul 2026", release["date"])


if __name__ == "__main__":
    unittest.main()
