# Development Setup

This repository uses Poetry 2.0+ to manage one development virtual environment at the repository root. Each member keeps its own runtime dependencies, while local members are installed editable into the shared environment.

## Prerequisites

- Python 3.12 or newer
- Poetry 2.0 or newer
- VS Code with the Python and Pylance extensions

Verify Poetry with:

```bash
poetry --version
```

## First-time setup

From the `company-data` directory, install every workspace member and the development tools:

```bash
poetry env use python3
poetry install --with dev
```

Poetry creates the single root environment. The root `pyproject.toml` installs `api`, `rag`, `agent`, `core`, `mcp`, and `client` as editable local dependencies, plus the shared `company-data-crawler` package from PyPI, which provides both the `CompanyData` model and the crawler. Production deployments should run Poetry from the individual member directory so only that member's dependencies are installed.

## Activate and select the environment

Linux/macOS:

```bash
source "$(poetry env info --path)/bin/activate"
```

Windows PowerShell:

```powershell
& "$(poetry env info --path)\Scripts\Activate.ps1"
```

In VS Code, select the interpreter returned by:

```bash
poetry env info --path
```

The checked-in `.vscode/settings.json` adds each member directory to Pylance's analysis paths, so imports and autocomplete work across the repository.

## Convenience scripts

The setup scripts install the root environment, activate it, and change into a selected member directory:

```bash
source common_setup.sh api
```

```powershell
. .\common_setup.psl api
```

Omit `api` to choose from the available member projects interactively.

## Adding dependencies

Add runtime dependencies in the relevant member's `pyproject.toml`, then regenerate the lock file from the root:

```bash
poetry lock
poetry install --with dev
```

Do not add heavy service dependencies such as `torch` or `langchain` to the root project unless the development environment needs them; they belong to the `rag` member.


Add it to the member project, not the root:

```bash
poetry add --directory rag seleniumbase
```

Equivalent:

```bash
cd rag
poetry add seleniumbase
cd ..
```

Then refresh the shared development environment:

```bash
poetry lock
poetry install --with dev
```

This adds `seleniumbase` only to `pyproject.toml`, keeping it out of lightweight services such as `api`.

For a pinned version:

```bash
poetry add --directory rag "seleniumbase>=4. treinta"
```

Use a real version number in place of the example. Verify with:

```bash
poetry show --directory rag seleniumbase
```