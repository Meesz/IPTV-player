# Contributing

Simple IPTV Player is a PyQt6 desktop app for M3U/Xtream live TV and XMLTV EPG, with local
SQLite state. It has no backend, accounts, or sync. See [docs/product.md](docs/product.md) for
the implemented scope and non-goals (cloud sync, recording, installers and backend APIs are not
implemented, so please open an issue to discuss before working on anything like that).

## Setup

Follow [README.md](README.md) and [docs/development.md](docs/development.md). In short, create a
virtualenv and install the dev dependencies, then enable the git hooks (ruff on commit):

```bash
pip install -r requirements-dev.txt
pre-commit install
```

## Before opening a pull request

Run the same checks CI runs, from the repo root:

```bash
ruff check .
ruff format --check .
python -m pytest -q
mypy app core infra ui
```

- `mypy` is an error-count ratchet: the number of errors must not rise.
- CI runs the tests on Python 3.12 and 3.14.
- Ruff configuration lives in `pyproject.toml`; use `ruff format` to fix formatting.

## Project rules

The full list is in [AGENTS.md](AGENTS.md) and the "Coding Expectations" in
[docs/development.md](docs/development.md). The main points:

- Widgets, windows and dialogs go through controllers/services; they must not call SQLite
  repositories, parsers, or Xtream HTTP directly. `tests/test_layer_boundaries.py` enforces this.
- Tests must not need libvlc. Use `tmp_path` databases and mocked `requests`; never touch
  `~/.simple_iptv/`.
- Never log Xtream passwords or channel URLs.
- Keep the channel list virtualized (`QListView` + model + delegate), not per-row widgets.
- Update the docs when commands, setup, architecture or behaviour change.

## Pull requests

- Branch off `main` and keep pull requests small and focused.
- Describe what changed, why, and how you tested it.

## Bug reports

Do not paste real playlist URLs, Xtream credentials, or unredacted logs (for example
`~/.simple_iptv/iptv_player.log`) into issues. Redact them first.

## License

By contributing, you agree that your contributions are licensed under the [MIT License](LICENSE).
