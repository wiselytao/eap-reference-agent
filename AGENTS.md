# Repository Guidelines

## Project Structure and Module Organization
This repository is documentation-only. Content lives in two top-level folders:
- `PRD/` stores product requirement documents (PRD) and guardrails.
- `Reference/` stores reference PRDs and planning notes like `Reference/TODO.md`.

If you add new documents, keep them in the closest matching folder and use clear, versioned names (example: `reference_agent_PRD_v1.en.md`).

## Build, Test, and Development Commands
There is no build system or local runtime in this repository. Typical work is editing Markdown files directly. If you add tooling later, document the commands here with a short explanation (example: `npm test` for unit tests).

## Coding Style and Naming Conventions
- Use Markdown for all content.
- Keep headings short and descriptive, and prefer ordered lists for step-by-step flows.
- File naming: lowercase with underscores, include version and language when relevant (example: `reference_agent_PRD_v1.en_with_guardrails.md`).
- Keep lines readable; wrap long paragraphs around 80-100 characters when practical.

## Testing Guidelines
There are no automated tests. If you introduce code or scripts, add a minimal test plan and explain how to run it. For documentation changes, perform a quick pass to confirm links and section numbering are correct.

## Commit and Pull Request Guidelines
There is no commit history in this repository yet, so no established convention exists. Use concise, imperative subjects (example: "Add v1.1 TODOs"). In pull requests, include:
- a short summary of the change,
- the affected files or sections,
- any follow-up tasks or open questions.

## Configuration and Security Notes
Do not add secrets or credentials to this repository. If you introduce configuration files, provide template examples and document required fields.

## Change Control
1. Before making changes, provide a brief plan and wait for approval.
2. Every change must update `CHANGELOG.md` and `VERSION.md`.
3. Each change increments the minor version. Major version increments require explicit user request or approval.
