# Daily Report Pipeline

Automated daily intelligence report collection and generation pipeline.

## Structure

- `bin/` — Shell scripts for each daily report (search query definitions)
- `collector/` — Python collector engine (multi-language search, deduplication, clustering)
- `temp/` — Temporary working files

## Environment

All Python tasks run in the `daily_report_env` conda environment.

```bash
conda activate daily_report_env
pip install -r requirements.txt
```

## Usage

Each report is triggered by a shell script in `bin/`. The scripts define search queries and invoke the Python collector pipeline.

## Cron Integration

Integrated with Hermes Agent cron system via `~/.hermes/cron/jobs.json`.

## Reports

Generated reports are stored in `cron/reports/` (managed by the cron scheduler).
