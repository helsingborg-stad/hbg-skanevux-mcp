# skanevux-mcp

MCP server exposing job-prospect data (salary, job chances, forecasts) from [skanevux.se](https://skanevux.se).

## Tools

| Tool | Description |
|---|---|
| `list_job_categories` | List all occupation areas |
| `list_jobs` | List jobs in a category |
| `search_jobs` | Search jobs by occupation name |
| `get_job_details` | Get salary, job chances and forecast for a job |

## Recommended system prompt

```
Use the skanevux tools when the user asks about salary, job chances or job prospects for an occupation or course.
1. search_jobs with a short Swedish occupation stem (e.g. "underskötersk", "elektriker"). Titles are plural occupation-group names.
2. If there are no relevant hits: list_job_categories → pick the best category → list_jobs(category_id) → pick the matching job(s).
3. get_job_details(slug) for the chosen job(s). Summarize salary (Lönenivå), job chances and the Arbetsförmedlingen forecast, and include the page URL as the source.
4. If nothing fits, say so and link to https://skanevux.se/yrken/
Data covers vocational occupations; forecasts are for Skåne län.
```

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
