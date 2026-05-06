# Stonks

<img src="assets/com.stonks.Stonks.svg" width="96" alt="Stonks icon"/>

Desktop stock tracker for Linux and MacOS.

<img width="902" height="776" alt="image" src="https://github.com/user-attachments/assets/d8ef0c6a-7d26-4cef-85fb-54b87eb90827" />

## Install

Download the latest release from the [Releases](../../releases/latest) page.

### macOS

Download `stonks-macos.dmg`, open it, and drag **Stonks** to your Applications folder.

### Linux (AppImage)

Download `stonks-x86_64.AppImage`, make it executable, and run it:

```bash
chmod +x stonks-x86_64.AppImage
./stonks-x86_64.AppImage
```

### Linux (Snap)

Download the `.snap` file and install it locally:

```bash
sudo snap install --dangerous stonks_*.snap
```

## Features

- Watchlist management (add/remove/reorder tickers)
- Interactive price charts with time range selectors
- Key financial stats for each stock

## Development

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

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
./release.sh X.Y.Z
git push && git push --tags
```

The script updates the version in `pyproject.toml`, commits, and creates a `v0.2.0` tag. Pushing the tag triggers the release workflow which builds and uploads macOS (DMG), Linux (AppImage), and Snap packages.

## License

GPL-3.0
