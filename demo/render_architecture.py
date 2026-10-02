"""Renders the Mermaid architecture diagram from README.md to docs/architecture.png."""

import re
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
diagram = re.search(r"```mermaid\n(.*?)```", (ROOT / "README.md").read_text(encoding="utf-8"), re.S).group(1)

html = f"""<!doctype html><html><head><meta charset="utf-8">
<script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>
<style>body{{margin:0;padding:32px;background:#eef0ec;font-family:sans-serif}}</style></head>
<body><pre class="mermaid">{diagram}</pre>
<script>mermaid.initialize({{startOnLoad:true, theme:'base', themeVariables:{{
  primaryColor:'#ffffff', primaryBorderColor:'#1f4e9a', primaryTextColor:'#1b2233',
  lineColor:'#e8741e', fontSize:'18px'}}}});</script></body></html>"""

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1800, "height": 900}, device_scale_factor=2)
    page.set_content(html)
    page.wait_for_selector("pre.mermaid svg", timeout=30_000)
    page.locator("pre.mermaid").screenshot(path=str(ROOT / "docs" / "architecture.png"))
    browser.close()
print(ROOT / "docs" / "architecture.png")
