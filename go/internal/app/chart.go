package app

import (
	"stonks/internal/stockdata"
	"stonks/internal/yahoo"
)

type ChartResponse struct {
	Timestamps []int64    `json:"timestamps"`
	Open       []*float64 `json:"open"`
	High       []*float64 `json:"high"`
	Low        []*float64 `json:"low"`
	Close      []*float64 `json:"close"`
	Volume     []*float64 `json:"volume"`
	Meta       map[string]any `json:"meta"`
}

type TimeRangeInfo struct {
	Label    string `json:"label"`
	Period   string `json:"period"`
	Interval string `json:"interval"`
}

func (a *App) FetchChartData(ticker string, period string, interval string) *ChartResponse {
	data, err := a.service.FetchHistory(ticker, period, interval)
	if err != nil || data == nil {
		return nil
	}
	return &ChartResponse{
		Timestamps: data.Timestamps,
		Open:       data.Open,
		High:       data.High,
		Low:        data.Low,
		Close:      data.Close,
		Volume:     data.Volume,
		Meta:       data.Meta,
	}
}

func (a *App) GetTimeRanges() []TimeRangeInfo {
	ranges := make([]TimeRangeInfo, len(stockdata.TimeRanges))
	for i, tr := range stockdata.TimeRanges {
		ranges[i] = TimeRangeInfo{
			Label:    tr.Label,
			Period:   tr.Period,
			Interval: tr.Interval,
		}
	}
	return ranges
}

func (a *App) FetchTickerInfo(ticker string) map[string]any {
	info, err := a.service.FetchInfo(ticker)
	if err != nil {
		return nil
	}
	return info
}

func (a *App) IsIntradayInterval(interval string) bool {
	return stockdata.IntradayIntervals[interval]
}

func (a *App) PrefetchHistory(period string, interval string) {
	go func() {
		tickers := a.getWatchlistTickers()
		if len(tickers) == 0 {
			return
		}
		results := a.service.BatchFetchHistory(tickers, period, interval)
		a.service.PopulateHistoryCache(results, period, interval)
	}()
}

func (a *App) GetChartDataCached(ticker string, period string, interval string) *ChartResponse {
	if !a.service.IsHistoryCached(ticker, period, interval) {
		return nil
	}
	return a.FetchChartData(ticker, period, interval)
}

func (a *App) FetchNewsItems(ticker string) []yahoo.NewsItem {
	items, err := a.service.FetchNews(ticker, 8)
	if err != nil {
		return nil
	}
	if items == nil {
		return []yahoo.NewsItem{}
	}
	return items
}
