"""WebFetch 工具 — 抓取网页并提取文本。"""

from __future__ import annotations

from shaw.provider import ToolDef, ToolParam
from shaw.tools.registry import BaseTool

_MAX_BYTES = 512 * 1024  # 512KB


class WebFetchTool(BaseTool):
    """抓取 URL 内容，返回纯文本（去 HTML 标签）。"""

    @property
    def tool_def(self) -> ToolDef:
        return ToolDef(
            name="WebFetch",
            description="Fetch a URL and return its text content (HTML stripped).",
            params=[
                ToolParam(name="url", type="string", description="URL to fetch", required=True),
                ToolParam(name="max_chars", type="integer", description="Max characters to return", required=False),
            ],
        )

    def execute(self, url: str, max_chars: int = 8000) -> str:
        try:
            import httpx
        except ImportError as e:
            return f"Error: httpx not installed: {e}"

        try:
            with httpx.Client(follow_redirects=True, timeout=20) as client:
                resp = client.get(url)
                resp.raise_for_status()
        except httpx.HTTPError as e:
            return f"Error fetching {url}: {e}"

        content_type = resp.headers.get("content-type", "")
        body = resp.text[:_MAX_BYTES]

        if "html" in content_type.lower():
            body = self._strip_html(body)

        if len(body) > max_chars:
            body = body[:max_chars] + f"\n... (truncated at {max_chars} chars)"
        return body

    @staticmethod
    def _strip_html(html: str) -> str:
        """粗略去除 HTML 标签与脚本/样式。"""
        import re

        html = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r"<[^>]+>", "", html)
        html = re.sub(r"&nbsp;", " ", html)
        html = re.sub(r"&amp;", "&", html)
        html = re.sub(r"&lt;", "<", html)
        html = re.sub(r"&gt;", ">", html)
        html = re.sub(r"\n\s*\n+", "\n\n", html)
        return html.strip()
