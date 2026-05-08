# Daily Report Pipeline

Multi-language, multi-source daily intelligence collection and report generation pipeline.

## Architecture

```
bin/*.sh          → Shell scripts: search query definitions per task
collector/        → Python collector engine: search, fetch, dedup, cluster
temp/             → Temporary working files (JSON artifacts per run)
```

Each shell script in `bin/` defines a task-specific set of search queries (11 per script: 4 English-focused + 7 multilingual covering zh/ru/ja/ko/hi/he/ar/es/pt/fr/de/hi/tr). The collector engine processes them through a 4-stage pipeline:

1. **Search** — DuckDuckGo HTML API, parallel execution (8 workers)
2. **Fetch** — Full page extraction with readability, parallel (12 workers)
3. **Dedup** — URL + title-key deduplication with domain scoring
4. **Cluster** — Token overlap + release signature matching → event clusters

## Tasks

| Script | Task Name | Description |
|--------|-----------|-------------|
| `ai_agent_daily_report.sh` | ai_agent | AI agent platforms, frameworks, tools, security, research |
| `ai_agent_usecase_daily_report.sh` | ai_agent_usecase | AI agent real-world use cases and deployments |
| `ai_model_daily_report.sh` | ai_model | AI model releases, benchmarks, research papers |
| `con_tech_daily_report.sh` | con_tech | Construction tech, proptech, robotics, BIM, digital twins |
| `headhunter_daily_report.sh` | headhunter | AI/tech job market intelligence |
| `selfmedia_daily_report.sh` | selfmedia | Self-media / creator economy trends |
| `international_affairs_daily_report.sh` | international_affairs | US-Israel-Iran geopolitical news |

## Environment

All Python tasks run in the `daily-report-env` conda environment:

```bash
conda activate daily-report-env
pip install -r requirements.txt
```

Dependencies: `requests`, `beautifulsoup4`, `readability-lxml`, `lxml`, `python-dateutil`

## Usage

Run a single task:
```bash
bash bin/ai_agent_daily_report.sh
```

Output JSON files are written to `temp/`:
- `*_raw_search_*.json` — Raw DuckDuckGo search results
- `*_raw_pages_*.json` — Full page content after fetch
- `*_structured_*.json` — Deduped + clustered events with metadata
- `*_agent_input_*.json` — Final structured payload for AI report generation

## Cron Integration

Tasks are scheduled via Hermes Agent cron system (`~/.hermes/cron/jobs.json`). Each cron run invokes the corresponding shell script, which outputs `agent_input.json` consumed by the AI agent for report generation.

## Configuration

- `--top-k`: Results per query (default: 10)
- `--final-event-cap`: Max event clusters (default: 12)
- `--max-content-chars`: Max page content length (default: 4000)
- `DAILY_REPORT_PYTHON`: Override Python binary path
