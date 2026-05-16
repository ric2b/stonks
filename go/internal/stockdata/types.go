package stockdata

type TimeRange struct {
	Label    string
	Period   string
	Interval string
}

var TimeRanges = []TimeRange{
	{"1D", "1d", "2m"},
	{"1W", "5d", "5m"},
	{"1M", "1mo", "30m"},
	{"3M", "3mo", "1h"},
	{"6M", "6mo", "1h"},
	{"YTD", "ytd", "1h"},
	{"1Y", "1y", "1d"},
	{"5Y", "5y", "1wk"},
	{"10Y", "10y", "1wk"},
	{"ALL", "max", "1mo"},
}

var IntradayIntervals = map[string]bool{
	"2m":  true,
	"5m":  true,
	"30m": true,
	"1h":  true,
}

type HistoryKey struct {
	Ticker   string
	Period   string
	Interval string
}

type PriceData struct {
	Price     float64 `json:"price"`
	ChangePct float64 `json:"changePct"`
}
