# Stonks

<img src="assets/com.stonks.Stonks.svg" width="96" alt="Stonks icon"/>

Desktop stock tracker for Linux, inspired by the macOS Stocks app.

## Features

- Watchlist management (add/remove/reorder tickers)
- Interactive price charts with time range selectors
- Key financial stats for each stock

## Development

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --all-extras
uv run stonks
```

## Testing

```bash
uv run pytest
uv run ruff check .
```

## Releasing

```bash
./release.sh 0.2.0
git push && git push --tags
```

The script updates the version in `pyproject.toml`, commits, and creates a `v0.2.0` tag. Pushing the tag triggers the release workflow which builds and uploads macOS (DMG), Linux (AppImage), and Snap packages.

## License

GPL-3.0
