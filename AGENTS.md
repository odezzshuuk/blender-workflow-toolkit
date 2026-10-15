# Repository Guidelines

## Project Structure & Module Organization

This workspace currently contains no source code, tests, assets, or build configuration. Treat it as an initial scaffold for `blender-workflow-toolkit`; no application architecture has been established.

When introducing implementation files, organize related functionality into clearly named modules and keep tests separate from runtime code. Document the chosen layout in `README.md`, including any Blender scripts, add-ons, example scenes, or supporting assets. Do not use `.agents/`, `.codex/`, `.aws/`, or `.git/` for application code.

## Build, Test, and Development Commands

No build, test, lint, or local execution commands are currently configured. Do not assume commands such as `npm test`, `make build`, or `pytest` are available.

When adding tooling, document exact installation and execution commands in `README.md`. Specify supported Blender and language runtime versions, required dependencies, and whether each command runs inside Blender or from a terminal.

## Coding Style & Naming Conventions

No formatter, linter, or language-specific style configuration exists yet. Follow the conventions of the language introduced and keep naming and indentation consistent within each module. For Python contributions, use four-space indentation, `snake_case` for functions and modules, and `PascalCase` for classes. Add shared tooling configuration when adopting a formatter or linter.

## Testing Guidelines

No testing framework or coverage threshold is established. Add appropriate validation alongside new behavior and document how to run it. For Blender-dependent changes, record the Blender version, setup steps, expected result, and any manual verification required. Use descriptive test names that identify the behavior being checked.

## Commit & Pull Request Guidelines

Git history is unavailable in this workspace, so no existing commit convention can be verified. Use concise, imperative commit subjects, such as `Add scene export helper`, and keep changes focused.

Pull requests should explain the purpose, summarize changes, link relevant issues, and report validation results. Include screenshots for visible Blender UI changes and disclose compatibility limits or untested behavior.
