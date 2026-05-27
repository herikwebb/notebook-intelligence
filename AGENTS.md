# AGENTS.md

## Cursor Cloud specific instructions

### Overview

Notebook Intelligence (NBI) is a JupyterLab 4.x extension with a Python server extension and a TypeScript frontend. Development setup and standard commands are documented in `CONTRIBUTING.md`.

### Running services

Start JupyterLab (with the NBI extension) for development:

```bash
jupyter lab --no-browser --ip=0.0.0.0 --port=8888 --ServerApp.token="" --ServerApp.password=""
```

For auto-rebuilding the frontend on source changes, run `jlpm watch` in a separate terminal (see `CONTRIBUTING.md`).

### Key commands

| Task | Command |
|---|---|
| Install JS deps | `jlpm install` |
| Build frontend | `jlpm build` |
| Lint (check only) | `jlpm lint:check` |
| Lint (auto-fix) | `jlpm lint` |
| TS unit tests | `jlpm test` |
| Python unit tests | `python3 -m pytest tests/ -v` |

### Gotchas

- `jlpm` is JupyterLab's bundled Yarn — it becomes available after `pip install jupyterlab`. Do not use a system-wide `yarn`.
- `/usr/share/jupyter` may need `chmod 777` for `jupyter labextension develop . --overwrite` to succeed (the command symlinks the built extension into the system data dir).
- The `@jupyterlab/launcher` version constraint (`~4.2.0`) in `package.json` may show a compatibility warning with `jupyter labextension list`, but the extension loads fine in development mode.
- The LiteLLM warnings about missing `botocore` at startup are harmless — they only affect AWS Bedrock/SageMaker provider paths.
- `$HOME/.local/bin` must be on `PATH` for `jupyter`, `jlpm`, and `pytest` to be found after user-local pip installs.
- No external databases or Docker containers are needed. Config is file-based (`~/.jupyter/nbi/`).
- LLM provider features (chat, completions) require an API key or account sign-in at runtime — they are optional for building, linting, and testing.
