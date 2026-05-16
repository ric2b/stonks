package yahoo

import (
	"net/url"
	"strings"
)

var quoteFieldMap = map[string]string{
	"regularMarketDayHigh":     "dayHigh",
	"regularMarketDayLow":      "dayLow",
	"regularMarketVolume":      "volume",
	"averageDailyVolume3Month": "averageVolume",
	"epsTrailingTwelveMonths":  "trailingEps",
}

func normalizeQuote(q map[string]any) map[string]any {
	out := make(map[string]any, len(q))
	for k, v := range q {
		if mapped, ok := quoteFieldMap[k]; ok {
			out[mapped] = v
		}
		out[k] = v
	}
	return out
}

func (c *Client) BatchQuote(tickers []string) (map[string]map[string]any, error) {
	if len(tickers) == 0 {
		return map[string]map[string]any{}, nil
	}

	params := url.Values{"symbols": {strings.Join(tickers, ",")}}
	data, err := c.getJSON(quoteURL, params)
	if err != nil {
		return nil, err
	}

	results := make(map[string]map[string]any)
	resp, _ := data["quoteResponse"].(map[string]any)
	quotes, _ := resp["result"].([]any)
	for _, raw := range quotes {
		q, ok := raw.(map[string]any)
		if !ok {
			continue
		}
		sym, _ := q["symbol"].(string)
		if sym == "" {
			continue
		}
		results[sym] = normalizeQuote(q)
	}
	return results, nil
}
