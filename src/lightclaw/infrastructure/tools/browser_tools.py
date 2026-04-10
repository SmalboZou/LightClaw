import json
from typing import Any
from urllib.parse import quote, urlparse

from lightclaw.domain.agent.models import ToolResult
from lightclaw.domain.errors import ProviderRequestError, PolicyViolationError
from lightclaw.domain.tools.base import Tool
from lightclaw.domain.tools.models import ToolExecutionContext


class BrowserTool(Tool):
    def __init__(self, browser_service: Any) -> None:
        self._browser_service = browser_service

    def _require_browser_service(self, context: ToolExecutionContext) -> Any:
        if not context.browser_enabled or self._browser_service is None:
            raise PolicyViolationError("Browser automation is disabled by policy.")
        return self._browser_service


def _check_allowed(url: str, context: ToolExecutionContext) -> None:
    if not context.browser_allowed_domains:
        return
    host = urlparse(url).netloc.lower()
    if any(host == domain or host.endswith(f".{domain}") for domain in context.browser_allowed_domains):
        return
    raise PolicyViolationError(f"Browser navigation to '{host}' is not allowed by policy.")


async def _record_event(context: ToolExecutionContext, event_type: str, message: str) -> None:
    if context.event_logger is None:
        return
    await context.event_logger.record(
        event_type=event_type,
        message=message,
        session_id=context.session_id,
    )


def _payload_output(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=True)


