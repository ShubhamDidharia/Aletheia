"""
Playwright scraper (Commit 9) — the fallback when Tavily returns nothing usable.

Tavily fails on some pages: paywalls, bot-blocking, or JS-rendered content that
its extractor can't see. When that happens the source arrives with an empty or
near-empty snippet, which is useless to the Auditor. This fetches the page with
a real browser and pulls the readable text.

Entirely optional. Playwright is a heavy dependency (it needs a downloaded
browser), so this is imported lazily and every failure is non-fatal — the
mission continues with whatever Tavily gave us.
"""
import asyncio
import logging
from typing import Optional

log = logging.getLogger("aletheia.scraper")

# Below this many characters a Tavily snippet isn't worth auditing.
THIN_CONTENT_CHARS = 200
NAV_TIMEOUT_MS = 15000
MAX_TEXT_CHARS = 4000

_unavailable_reason: Optional[str] = None
_browser_lock = asyncio.Lock()

# Strip the page furniture that would otherwise dominate the extracted text.
_STRIP_SELECTORS = "script, style, nav, header, footer, aside, noscript, iframe, svg"

_EXTRACT_JS = """
() => {
  const main = document.querySelector('article, main, [role="main"]') || document.body;
  return main ? main.innerText : '';
}
"""


def is_available() -> bool:
    """True if Playwright is installed and hasn't already failed to launch."""
    if _unavailable_reason is not None:
        return False
    try:
        import playwright  # noqa: F401
        return True
    except ImportError:
        return False


def unavailable_reason() -> Optional[str]:
    return _unavailable_reason


def needs_scraping(snippet: str) -> bool:
    return len((snippet or "").strip()) < THIN_CONTENT_CHARS


async def scrape(url: str) -> Optional[str]:
    """
    Fetch `url` in a headless browser and return its readable text.

    Returns None on any failure — a scrape is a bonus, never a requirement.
    """
    global _unavailable_reason

    if _unavailable_reason is not None:
        return None

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        _unavailable_reason = (
            "playwright is not installed. `pip install playwright` then "
            "`playwright install chromium` to enable the scraper fallback."
        )
        log.info("Scraper disabled: %s", _unavailable_reason)
        return None

    # Playwright launches a real browser; serialise to avoid spawning several.
    async with _browser_lock:
        browser = None
        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
                    ),
                    viewport={"width": 1280, "height": 900},
                )
                page = await context.new_page()
                await page.goto(url, timeout=NAV_TIMEOUT_MS, wait_until="domcontentloaded")
                await page.eval_on_selector_all(
                    _STRIP_SELECTORS, "els => els.forEach(e => e.remove())"
                )
                text = await page.evaluate(_EXTRACT_JS)
                await context.close()
        except Exception as e:
            message = str(e)
            if "Executable doesn't exist" in message or "playwright install" in message:
                _unavailable_reason = (
                    "Playwright's browser is not downloaded. Run "
                    "`playwright install chromium` to enable the scraper fallback."
                )
                log.info("Scraper disabled: %s", _unavailable_reason)
            else:
                log.info("Scrape failed for %s: %s", url, message[:160])
            return None
        finally:
            if browser is not None:
                try:
                    await browser.close()
                except Exception:
                    pass

    cleaned = " ".join((text or "").split())
    if len(cleaned) < THIN_CONTENT_CHARS:
        return None

    log.info("Scraped %d chars from %s", len(cleaned), url)
    return cleaned[:MAX_TEXT_CHARS]
