"""Records a scripted walkthrough of the live site as a video (Playwright).

Usage:
  demo/.venv/Scripts/python demo/record_site.py --lang en --ask "My grandmother is 80..."
  add --replay to answer from a real reply captured earlier (when the AI is offline);
  the replay is labelled on screen so it is never mistaken for a live answer.
Output: demo/out/site-<lang>.webm
"""

import argparse
import json
import shutil
import time
from pathlib import Path

from playwright.sync_api import Page, Route, sync_playwright

SITE = "https://main.d3197h98vf4n1z.amplifyapp.com"
OUT = Path(__file__).parent / "out"
SIZE = {"width": 1280, "height": 720}

# Real answer the assistant gave to this question in backend/evals/EVALUATION.md (2026-09-30 run).
REPLAY = {
    "en": (
        "Hi, my grandmother is 80 years old, lives alone in Brazil and earns about 200 reais a month. "
        "Is there any benefit she could get?",
        "Your grandmother can get several benefits. The most important one is the BPC, which gives her 1.621 reais "
        "every month because she is 80 years old. She can also get around 600 reais from Bolsa Família, free "
        "electricity up to 80 kilowatts per month, a senior citizen card for free bus travel, and free medicines at "
        "Popular Pharmacy. To start, she needs to go to the CRAS — that is the social assistance center in her city — "
        "and register at Cadastro Único, bringing her CPF or voter ID. After that, she can ask for the BPC by calling "
        "the INSS at 135. Does she know where the CRAS is in her city?",
    ),
    "pt": (
        "Oi, tenho 67 anos, moro sozinha e ganho uns 350 reais por mês fazendo faxina. Tenho direito a alguma coisa?",
        "Oi, que bom que você ligou! Pelo que você me contou, você pode ter direito a um benefício bem importante: "
        "o BPC, que é um salário mínimo por mês, 1.621 reais. Você também pode aproveitar a tarifa social da conta de "
        "luz e a Carteira da Pessoa Idosa. Mas para tudo isso, o primeiro passo é fazer o Cadastro Único no CRAS.",
    ),
}

# Headless recordings have no mouse pointer; draw one so viewers can follow the clicks.
CURSOR_JS = """
(() => {
  const dot = document.createElement('div');
  dot.style.cssText = 'position:fixed;left:0;top:0;width:22px;height:22px;margin:-11px 0 0 -11px;border-radius:50%;'
    + 'background:rgba(27,34,51,.85);border:3px solid #fff;box-shadow:0 2px 8px rgba(0,0,0,.35);'
    + 'z-index:99999;pointer-events:none;transition:transform .12s ease;';
  document.addEventListener('DOMContentLoaded', () => document.body.appendChild(dot));
  addEventListener('mousemove', e => { dot.style.left = e.clientX + 'px'; dot.style.top = e.clientY + 'px'; });
  addEventListener('mousedown', () => dot.style.transform = 'scale(.7)');
  addEventListener('mouseup', () => dot.style.transform = 'scale(1)');
})();
"""

SMOOTH_SCROLL_JS = """
([target, duration]) => new Promise(done => {
  const start = scrollY, delta = target - start, t0 = performance.now();
  const ease = t => t < .5 ? 4*t*t*t : 1 - Math.pow(-2*t + 2, 3) / 2;
  const step = now => {
    const t = Math.min(1, (now - t0) / duration);
    scrollTo(0, start + delta * ease(t));
    t < 1 ? requestAnimationFrame(step) : done();
  };
  requestAnimationFrame(step);
})
"""


class Director:
    def __init__(self, page: Page):
        self.page = page
        self.x, self.y = 640, 360
        self.t0 = time.monotonic()
        self.chapters: dict[str, float] = {}

    def mark(self, name: str) -> None:
        """Records when a part of the walkthrough starts, so the video builder can cut by topic."""
        self.chapters[name] = round(time.monotonic() - self.t0, 2)

    def scroll_to(self, selector: str, offset: int = -24, duration: int = 1800, hold: float = 1.5) -> None:
        y = self.page.evaluate(
            "([s, o]) => document.querySelector(s).getBoundingClientRect().top + scrollY + o", [selector, offset]
        )
        self.page.evaluate(SMOOTH_SCROLL_JS, [max(0, y), duration])
        time.sleep(hold)

    def scroll_by(self, dy: int, duration: int = 2200, hold: float = 1.0) -> None:
        y = self.page.evaluate("() => scrollY") + dy
        self.page.evaluate(SMOOTH_SCROLL_JS, [y, duration])
        time.sleep(hold)

    def move_to(self, selector: str, steps: int = 30) -> None:
        box = self.page.locator(selector).first.bounding_box()
        tx, ty = box["x"] + min(box["width"] / 2, 60), box["y"] + box["height"] / 2
        self.page.mouse.move(tx, ty, steps=steps)
        self.x, self.y = tx, ty
        time.sleep(0.3)

    def click(self, selector: str) -> None:
        self.move_to(selector)
        self.page.mouse.down()
        time.sleep(0.12)
        self.page.mouse.up()
        time.sleep(0.4)


