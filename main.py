import contextlib
import re
import secrets
from typing import Any

import httpx
import uvicorn
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from starlette.datastructures import Headers
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Receive, Scope, Send

BASE_URL = "https://skanevux.se"
SLUG_PATTERN = re.compile(r"^[a-z0-9-]+$")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SKANEVUX_MCP_",
        env_file=".env",
        extra="ignore",
    )

    api_timeout_seconds: float = 30.0
    user_agent: str = "skanevux-mcp/0.1"

    host: str = "0.0.0.0"
    port: int = 8000
    mcp_path: str = "/mcp"
    allowed_hosts: str = "localhost:*,127.0.0.1:*"
    allowed_origins: str = "http://localhost:*,http://127.0.0.1:*"

    api_key: str = Field(default="", validate_default=True)

    @field_validator("api_key")
    @classmethod
    def _require_api_key(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError(
                "SKANEVUX_MCP_API_KEY must be set to a non-empty value; "
                "the MCP path requires 'Authorization: Bearer <key>'."
            )
        return v


settings = Settings()

mcp = MCPServer("Skanevux MCP")

http_client = httpx.AsyncClient(
    base_url=BASE_URL,
    timeout=settings.api_timeout_seconds,
    follow_redirects=False,
    headers={"User-Agent": settings.user_agent},
)


async def _fetch_json(path: str, params: dict[str, Any] | None = None) -> Any:
    try:
        response = await http_client.get(path, params=params)
    except httpx.TimeoutException:
        raise ValueError("Request timed out, please try again.") from None
    except httpx.RequestError:
        raise ValueError("Could not reach the data source, please try again later.") from None
    if response.is_redirect:
        raise ValueError("Unexpected redirect, please try again later.")
    if response.is_error:
        raise ValueError("Could not retrieve the requested data, please try again later.")
    return response.json()


async def _fetch_html(path: str) -> str:
    try:
        response = await http_client.get(path)
    except httpx.TimeoutException:
        raise ValueError("Request timed out, please try again.") from None
    except httpx.RequestError:
        raise ValueError("Could not reach the data source, please try again later.") from None
    if response.is_redirect:
        raise ValueError("Unexpected redirect, please try again later.")
    if response.is_error:
        if response.status_code == 404:
            raise ValueError("No job page found for that occupation.")
        raise ValueError("Could not retrieve the job details, please try again later.")
    return response.text


def _flatten_jobs(items: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {"title": item["title"]["rendered"], "slug": item["slug"], "link": item["link"]}
        for item in items
    ]


def _html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return md(str(soup)).strip()


@mcp.tool()
async def list_job_categories() -> list[dict[str, Any]]:
    """List all occupation areas on skanevux.se.

    Returns a list of objects with `id` (used to filter in `list_jobs`), `name`
    (occupation area in Swedish), and `count` (number of jobs in the area).
    """
    return await _fetch_json(
        "/wp-json/wp/v2/job_category",
        params={"per_page": "100", "_fields": "id,name,count"},
    )


@mcp.tool()
async def list_jobs(category_id: int) -> list[dict[str, str]]:
    """List all jobs in a specific occupation area.

    Args:
        category_id: The `id` of a job category from `list_job_categories`.
    """
    data = await _fetch_json(
        "/wp-json/wp/v2/job",
        params={
            "job_category": str(category_id),
            "per_page": "100",
            "_fields": "title,slug,link",
        },
    )
    return _flatten_jobs(data)


@mcp.tool()
async def search_jobs(query: str) -> list[dict[str, str]]:
    """Search for jobs by occupation name on skanevux.se.

    The search matches substrings in job titles. Titles are plural Swedish
    occupation-group names. Use a short Swedish stem for best results
    (e.g. "underskotersk" instead of "underskoterska", "elektriker").

    Args:
        query: A short Swedish occupation search term.
    """
    data = await _fetch_json(
        "/wp-json/wp/v2/job",
        params={"search": query, "per_page": "100", "_fields": "title,slug,link"},
    )
    return _flatten_jobs(data)


@mcp.tool()
async def get_job_details(slug: str) -> dict[str, str]:
    """Get detailed job information including salary, job chances and forecast.

    Retrieves the full job page from skanevux.se and returns it as text.
    The page contains salary levels (Loneniva), job chances, and the
    Arbetsformedlingen forecast for Skane lan.

    Args:
        slug: The job's URL slug from `search_jobs` or `list_jobs` results.
    """
    if not SLUG_PATTERN.match(slug):
        raise ValueError("Invalid slug format.")
    html = await _fetch_html(f"/yrken/{slug}/")
    return {"url": f"{BASE_URL}/yrken/{slug}/", "text": _html_to_text(html)}


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> PlainTextResponse:
    return PlainTextResponse("ok")


class BearerAuthMiddleware:
    def __init__(self, app: ASGIApp, api_key: str, protected_path: str) -> None:
        self.app = app
        self.api_key = api_key.encode("utf-8")
        self.protected_path = protected_path

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["path"].startswith(self.protected_path):
            scheme, _, credentials = (
                Headers(scope=scope).get("Authorization", "").partition(" ")
            )
            if scheme.lower() != "bearer" or not secrets.compare_digest(
                credentials.encode("utf-8"), self.api_key
            ):
                await PlainTextResponse("Unauthorized", status_code=401)(scope, receive, send)
                return
        await self.app(scope, receive, send)


app = mcp.streamable_http_app(
    streamable_http_path=settings.mcp_path,
    stateless_http=True,
    json_response=True,
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=settings.allowed_hosts.split(","),
        allowed_origins=settings.allowed_origins.split(","),
    ),
)

_mcp_lifespan = app.router.lifespan_context


@contextlib.asynccontextmanager
async def _lifespan(scope):
    try:
        async with _mcp_lifespan(scope):
            yield
    finally:
        await http_client.aclose()


app.router.lifespan_context = _lifespan

app.add_middleware(
    BearerAuthMiddleware,
    api_key=settings.api_key,
    protected_path=settings.mcp_path,
)


if __name__ == "__main__":
    uvicorn.run(app, host=settings.host, port=settings.port)
