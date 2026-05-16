package yahoo

type ChartData struct {
	Timestamps []int64    `json:"timestamps"`
	Open       []*float64 `json:"open"`
	High       []*float64 `json:"high"`
	Low        []*float64 `json:"low"`
	Close      []*float64 `json:"close"`
	Volume     []*float64 `json:"volume"`
	Meta       map[string]any `json:"meta"`
}

type SearchResult struct {
	Symbol   string `json:"symbol"`
	Name     string `json:"name"`
	Exchange string `json:"exchange"`
}

type NewsItem struct {
	Title    string `json:"title"`
	URL      string `json:"url"`
	Provider string `json:"provider"`
	PubDate  int64  `json:"pubDate"`
}
