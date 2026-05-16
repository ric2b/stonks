package app

import (
	"context"
	"database/sql"

	"stonks/internal/database"
	"stonks/internal/stockdata"
	"stonks/internal/yahoo"
)

type App struct {
	ctx     context.Context
	db      *sql.DB
	service *stockdata.Service
}

func New() *App {
	return &App{}
}

func (a *App) Startup(ctx context.Context) {
	a.ctx = ctx

	dbPath := database.DefaultDBPath()
	db, err := database.InitDB(dbPath)
	if err != nil {
		panic("failed to open database: " + err.Error())
	}
	a.db = db

	client := yahoo.NewClient()
	a.service = stockdata.NewService(client)

	a.startNameFetch()
	a.startPriceRefresh()
}

func (a *App) Shutdown(_ context.Context) {
	if a.db != nil {
		a.db.Close()
	}
}

func (a *App) GetWatchlist() []database.WatchlistEntry {
	entries, err := database.GetWatchlist(a.db)
	if err != nil {
		return nil
	}
	if entries == nil {
		return []database.WatchlistEntry{}
	}
	return entries
}

func (a *App) AddTicker(ticker string) error {
	return database.AddTicker(a.db, ticker)
}

func (a *App) RemoveTicker(ticker string) error {
	return database.RemoveTicker(a.db, ticker)
}

func (a *App) ReorderWatchlist(tickers []string) error {
	return database.ReorderWatchlist(a.db, tickers)
}

func (a *App) SearchTickers(query string) []yahoo.SearchResult {
	results, err := a.service.SearchTickers(query, 5)
	if err != nil {
		return nil
	}
	if results == nil {
		return []yahoo.SearchResult{}
	}
	return results
}

func (a *App) ValidateTicker(ticker string) bool {
	return a.service.ValidateTicker(ticker)
}

func (a *App) GetSetting(key string) string {
	val, _ := database.GetSetting(a.db, key, "")
	return val
}

func (a *App) SetSetting(key string, value string) {
	database.SetSetting(a.db, key, value)
}
