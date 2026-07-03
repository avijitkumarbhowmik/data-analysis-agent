# Capabilities Index

> **Boilerplate status:** The spec-writer sub-agent creates one file per capability in this directory. Each file describes exactly one discrete thing the agent can do.

---

## What Is a Capability?

A capability is a single, discrete action or behavior the agent performs. Examples:
- "Search the web for companies matching criteria X"
- "Draft a personalized email given a lead profile"
- "Send a Slack notification when a threshold is crossed"

## Capabilities in This Project

| Capability | Phase | File |
|-----------|-------|------|
| Workspace Management | 1 | [workspace-management.md](workspace-management.md) |
| Dataset Upload | 1 | [dataset-upload.md](dataset-upload.md) |
| PII Masking (Privacy Boundary) | 1 | [pii-masking.md](pii-masking.md) |
| Local Code Analysis (the Ask loop) | 1 | [local-code-analysis.md](local-code-analysis.md) |
| Chart Generation | 2 | [chart-generation.md](chart-generation.md) |
| Data-Quality Flags | 2 | [data-quality-flags.md](data-quality-flags.md) |
| Follow-up Suggestions | 2 | [followup-suggestions.md](followup-suggestions.md) |
| Conversation Memory | 2 | [conversation-memory.md](conversation-memory.md) |
| Run History | 2 | [run-history.md](run-history.md) |
| Live Query Feedback (Streaming + Cost) | 2 | [live-query-feedback.md](live-query-feedback.md) |
| Multi-File Joins | 3 | [multi-file-joins.md](multi-file-joins.md) |
| Multi-Sheet Excel | 3 | [multi-sheet-excel.md](multi-sheet-excel.md) |
| Column Notes & Business Rules | 3 | [column-notes-and-rules.md](column-notes-and-rules.md) |
| Derived Datasets & Exports | 3 | [derived-datasets-and-exports.md](derived-datasets-and-exports.md) |
| Adaptive Reasoning (Clarify + Plan + Iterate) | 3 | [adaptive-reasoning.md](adaptive-reasoning.md) |

## How to Add a New Capability

Run `/zero-shot-build [description]` on the existing spec. The spec-writer sub-agent will:
1. Create a new file in this directory (`<name>.md`, no number prefix)
2. Update this index
3. Flag any dependencies on existing capabilities
4. Self-review that it fits the architecture and data model before returning

## Capability File Template

Each capability file should answer:
- **What it does** (one sentence)
- **Inputs** (what data it receives)
- **Outputs** (what it produces)
- **External calls** (APIs, LLMs, databases it touches)
- **Error cases** (what can go wrong and how it's handled)
- **Success criteria** (how we test it)
