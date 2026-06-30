# Prototype guide for Claude Code

Web application for tracking and monitoring golf-related product prices with historical data and basic alert mechanisms.

The source PRD / Epic: https://bytecubed.atlassian.net/wiki/spaces/EA/pages/4658397185/PRD+Golf+Price+Monitoring+Application+2026-06-30

## How this repo is built

This prototype is built in two phases:

1. **Primary build** — `.github/workflows/build.yml` runs you (Claude Code) once to
   build as much of the product as possible, committed directly to the default branch.
2. **Follow-on issues** — after the primary build, each item below is filed as a GitHub
   issue. `.github/workflows/claude.yml` then runs you to implement that one issue as an
   incremental change on top of the default branch and open a pull request. Those pull
   requests are reviewed and merged by a human — do not merge them yourself.

## Planned follow-on work

These will be filed as issues after the primary build, so you don't need to complete
them during the primary build — just leave a clean foundation they can build on:

1. Implement price alert system with configurable thresholds
2. Add multi-user support with user authentication
3. Integrate web scraping for live golf equipment prices
4. Build price trend analysis and visualization dashboard
5. Implement email and SMS alert notifications
6. Add golf course green fee and membership price tracking
7. Implement import/export and data backup features

## Tech stack & conventions

Use Python (Flask/FastAPI) for backend with SQLite for data persistence, and React/Svelte for frontend. Goal: runnable locally with `pip install -r requirements.txt && python app.py` or similar. Primary build should create: database schema for products/prices/history, REST API endpoints for CRUD on tracked items, basic web UI showing current prices and simple price history charts, and manual price input mechanism (no web scraping in MVP). Keep dependencies minimal and focus on a single-user or small-group prototype first. Recommend storing price snapshots with timestamps for trend analysis. Frontend should display a product list, price details, and historical price graph.

## Working agreement

- Build the simplest thing that satisfies the goal — this is a prototype, not
  production. Favor a working end-to-end slice over breadth.
- Keep the project runnable at every step. Document any new setup/run command in the
  README under a "Running" section.
- For follow-on issues, open one pull request per issue and reference the issue with
  "Closes #<number>". Never merge your own pull request.
- Don't introduce secrets or external services that require credentials the repo
  doesn't have.
