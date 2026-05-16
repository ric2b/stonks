package stockdata

import (
	"fmt"
	"sync"
	"time"

	"stonks/internal/cache"
	"stonks/internal/yahoo"
)

type Service struct {
	client       *yahoo.Client
	historyCache *cache.TTLCache[HistoryKey, *yahoo.ChartData]
	infoCache    *cache.TTLCache[string, map[string]any]
	newsCache    *cache.TTLCache[string, []yahoo.NewsItem]
	nameCache    map[string]string
	nameMu       sync.RWMutex
}

func NewService(client *yahoo.Client) *Service {
	return &Service{
		client:       client,
		historyCache: cache.New[HistoryKey, *yahoo.ChartData](60 * time.Second),
		infoCache:    cache.New[string, map[string]any](300 * time.Second),
		newsCache:    cache.New[string, []yahoo.NewsItem](300 * time.Second),
		nameCache:    make(map[string]string),
	}
}

func (s *Service) FetchHistory(ticker, period, interval string) (*yahoo.ChartData, error) {
	key := HistoryKey{ticker, period, interval}
	if data, ok := s.historyCache.Get(key); ok {
		return data, nil
	}

	data, err := s.client.FetchChart(ticker, period, interval)
	if err != nil {
		return nil, err
	}
	if data == nil {
		return nil, fmt.Errorf("no data returned for %s", ticker)
	}

	s.historyCache.Set(key, data)
	return data, nil
}

func (s *Service) IsHistoryCached(ticker, period, interval string) bool {
	_, ok := s.historyCache.Get(HistoryKey{ticker, period, interval})
	return ok
}

func (s *Service) PopulateHistoryCache(results map[string]*yahoo.ChartData, period, interval string) {
	for ticker, data := range results {
		s.historyCache.Set(HistoryKey{ticker, period, interval}, data)
	}
}

func (s *Service) BatchFetchHistory(tickers []string, period, interval string) map[string]*yahoo.ChartData {
	if len(tickers) == 0 {
		return map[string]*yahoo.ChartData{}
	}

	type result struct {
		ticker string
		data   *yahoo.ChartData
	}

	workers := min(len(tickers), 8)
	jobs := make(chan string, len(tickers))
	results := make(chan result, len(tickers))

	var wg sync.WaitGroup
	for i := 0; i < workers; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for ticker := range jobs {
				data, err := s.client.FetchChart(ticker, period, interval)
				if err == nil && data != nil {
					results <- result{ticker, data}
				}
			}
		}()
	}

	for _, t := range tickers {
		jobs <- t
	}
	close(jobs)

	go func() {
		wg.Wait()
		close(results)
	}()

	out := make(map[string]*yahoo.ChartData)
	for r := range results {
		out[r.ticker] = r.data
	}
	return out
}

func (s *Service) FetchInfo(ticker string) (map[string]any, error) {
	if info, ok := s.infoCache.Get(ticker); ok {
		return info, nil
	}

	quotes, err := s.client.BatchQuote([]string{ticker})
	if err != nil {
		return nil, err
	}

	summary, err := s.client.FetchQuoteSummary(ticker, "")
	if err != nil {
		summary = make(map[string]any)
	}

	quote := quotes[ticker]
	if quote != nil {
		for k, v := range quote {
			summary[k] = v
		}
	}

	s.infoCache.Set(ticker, summary)
	return summary, nil
}

func (s *Service) FetchPrices(tickers []string) (map[string]PriceData, error) {
	results := make(map[string]PriceData)
	if len(tickers) == 0 {
		return results, nil
	}

	quotes, err := s.client.BatchQuote(tickers)
	if err != nil {
		return results, err
	}

	for _, ticker := range tickers {
		info := quotes[ticker]
		if info == nil {
			continue
		}

		price, ok := info["regularMarketPrice"].(float64)
		if !ok {
			continue
		}

		var changePct float64
		if cp, ok := info["regularMarketChangePercent"].(float64); ok {
			changePct = cp
		} else if prev, ok := info["regularMarketPreviousClose"].(float64); ok && prev != 0 {
			changePct = ((price - prev) / prev) * 100
		}

		results[ticker] = PriceData{Price: price, ChangePct: changePct}
		s.infoCache.Set(ticker, info)
	}
	return results, nil
}

func (s *Service) FetchNames(tickers []string) map[string]string {
	s.nameMu.RLock()
	var uncached []string
	for _, t := range tickers {
		if _, ok := s.nameCache[t]; !ok {
			uncached = append(uncached, t)
		}
	}
	s.nameMu.RUnlock()

	if len(uncached) > 0 {
		quotes, err := s.client.BatchQuote(uncached)
		if err == nil {
			s.nameMu.Lock()
			for sym, info := range quotes {
				name := ""
				if n, ok := info["longName"].(string); ok && n != "" {
					name = n
				} else if n, ok := info["shortName"].(string); ok && n != "" {
					name = n
				}
				if name != "" {
					s.nameCache[sym] = name
				}
			}
			s.nameMu.Unlock()
		}
	}

	s.nameMu.RLock()
	defer s.nameMu.RUnlock()
	out := make(map[string]string)
	for _, t := range tickers {
		if name, ok := s.nameCache[t]; ok {
			out[t] = name
		}
	}
	return out
}

func (s *Service) FetchCurrencies(tickers []string) map[string]string {
	results := make(map[string]string)
	for _, ticker := range tickers {
		if info, ok := s.infoCache.Get(ticker); ok {
			if code, ok := info["currency"].(string); ok && code != "" {
				results[ticker] = code
			}
		}
	}
	return results
}

func (s *Service) SearchTickers(query string, maxResults int) ([]yahoo.SearchResult, error) {
	return s.client.Search(query, maxResults)
}

func (s *Service) ValidateTicker(ticker string) bool {
	return s.client.ValidateTicker(ticker)
}

func (s *Service) FetchNews(ticker string, maxItems int) ([]yahoo.NewsItem, error) {
	if items, ok := s.newsCache.Get(ticker); ok {
		return items, nil
	}

	items, err := s.client.FetchNews(ticker, maxItems)
	if err != nil {
		return nil, err
	}

	s.newsCache.Set(ticker, items)
	return items, nil
}
