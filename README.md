# Meeting Agent (Multi-Agent Action Item Extraction & Distribution)

An AI meeting assistant that reads a meeting transcript, extracts and validates action items using a multi-agent workflow, and automatically distributes them to the right places  Notion tasks and email  with built-in self-correction and monitoring.

## What it does

Meetings generate action items, but turning a messy transcript into clean, assigned, trackable tasks is manual and error-prone. This project automates that pipeline end to end:

1. **Ingest** a meeting transcript
2. **Extract** candidate action items using an LLM
3. **Validate** each item through a second agent pass  checking it's a real, actionable task with a clear owner, not a vague mention or a duplicate
4. **Self-correct**: if validation fails, the extraction agent retries with feedback rather than silently producing a bad result
5. **Distribute**: creates the corresponding task in Notion and sends a summary email to relevant participants
6. **Monitor**: the workflow logs its own steps so failures are traceable, not silent

## Why multi-agent, not a single prompt

A single LLM call asked to "extract and send action items" tends to hallucinate owners, miss implicit tasks, or produce items that look right but aren't actionable. Splitting extraction and validation into separate agent roles  with the validator allowed to reject and send work back  catches these failure modes before anything reaches Notion or a real inbox.

## Architecture

```
Transcript
    │
    ▼
Extraction Agent (LangGraph)  ──► candidate action items
    │
    ▼
Validation Agent  ──► pass/fail + feedback
    │
    ├── fail → back to Extraction Agent (self-correction loop)
    │
    └── pass
         │
         ▼
   Distribution layer
    ├── Notion (task creation via MCP)
    └── Email (summary send)
```

## Tech stack

Python, LangGraph, LangChain, FastMCP (Notion integration via Model Context Protocol), Docker, `uv` for dependency management

## Repository structure

```
backend/    Agent workflow, extraction/validation logic, Notion & email integrations
frontend/   User-facing interface for reviewing transcripts and results
```

## Running locally

```bash
docker-compose up
```

or, for local development without containers:

```bash
uv sync
uv run <entry point>
```

Requires API keys for the LLM provider and Notion, set as environment variables (see `.env.example` if present, or the backend config).

## Why I built this

Built to get hands-on with multi-agent orchestration patterns beyond a single-prompt chatbot  specifically the self-correction loop, where one agent's output is checked and, if needed, sent back for revision before it's allowed to take a real-world action (creating a Notion task, sending an email). This mirrors the kind of reliability concerns that come up in production agentic systems, where an LLM acting autonomously needs a check before it does something irreversible.
