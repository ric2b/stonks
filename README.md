# Stonks

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

## License

GPL-3.0
