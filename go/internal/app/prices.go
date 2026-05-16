package app

import (
	"time"

	"stonks/internal/database"
	"stonks/internal/stockdata"

	"github.com/wailsapp/wails/v2/pkg/runtime"
)

type PriceUpdate struct {
	Ticker    string  `json:"ticker"`
	Price     float64 `json:"price"`
	ChangePct float64 `json:"changePct"`
}

type NameUpdate struct {
	Ticker string `json:"ticker"`
	Name   string `json:"name"`
}

func (a *App) FetchPricesNow() []PriceUpdate {
	tickers := a.getWatchlistTickers()
	if len(tickers) == 0 {
		return nil
	}

	prices, err := a.service.FetchPrices(tickers)
	if err != nil {
		return nil
	}

	var updates []PriceUpdate
	for ticker, data := range prices {
		updates = append(updates, PriceUpdate{
			Ticker:    ticker,
			Price:     data.Price,
			ChangePct: data.ChangePct,
		})
	}
	return updates
}

func (a *App) startPriceRefresh() {
	go func() {
		// Initial fetch after short delay
		time.Sleep(500 * time.Millisecond)
		a.emitPriceUpdates()

		ticker := time.NewTicker(60 * time.Second)
		defer ticker.Stop()
		for {
			select {
			case <-ticker.C:
				a.emitPriceUpdates()
			case <-a.ctx.Done():
				return
			}
		}
	}()
}

func (a *App) emitPriceUpdates() {
	updates := a.FetchPricesNow()
	if len(updates) > 0 {
		runtime.EventsEmit(a.ctx, "prices:updated", updates)
	}
}

func (a *App) startNameFetch() {
	go func() {
		tickers := a.getWatchlistTickers()
		if len(tickers) == 0 {
			return
		}

		names := a.service.FetchNames(tickers)
		currencies := a.service.FetchCurrencies(tickers)

		var updates []NameUpdate
		for ticker, name := range names {
			updates = append(updates, NameUpdate{Ticker: ticker, Name: name})
			currency := currencies[ticker]
			if name != "" || currency != "" {
				database.UpdateTickerMeta(a.db, ticker, name, currency)
			}
		}

		if len(updates) > 0 {
			runtime.EventsEmit(a.ctx, "names:updated", updates)
		}
	}()
}

func (a *App) getWatchlistTickers() []string {
	entries, err := database.GetWatchlist(a.db)
	if err != nil {
		return nil
	}
	tickers := make([]string, len(entries))
	for i, e := range entries {
		tickers[i] = e.Ticker
	}
	return tickers
}

func (a *App) GetPriceData(ticker string) *stockdata.PriceData {
	prices, err := a.service.FetchPrices([]string{ticker})
	if err != nil {
		return nil
	}
	if p, ok := prices[ticker]; ok {
		return &p
	}
	return nil
}