class BrowserOpenTool(BrowserTool):
    name = "browser.open"
    description = "Open a managed browser session."
    required_scope = "browser_read"
    timeout_seconds = 20.0
    argument_schema = {
        "type": "object",
        "properties": {
            "session_name": {"type": "string"},
            "headless": {"type": "boolean"},
            "start_url": {"type": "string"},
            "persistent_profile": {"type": "boolean"},
        },
        "required": ["session_name"],
        "additionalProperties": False,
    }

    async def run(self, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolResult:
        browser_service = self._require_browser_service(context)
        start_url = arguments.get("start_url")
        if isinstance(start_url, str) and start_url:
            _check_allowed(start_url, context)
        payload = await browser_service.open_session(
            session_name=str(arguments["session_name"]),
            headless=bool(arguments.get("headless", context.browser_headless)),
            start_url=str(start_url) if start_url else None,
            persistent_profile=bool(arguments.get("persistent_profile", False)),
            profile_root=context.browser_profile_root,
        )
        await _record_event(
            context,
            "browser_session_started",
            f"browser_session_id={payload['session_id']} session_name={payload['session_name']}",
        )
        return ToolResult(name=self.name, output=_payload_output(payload))


class BrowserNavigateTool(BrowserTool):
    name = "browser.navigate"
    description = "Navigate a managed browser session to a URL."
    required_scope = "browser_read"
    timeout_seconds = 20.0
    argument_schema = {
        "type": "object",
        "properties": {"session_id": {"type": "string"}, "url": {"type": "string"}},
        "required": ["session_id", "url"],
        "additionalProperties": False,
    }

    async def run(self, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolResult:
        browser_service = self._require_browser_service(context)
        url = str(arguments["url"])
        _check_allowed(url, context)
        await _record_event(context, "browser_navigation_started", f"url={url}")
        payload = await browser_service.navigate(str(arguments["session_id"]), url)
        await _record_event(
            context,
            "browser_navigation_completed",
            f"browser_session_id={payload['session_id']} url={payload['url']}",
        )
        return ToolResult(name=self.name, output=_payload_output(payload))


class BrowserSnapshotTool(BrowserTool):
    name = "browser.snapshot"
    description = "Capture a normalized snapshot of the current browser page."
    required_scope = "browser_read"
    timeout_seconds = 15.0
    argument_schema = {
        "type": "object",
        "properties": {"session_id": {"type": "string"}},
        "required": ["session_id"],
        "additionalProperties": False,
    }

    async def run(self, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolResult:
        browser_service = self._require_browser_service(context)
        snapshot = await browser_service.snapshot(str(arguments["session_id"]))
        await _record_event(
            context,
            "browser_snapshot_captured",
            f"browser_session_id={arguments['session_id']} url={snapshot.url}",
        )
        return ToolResult(name=self.name, output=_payload_output(snapshot.to_payload()))


class BrowserClickTool(BrowserTool):
    name = "browser.click"
    description = "Click a page element in a managed browser session."
    required_scope = "browser_write"
    timeout_seconds = 15.0
    argument_schema = {
        "type": "object",
        "properties": {
            "session_id": {"type": "string"},
            "selector": {"type": "string"},
        },
        "required": ["session_id", "selector"],
        "additionalProperties": False,
    }

    async def run(self, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolResult:
        browser_service = self._require_browser_service(context)
        payload = await browser_service.click(
            str(arguments["session_id"]),
            str(arguments["selector"]),
        )
        await _record_event(
            context,
            "browser_element_clicked",
            f"browser_session_id={arguments['session_id']} selector={arguments['selector']}",
        )
        return ToolResult(name=self.name, output=_payload_output(payload))


class BrowserTypeTool(BrowserTool):
    name = "browser.type"
    description = "Type text into a page field in a managed browser session."
    required_scope = "browser_write"
    timeout_seconds = 15.0
    argument_schema = {
        "type": "object",
        "properties": {
            "session_id": {"type": "string"},
            "selector": {"type": "string"},
            "text": {"type": "string"},
            "secret": {"type": "boolean"},
        },
        "required": ["session_id", "selector", "text"],
        "additionalProperties": False,
    }

    async def run(self, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolResult:
        browser_service = self._require_browser_service(context)
        secret = bool(arguments.get("secret", False))
        payload = await browser_service.type(
            str(arguments["session_id"]),
            str(arguments["selector"]),
            str(arguments["text"]),
            secret=secret,
        )
        await _record_event(
            context,
            "browser_input_typed",
            f"browser_session_id={arguments['session_id']} selector={arguments['selector']} secret={secret}",
        )
        safe_payload = {**payload, "text": "[REDACTED]" if secret else "[PROVIDED]"}
        return ToolResult(name=self.name, output=_payload_output(safe_payload))


class BrowserWaitTool(BrowserTool):
    name = "browser.wait"
    description = "Wait for a selector or URL condition in a managed browser session."
    required_scope = "browser_read"
    timeout_seconds = 15.0
    argument_schema = {
        "type": "object",
        "properties": {
            "session_id": {"type": "string"},
            "selector": {"type": "string"},
            "url_contains": {"type": "string"},
            "timeout_seconds": {"type": "number"},
        },
        "required": ["session_id"],
        "additionalProperties": False,
    }

    async def run(self, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolResult:
        browser_service = self._require_browser_service(context)
        payload = await browser_service.wait(
            str(arguments["session_id"]),
            selector=str(arguments.get("selector")) if arguments.get("selector") else None,
            url_contains=str(arguments.get("url_contains")) if arguments.get("url_contains") else None,
            timeout_seconds=float(arguments.get("timeout_seconds", 10.0)),
        )
        return ToolResult(name=self.name, output=_payload_output(payload))


class BrowserExtractTool(BrowserTool):
    name = "browser.extract"
    description = "Extract text or a structured snapshot from the current browser page."
    required_scope = "browser_read"
    timeout_seconds = 15.0
    argument_schema = {
        "type": "object",
        "properties": {
            "session_id": {"type": "string"},
            "selector": {"type": "string"},
            "mode": {"type": "string"},
        },
        "required": ["session_id"],
        "additionalProperties": False,
    }

    async def run(self, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolResult:
        browser_service = self._require_browser_service(context)
        payload = await browser_service.extract(
            str(arguments["session_id"]),
            selector=str(arguments.get("selector")) if arguments.get("selector") else None,
            mode=str(arguments.get("mode", "text")),
        )
        return ToolResult(name=self.name, output=_payload_output(payload))


class BrowserCloseTool(BrowserTool):
    name = "browser.close"
    description = "Close a managed browser session."
    required_scope = "browser_read"
    timeout_seconds = 10.0
    argument_schema = {
        "type": "object",
        "properties": {"session_id": {"type": "string"}},
        "required": ["session_id"],
        "additionalProperties": False,
    }

    async def run(self, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolResult:
        browser_service = self._require_browser_service(context)
        payload = await browser_service.close(str(arguments["session_id"]))
        await _record_event(
            context,
            "browser_session_closed",
            f"browser_session_id={arguments['session_id']}",
        )
        return ToolResult(name=self.name, output=_payload_output(payload))


class WeatherLookupWebTool(BrowserTool):
    name = "weather.lookup_web"
    description = "Look up weather by loading a browser page and extracting the result."
    required_scope = "browser_read"
    timeout_seconds = 20.0
    argument_schema = {
        "type": "object",
        "properties": {"location": {"type": "string"}},
        "required": ["location"],
        "additionalProperties": False,
    }

    async def run(self, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolResult:
        browser_service = self._require_browser_service(context)
        location = str(arguments["location"]).strip()
        weather_url = context.weather_url_template.format(location=quote(location))
        _check_allowed(weather_url, context)
        session = await browser_service.open_session(
            session_name=f"weather-{context.session_id}",
            headless=context.browser_headless,
            start_url=weather_url,
            persistent_profile=False,
            profile_root=context.browser_profile_root,
        )
        extracted = await browser_service.extract(session["session_id"], mode="text")
        payload = {
            "location": location,
            "url": weather_url,
            "summary": extracted["content"],
            "session_id": session["session_id"],
        }
        await _record_event(
            context,
            "browser_navigation_completed",
            f"browser_session_id={session['session_id']} url={weather_url}",
        )
        return ToolResult(name=self.name, output=_payload_output(payload))


class MailSendWebTool(BrowserTool):
    name = "mail.send_web"
    description = "Send an email through a configured webmail provider in a browser session."
    required_scope = "browser_auth"
    timeout_seconds = 30.0
    argument_schema = {
        "type": "object",
        "properties": {
            "to": {"type": "string"},
            "subject": {"type": "string"},
            "body": {"type": "string"},
            "session_name": {"type": "string"},
        },
        "required": ["to", "subject", "body"],
        "additionalProperties": False,
    }

    async def run(self, arguments: dict[str, Any], context: ToolExecutionContext) -> ToolResult:
        browser_service = self._require_browser_service(context)
        if context.mail_web_provider != "gmail":
            raise ProviderRequestError(
                f"Unsupported webmail provider '{context.mail_web_provider}'."
            )
        compose_url = "https://mail.google.com/mail/u/0/#inbox?compose=new"
        _check_allowed(compose_url, context)
        session = await browser_service.open_session(
            session_name=str(arguments.get("session_name") or f"mail-{context.session_id}"),
            headless=context.browser_headless,
            start_url=compose_url,
            persistent_profile=context.browser_allow_persistent_auth,
            profile_root=context.browser_profile_root,
        )
        session_id = session["session_id"]
        await browser_service.wait(
            session_id,
            selector="input[aria-label='Recipients']",
            timeout_seconds=10.0,
        )
        await browser_service.type(
            session_id,
            "input[aria-label='Recipients']",
            str(arguments["to"]),
        )
        await browser_service.type(
            session_id,
            "input[name='subjectbox']",
            str(arguments["subject"]),
        )
        await browser_service.type(
            session_id,
            "div[aria-label='Message Body']",
            str(arguments["body"]),
        )
        await browser_service.click(session_id, "div[role='button'][data-tooltip*='Send']")
        snapshot = await browser_service.snapshot(session_id)
        await _record_event(
            context,
            "browser_element_clicked",
            f"browser_session_id={session_id} selector=send",
        )
        payload = {
            "provider": context.mail_web_provider,
            "to": str(arguments["to"]),
            "subject": str(arguments["subject"]),
            "status": "sent",
            "session_id": session_id,
            "title": snapshot.title,
        }
        return ToolResult(name=self.name, output=_payload_output(payload))
