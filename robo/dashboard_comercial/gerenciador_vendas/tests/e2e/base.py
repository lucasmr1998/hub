"""
Helpers compartilhados para testes E2E com Playwright.

Uso:
    from tests.e2e.base import E2ESession

    with E2ESession("inbox_claiming") as s:
        s.login()
        s.goto("/inbox/")
        s.shot("01_inbox_aberto")
        ...
"""

import os
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright, Page

BASE_URL = os.environ.get("E2E_BASE_URL", "http://localhost:8001")
EMAIL    = os.environ.get("E2E_EMAIL", "admin@auroraisp.com.br")
PASSWORD = os.environ.get("E2E_PASS", "e2e_aurora_2026")

SCREENSHOTS_DIR = Path(__file__).parent / "screenshots"


class E2ESession:
    def __init__(self, feature: str, headless: bool = True, slow_mo: int = 200):
        self.feature = feature
        self.headless = headless
        self.slow_mo = slow_mo
        self.ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.out_dir = SCREENSHOTS_DIR / feature / self.ts
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self._pw = None
        self._browser = None
        self.page: Page = None

    def __enter__(self):
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=self.headless, slow_mo=self.slow_mo)
        ctx = self._browser.new_context(viewport={"width": 1400, "height": 900})
        self.page = ctx.new_page()
        return self

    def __exit__(self, *_):
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()

    def login(self):
        self.page.goto(f"{BASE_URL}/login/")
        self.page.fill("input[name='email']", EMAIL)
        self.page.fill("input[name='password']", PASSWORD)
        self.page.click("button[type='submit']")
        self.page.wait_for_load_state("networkidle")
        print(f"  Login OK — {self.page.url}")

    def goto(self, path: str):
        self.page.goto(f"{BASE_URL}{path}")
        self.page.wait_for_load_state("networkidle")

    def shot(self, name: str):
        path = self.out_dir / f"{name}.png"
        self.page.screenshot(path=str(path), full_page=False)
        print(f"  [{name}] -> {path}")
        return path

    def shot_mobile(self, name: str):
        """Screenshot com viewport mobile."""
        self.page.set_viewport_size({"width": 390, "height": 844})
        path = self.out_dir / f"{name}_mobile.png"
        self.page.screenshot(path=str(path))
        self.page.set_viewport_size({"width": 1400, "height": 900})
        print(f"  [{name}_mobile] -> {path}")
        return path
