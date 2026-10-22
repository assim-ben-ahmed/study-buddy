"""Capture the app into docs/images/ (used by the README). Uses real Mistral answers, so it needs a key in .env.

Start the app first (`python tasks.py serve`), then run `python scripts/screenshots.py`.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parents[1] / "docs" / "images"


def _launch(p):
    for channel in ("msedge", "chrome"):
        try:
            return p.chromium.launch(channel=channel)
        except Exception:  # noqa: BLE001 - channel not installed
            continue
    return p.chromium.launch()


def wait_answer(page, count: int) -> None:
    page.wait_for_function(
        "n => document.querySelectorAll('.msg.bot').length >= n && document.body.dataset.busy === '0'", arg=count,
        timeout=120_000)
    page.wait_for_timeout(1200)


def scroll_to(page, element_js: str) -> None:
    """Scroll the message list so that the given element sits at its top."""
    page.evaluate(f"""() => {{ const list = document.getElementById('messages'); const el = {element_js};
        list.scrollTop += el.getBoundingClientRect().top - list.getBoundingClientRect().top - 12; }}""")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = _launch(p)
        page = browser.new_page(viewport={"width": 1280, "height": 900}, locale="en-US")
        page.goto(args.url)
        page.wait_for_selector("#status.live")
        page.screenshot(path=str(OUT / "welcome.png"))

        page.click("text=✍️ Homework coach")
        page.fill("#input", "Help me solve 2x + 5 = 17")
        page.press("#input", "Enter")
        wait_answer(page, 2)
        page.fill("#input", "I subtract 5 from both sides, so 2x = 12")
        page.press("#input", "Enter")
        wait_answer(page, 3)
        # Frame the student's own step and the coach's reaction to it.
        scroll_to(page, "document.querySelectorAll('.msg.user')[1]")
        page.wait_for_timeout(300)
        page.screenshot(path=str(OUT / "homework_coach.png"))

        page.click("text=↺ New chat")
        page.click("text=💡 Explain")
        page.fill("#input", "Explain photosynthesis simply")
        page.press("#input", "Enter")
        wait_answer(page, 2)
        page.evaluate("document.getElementById('messages').scrollTop = 0")
        page.screenshot(path=str(OUT / "explain.png"))

        page.click("text=📝 Quiz")
        page.fill("#quiz-topic", "The water cycle")
        page.click("text=📝 Generate quiz")
        page.wait_for_selector(".q", timeout=120_000)
        for i in (0, 1, 2):  # answer three questions, one of them deliberately with option D
            page.locator(".q").nth(i).locator(".opt").nth(1 if i != 1 else 3).click()
        page.wait_for_timeout(600)
        page.evaluate("document.getElementById('quiz-area').scrollTop = 0")
        page.screenshot(path=str(OUT / "quiz.png"))

        page.click("text=🃏 Flashcards")
        page.fill("#cards-topic", "Newton's three laws of motion")
        page.click("text=🃏 Make flashcards")
        page.wait_for_selector(".card", timeout=120_000)
        page.locator(".card").nth(1).click()
        page.locator(".card").nth(4).click()
        page.wait_for_timeout(900)
        page.screenshot(path=str(OUT / "flashcards.png"))

        phone = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2, locale="fr-FR")
        phone.goto(args.url)
        phone.wait_for_selector("#status.live")
        phone.fill("#input", "Explique le théorème de Pythagore")
        phone.press("#input", "Enter")
        wait_answer(phone, 2)
        scroll_to(phone, "document.querySelector('.msg.user')")
        phone.wait_for_timeout(300)
        phone.screenshot(path=str(OUT / "mobile.png"))
        browser.close()
    print("saved to", OUT)


if __name__ == "__main__":
    main()
