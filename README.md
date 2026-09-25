# skanevux-mcp

MCP server exposing job-prospect data (salary, job chances, forecasts) from [skanevux.se](https://skanevux.se).

## Tools

| Tool | Description |
|---|---|
| `list_job_categories` | List all occupation areas |
| `list_jobs` | List jobs in a category |
| `search_jobs` | Search jobs by occupation name |
| `get_job_details` | Get salary, job chances and forecast for a job |

## Run locally

```bash
cp .env.example .env
# Edit .env and set SKANEVUX_MCP_API_KEY
uv sync
uv run python main.py
```

## Run with Docker

```bash
cp .env.example .env
# Edit .env with real values
docker compose up --build
```
