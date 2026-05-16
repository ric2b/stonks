package main

import (
	"embed"
	"log"
	"runtime"

	"github.com/wailsapp/wails/v2"
	"github.com/wailsapp/wails/v2/pkg/menu"
	"github.com/wailsapp/wails/v2/pkg/menu/keys"
	"github.com/wailsapp/wails/v2/pkg/options"
	"github.com/wailsapp/wails/v2/pkg/options/assetserver"

	"stonks/internal/app"
)

//go:embed all:frontend/dist
var assets embed.FS

func main() {
	a := app.New()

	appOptions := &options.App{
		Title:     "Stonks",
		Width:     900,
		Height:    600,
		MinWidth:  900,
		MinHeight: 600,
		AssetServer: &assetserver.Options{
			Assets: assets,
		},
		BackgroundColour: &options.RGBA{R: 30, G: 30, B: 30, A: 255},
		OnStartup:        a.Startup,
		OnShutdown:       a.Shutdown,
		Bind: []interface{}{
			a,
		},
	}

	if runtime.GOOS == "darwin" {
		appOptions.Menu = buildMacMenu()
	}

	err := wails.Run(appOptions)
	if err != nil {
		log.Fatal(err)
	}
}

func buildMacMenu() *menu.Menu {
	appMenu := menu.NewMenu()

	appMenu.Append(menu.AppMenu())
	appMenu.Append(menu.EditMenu())

	viewMenu := appMenu.AddSubmenu("View")
	viewMenu.AddText("Reload", keys.CmdOrCtrl("r"), func(_ *menu.CallbackData) {})

	return appMenu
}
