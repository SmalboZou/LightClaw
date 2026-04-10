import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from lightclaw.domain.errors import BrowserAutomationError, BrowserSessionNotFoundError


@dataclass
class BrowserSnapshot:
    url: str
    title: str
    visible_text: str
    elements: list[dict[str, str]] = field(default_factory=list)
    forms: list[dict[str, Any]] = field(default_factory=list)

    def to_payload(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "visible_text": self.visible_text,
            "elements": self.elements,
            "forms": self.forms,
        }


class BrowserService:
    async def open_session(
        self,
        *,
        session_name: str,
        headless: bool,
        start_url: str | None,
        persistent_profile: bool,
        profile_root: Path | None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    async def navigate(self, session_id: str, url: str) -> dict[str, Any]:
        raise NotImplementedError

    async def snapshot(self, session_id: str) -> BrowserSnapshot:
        raise NotImplementedError

    async def click(self, session_id: str, selector: str) -> dict[str, Any]:
        raise NotImplementedError

    async def type(
        self,
        session_id: str,
        selector: str,
        text: str,
        *,
        secret: bool = False,
    ) -> dict[str, Any]:
        raise NotImplementedError

    async def wait(
        self,
        session_id: str,
        *,
        selector: str | None = None,
        url_contains: str | None = None,
        timeout_seconds: float = 10.0,
    ) -> dict[str, Any]:
        raise NotImplementedError

    async def extract(
        self,
        session_id: str,
        *,
        selector: str | None = None,
        mode: str = "text",
    ) -> dict[str, Any]:
        raise NotImplementedError

    async def close(self, session_id: str) -> dict[str, Any]:
        raise NotImplementedError

    async def aclose(self) -> None:
        return None


@dataclass
class _MockSession:
    session_id: str
    session_name: str
    headless: bool
    persistent_profile: bool
    url: str = "about:blank"
    title: str = "Blank"
    visible_text: str = ""
    compose_to: str = ""
    compose_subject: str = ""
    compose_body: str = ""


class MockBrowserService(BrowserService):
    def __init__(self) -> None:
        self._sessions: dict[str, _MockSession] = {}

    async def open_session(
        self,
        *,
        session_name: str,
        headless: bool,
        start_url: str | None,
        persistent_profile: bool,
        profile_root: Path | None,
    ) -> dict[str, Any]:
        session_id = str(uuid.uuid4())
        session = _MockSession(
            session_id=session_id,
            session_name=session_name,
            headless=headless,
            persistent_profile=persistent_profile,
        )
        self._sessions[session_id] = session
        if start_url:
            await self.navigate(session_id, start_url)
        return self._session_payload(session)

    async def navigate(self, session_id: str, url: str) -> dict[str, Any]:
        session = self._require_session(session_id)
        session.url = url
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        if "wttr.in" in host:
            location = parsed.path.strip("/") or "unknown"
            location = location.replace("+", " ")
            session.title = f"Weather for {location}"
            session.visible_text = f"Weather for {location}: 20C Sunny H:25C L:15C"
        elif "mail.google.com" in host:
            session.title = "Gmail Compose"
            session.visible_text = "Compose a message"
        else:
            session.title = parsed.netloc or "Page"
            session.visible_text = f"Loaded {url}"
        return self._session_payload(session)

    async def snapshot(self, session_id: str) -> BrowserSnapshot:
        session = self._require_session(session_id)
        elements = []
        forms: list[dict[str, Any]] = []
        if "mail.google.com" in session.url:
            elements = [
                {"selector": "input[aria-label='Recipients']", "role": "textbox", "label": "Recipients"},
                {"selector": "input[name='subjectbox']", "role": "textbox", "label": "Subject"},
                {"selector": "div[aria-label='Message Body']", "role": "textbox", "label": "Message Body"},
                {"selector": "div[role='button'][data-tooltip*='Send']", "role": "button", "label": "Send"},
            ]
            forms = [
                {
                    "name": "compose",
                    "fields": [
                        {"selector": item["selector"], "label": item["label"]}
                        for item in elements[:-1]
                    ],
                }
            ]
        return BrowserSnapshot(
            url=session.url,
            title=session.title,
            visible_text=session.visible_text,
            elements=elements,
            forms=forms,
        )

    async def click(self, session_id: str, selector: str) -> dict[str, Any]:
        session = self._require_session(session_id)
        if "mail.google.com" in session.url and "Send" in selector:
            session.title = "Message sent"
            session.visible_text = (
                f"Sent email to {session.compose_to} with subject {session.compose_subject}"
            )
        return {"clicked": True, "url": session.url, "title": session.title}

    async def type(
        self,
        session_id: str,
        selector: str,
        text: str,
        *,
        secret: bool = False,
    ) -> dict[str, Any]:
        session = self._require_session(session_id)
        if "Recipients" in selector:
            session.compose_to = text
        elif "subjectbox" in selector:
            session.compose_subject = text
        elif "Message Body" in selector:
            session.compose_body = text
        return {"typed": True, "selector": selector, "secret": secret}

    async def wait(
        self,
        session_id: str,
        *,
        selector: str | None = None,
        url_contains: str | None = None,
        timeout_seconds: float = 10.0,
    ) -> dict[str, Any]:
        session = self._require_session(session_id)
        if url_contains and url_contains not in session.url:
            raise BrowserAutomationError(
                f"Current URL '{session.url}' does not contain '{url_contains}'."
            )
        return {
            "matched": True,
            "selector": selector,
            "url_contains": url_contains,
            "timeout_seconds": timeout_seconds,
        }

    async def extract(
        self,
        session_id: str,
        *,
        selector: str | None = None,
        mode: str = "text",
    ) -> dict[str, Any]:
        snapshot = await self.snapshot(session_id)
        if mode == "snapshot":
            return {"mode": mode, "content": snapshot.to_payload()}
        return {"mode": mode, "selector": selector, "content": snapshot.visible_text}

    async def close(self, session_id: str) -> dict[str, Any]:
        self._require_session(session_id)
        self._sessions.pop(session_id, None)
        return {"closed": True, "session_id": session_id}

    def _require_session(self, session_id: str) -> _MockSession:
        session = self._sessions.get(session_id)
        if session is None:
            raise BrowserSessionNotFoundError(f"Browser session '{session_id}' was not found.")
        return session

    def _session_payload(self, session: _MockSession) -> dict[str, Any]:
        return {
            "session_id": session.session_id,
            "session_name": session.session_name,
            "headless": session.headless,
            "persistent_profile": session.persistent_profile,
            "url": session.url,
            "title": session.title,
        }


@dataclass
class _PlaywrightSession:
    session_id: str
    session_name: str
    browser: Any | None
    context: Any
    page: Any
    headless: bool
    persistent_profile: bool


class PlaywrightBrowserService(BrowserService):
    def __init__(self) -> None:
        self._playwright = None
        self._sessions: dict[str, _PlaywrightSession] = {}

    async def open_session(
        self,
        *,
        session_name: str,
        headless: bool,
        start_url: str | None,
        persistent_profile: bool,
        profile_root: Path | None,
    ) -> dict[str, Any]:
        playwright = await self._ensure_playwright()
        browser = None
        if persistent_profile:
            if profile_root is None:
                raise BrowserAutomationError("Persistent browser profiles require a profile root.")
            profile_dir = profile_root / session_name
            profile_dir.mkdir(parents=True, exist_ok=True)
            context = await playwright.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=headless,
            )
            page = context.pages[0] if context.pages else await context.new_page()
        else:
            browser = await playwright.chromium.launch(headless=headless)
            context = await browser.new_context()
            page = await context.new_page()
        session_id = str(uuid.uuid4())
        self._sessions[session_id] = _PlaywrightSession(
            session_id=session_id,
            session_name=session_name,
            browser=browser,
            context=context,
            page=page,
            headless=headless,
            persistent_profile=persistent_profile,
        )
        if start_url:
            await self.navigate(session_id, start_url)
        return await self._session_payload(self._sessions[session_id])

    async def navigate(self, session_id: str, url: str) -> dict[str, Any]:
        session = self._require_session(session_id)
        await session.page.goto(url, wait_until="domcontentloaded")
        return await self._session_payload(session)

    async def snapshot(self, session_id: str) -> BrowserSnapshot:
        session = self._require_session(session_id)
        title = await session.page.title()
        visible_text = (await session.page.locator("body").inner_text())[:4000]
        elements = await self._collect_elements(session.page)
        forms = await self._collect_forms(session.page)
        return BrowserSnapshot(
            url=session.page.url,
            title=title,
            visible_text=visible_text,
            elements=elements,
            forms=forms,
        )

    async def click(self, session_id: str, selector: str) -> dict[str, Any]:
        session = self._require_session(session_id)
        await session.page.locator(selector).first.click()
        return await self._session_payload(session)

    async def type(
        self,
        session_id: str,
        selector: str,
        text: str,
        *,
        secret: bool = False,
    ) -> dict[str, Any]:
        session = self._require_session(session_id)
        await session.page.locator(selector).first.fill(text)
        return {"typed": True, "selector": selector, "secret": secret}

    async def wait(
        self,
        session_id: str,
        *,
        selector: str | None = None,
        url_contains: str | None = None,
        timeout_seconds: float = 10.0,
    ) -> dict[str, Any]:
        session = self._require_session(session_id)
        timeout_ms = int(timeout_seconds * 1000)
        if selector:
            await session.page.locator(selector).first.wait_for(timeout=timeout_ms)
        if url_contains:
            await session.page.wait_for_url(f"**{url_contains}**", timeout=timeout_ms)
        return {"matched": True, "selector": selector, "url_contains": url_contains}

    async def extract(
        self,
        session_id: str,
        *,
        selector: str | None = None,
        mode: str = "text",
    ) -> dict[str, Any]:
        session = self._require_session(session_id)
        if mode == "snapshot":
            return {"mode": mode, "content": (await self.snapshot(session_id)).to_payload()}
        target = session.page.locator(selector).first if selector else session.page.locator("body")
        content = await target.inner_text()
        return {"mode": mode, "selector": selector, "content": (content or "")[:4000]}

    async def close(self, session_id: str) -> dict[str, Any]:
        session = self._require_session(session_id)
        await session.context.close()
        if session.browser is not None:
            await session.browser.close()
        self._sessions.pop(session_id, None)
        return {"closed": True, "session_id": session_id}

    async def aclose(self) -> None:
        session_ids = list(self._sessions.keys())
        for session_id in session_ids:
            try:
                await self.close(session_id)
            except BrowserSessionNotFoundError:
                continue
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None

    async def _ensure_playwright(self) -> Any:
        if self._playwright is not None:
            return self._playwright
        try:
            from playwright.async_api import async_playwright
        except ModuleNotFoundError as exc:
            raise BrowserAutomationError(
                "Playwright browser automation requires the 'playwright' package. "
                "Install with: uv sync --extra browser --extra dev"
            ) from exc
        self._playwright = await async_playwright().start()
        return self._playwright

    async def _collect_elements(self, page: Any) -> list[dict[str, str]]:
        payload = await page.locator(
            "a, button, input, textarea, select, [role='button']"
        ).evaluate_all(
            """
            (elements) => elements.slice(0, 25).map((element) => ({
              tag: element.tagName.toLowerCase(),
              role: element.getAttribute('role') || '',
              label:
                element.getAttribute('aria-label') ||
                element.innerText ||
                element.textContent ||
                element.getAttribute('placeholder') ||
                '',
              selector:
                element.id ? `#${element.id}` :
                element.getAttribute('name') ? `${element.tagName.toLowerCase()}[name="${element.getAttribute('name')}"]` :
                element.getAttribute('aria-label') ? `${element.tagName.toLowerCase()}[aria-label="${element.getAttribute('aria-label')}"]` :
                element.tagName.toLowerCase()
            }))
            """
        )
        return [
            {
                "selector": str(item.get("selector") or ""),
                "role": str(item.get("role") or item.get("tag") or ""),
                "label": " ".join(str(item.get("label") or "").split())[:120],
            }
            for item in payload
            if str(item.get("selector") or "").strip()
        ]

    async def _collect_forms(self, page: Any) -> list[dict[str, Any]]:
        payload = await page.locator("form").evaluate_all(
            """
            (forms) => forms.slice(0, 10).map((form, index) => ({
              name: form.getAttribute('name') || form.getAttribute('id') || `form-${index + 1}`,
              fields: Array.from(form.querySelectorAll('input, textarea, select')).slice(0, 10).map((field) => ({
                selector:
                  field.id ? `#${field.id}` :
                  field.getAttribute('name') ? `${field.tagName.toLowerCase()}[name="${field.getAttribute('name')}"]` :
                  field.getAttribute('aria-label') ? `${field.tagName.toLowerCase()}[aria-label="${field.getAttribute('aria-label')}"]` :
                  field.tagName.toLowerCase(),
                label:
                  field.getAttribute('aria-label') ||
                  field.getAttribute('placeholder') ||
                  field.getAttribute('name') ||
                  field.tagName.toLowerCase()
              }))
            }))
            """
        )
        return [
            {
                "name": str(item.get("name") or ""),
                "fields": [
                    {
                        "selector": str(field.get("selector") or ""),
                        "label": str(field.get("label") or ""),
                    }
                    for field in item.get("fields", [])
                    if str(field.get("selector") or "").strip()
                ],
            }
            for item in payload
        ]

    def _require_session(self, session_id: str) -> _PlaywrightSession:
        session = self._sessions.get(session_id)
        if session is None:
            raise BrowserSessionNotFoundError(f"Browser session '{session_id}' was not found.")
        return session

    async def _session_payload(self, session: _PlaywrightSession) -> dict[str, Any]:
        return {
            "session_id": session.session_id,
            "session_name": session.session_name,
            "headless": session.headless,
            "persistent_profile": session.persistent_profile,
            "url": session.page.url,
            "title": await session.page.title(),
        }


def build_browser_service(backend: str) -> BrowserService:
    if backend == "playwright":
        return PlaywrightBrowserService()
    return MockBrowserService()