def install_replay(page: Page, answer: str) -> None:
    def handle(route: Route) -> None:
        time.sleep(3.0)  # roughly the live answer time, so the "thinking" bubble is visible
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"fala": answer, "beneficios": ["bpc"], "encerrar": False}),
        )

    page.route("**/chat", handle)
    page.add_init_script(
        "document.addEventListener('DOMContentLoaded', () => {"
        "const b = document.createElement('div');"
        "b.textContent = 'Replay of a real answer recorded on 2026-09-30';"
        "b.style.cssText = 'position:fixed;right:12px;bottom:12px;padding:4px 10px;border-radius:6px;"
        "background:#1b2233;color:#fff;font:13px sans-serif;z-index:99998;opacity:.8';"
        "document.body.appendChild(b); });"
    )


def walkthrough(d: Director, lang: str, question: str | None, conversation: list[str] | None = None) -> None:
    page = d.page
    d.mark("start")
    page.goto(SITE, wait_until="load")
    page.wait_for_selector("h1")
    page.mouse.move(d.x, d.y)
    want_en = lang == "en"
    if want_en != (page.locator("button.lang").inner_text().strip() == "Português"):
        page.click("button.lang")
    time.sleep(2.5)

    d.mark("hero")
    d.move_to(".aparelho", steps=40)
    time.sleep(1.5)
    d.click(".facts summary")
    d.scroll_by(380, duration=2600, hold=2.5)
    d.scroll_by(380, duration=2600, hold=3.0)

    d.mark("chat")
    d.scroll_to(".chat", duration=2200, hold=1.0)
    if conversation:
        d.scroll_to(".chat-panel", offset=-40, duration=1200, hold=0.3)
        for n, message in enumerate(conversation):
            d.click("#chat-input")
            page.keyboard.type(message, delay=30)
            time.sleep(0.3)
            d.click("button.send")
            page.wait_for_function("n => document.querySelectorAll('.msg-assistant:not(.msg-thinking)').length > n", arg=n + 1, timeout=60_000)
            # longer pauses where the answer carries the result
            time.sleep(4.5 if len(page.locator(".msg-assistant").last.inner_text()) > 160 else 1.2)
        time.sleep(1.5)
    elif question:
        d.click("#chat-input")
        page.keyboard.type(question, delay=38)
        time.sleep(0.6)
        d.click("button.send")
        page.wait_for_selector(".msg-thinking", timeout=10_000)
        page.wait_for_selector(".msg-thinking", state="detached", timeout=60_000)
        time.sleep(0.8)
        d.scroll_to(".chat-panel", offset=-80, duration=1200, hold=0.5)
        page.evaluate("() => { const l = document.querySelector('.chat-log'); l.scrollTo({top: l.scrollHeight, behavior: 'smooth'}); }")
        time.sleep(9.0)  # time to read the answer
    else:
        d.move_to(".suggestions button")
        time.sleep(2.5)

    d.mark("impact")
    d.scroll_to(".impact", duration=2400, hold=4.5)
    d.scroll_to(".how", duration=2400, hold=5.5)
    d.mark("end")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lang", choices=["en", "pt"], default="en")
    parser.add_argument("--ask", help="question to type in the chat (live AI)")
    parser.add_argument("--replay", action="store_true", help="answer with a real reply captured earlier")
    parser.add_argument("--conversation", nargs="+", help="several messages sent in turn (live)")
    args = parser.parse_args()

    question = args.ask
    if args.replay:
        question, answer = REPLAY[args.lang]

    OUT.mkdir(exist_ok=True)
    raw_dir = OUT / "raw"
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(
            viewport=SIZE,
            record_video_dir=str(raw_dir),
            record_video_size=SIZE,
            locale="en-US" if args.lang == "en" else "pt-BR",
            device_scale_factor=1,
        )
        page = context.new_page()
        page.add_init_script(CURSOR_JS)
        page.add_init_script("try { sessionStorage.clear() } catch (e) {}")
        if args.replay:
            install_replay(page, answer)
        director = Director(page)
        walkthrough(director, args.lang, question, args.conversation)
        video = page.video.path()
        context.close()
        browser.close()

    target = OUT / f"site-{args.lang}.webm"
    shutil.move(video, target)
    (OUT / f"site-{args.lang}.chapters.json").write_text(json.dumps(director.chapters, indent=2), encoding="utf-8")
    shutil.rmtree(raw_dir, ignore_errors=True)
    print(target)


if __name__ == "__main__":
    main()
