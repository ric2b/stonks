# Stonks

<img src="assets/com.stonks.Stonks.svg" width="96" alt="Stonks icon"/>

Desktop stock tracker for Linux and macOS. Built with Go + Wails.

<img width="946" height="881" alt="image" src="https://github.com/user-attachments/assets/34b34e95-6909-479d-82fe-7db325b26225" />

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

Requires `libwebkit2gtk-4.1` on your system.

## Features

- Watchlist management (add/remove/reorder via drag-and-drop)
- Interactive price charts with time range selectors
- Drag-to-compare price changes between two points
- Key financial stats grid
- News feed with links to articles
- Market state indicator
- Keyboard shortcuts (/, 1-9, arrows, Delete)
- Session restore (remembers last ticker and time range)

## Development

Requires Go 1.23+, Node.js 20+, and [Wails v2](https://wails.io/docs/gettingstarted/installation).

```bash
cd go
wails dev
```

### Linux build dependencies

```bash
sudo apt-get install libgtk-3-dev libwebkit2gtk-4.1-dev
```

## Testing

```bash
cd go
go test ./...
```

Frontend type check:

```bash
cd go/frontend
npm ci
npx tsc --noEmit
```

## Building

```bash
cd go
wails build
```

Output binary is in `go/build/bin/`.

## Releasing

Push a version tag to trigger the release workflow:

```bash
git tag v0.6.0
git push && git push --tags
```

The workflow builds macOS (universal DMG) and Linux (AppImage) packages and creates a GitHub release.

## License

GPL-3.0
