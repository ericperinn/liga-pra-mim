"""Records a scripted walkthrough of the live site as a video (Playwright).

Usage: demo/.venv/Scripts/python demo/record_site.py [--lang en|pt] [--send "message"]
Output: demo/out/site-<lang>.webm
"""

import argparse
import shutil
import time
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

SITE = "https://main.d3197h98vf4n1z.amplifyapp.com"
OUT = Path(__file__).parent / "out"
SIZE = {"width": 1280, "height": 720}


def glide_to(page: Page, selector: str, pause: float = 1.5) -> None:
    """Scrolls smoothly so the viewer can follow, instead of jumping."""
    page.evaluate(
        "s => document.querySelector(s).scrollIntoView({behavior: 'smooth', block: 'start'})", selector
    )
    time.sleep(pause)


def type_slowly(page: Page, selector: str, text: str) -> None:
    page.click(selector)
    page.keyboard.type(text, delay=45)


def walkthrough(page: Page, lang: str, send: str | None) -> None:
    page.goto(SITE, wait_until="load")
    page.wait_for_selector("h1")
    want_en = lang == "en"
    is_en = page.locator("button.lang").inner_text().strip() == "Português"
    if want_en != is_en:
        page.click("button.lang")
    time.sleep(2.5)

    page.click(".facts summary")
    time.sleep(1.0)
    page.mouse.wheel(0, 420)
    time.sleep(4.0)
    page.mouse.wheel(0, 420)
    time.sleep(3.5)

    glide_to(page, ".chat", 2.0)
    if send:
        type_slowly(page, "#chat-input", send)
        page.click("button.send")
        page.wait_for_selector(".msg-assistant:not(.msg-thinking) >> nth=1", timeout=60_000)
        time.sleep(6.0)
    else:
        page.hover(".suggestions button >> nth=0")
        time.sleep(3.0)

    glide_to(page, ".impact", 4.0)
    glide_to(page, ".how", 5.0)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lang", choices=["en", "pt"], default="en")
    parser.add_argument("--send", help="message to send in the chat (needs the AI online)")
    args = parser.parse_args()

    OUT.mkdir(exist_ok=True)
    raw_dir = OUT / "raw"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(
            viewport=SIZE,
            record_video_dir=str(raw_dir),
            record_video_size=SIZE,
            locale="en-US" if args.lang == "en" else "pt-BR",
        )
        page = context.new_page()
        walkthrough(page, args.lang, args.send)
        video = page.video.path()
        context.close()
        browser.close()

    target = OUT / f"site-{args.lang}.webm"
    shutil.move(video, target)
    shutil.rmtree(raw_dir, ignore_errors=True)
    print(target)


if __name__ == "__main__":
    main()
