package yahoo

import (
	"fmt"
	"net/url"
)

func (c *Client) FetchChart(ticker string, rangeStr string, interval string) (*ChartData, error) {
	params := url.Values{
		"range":    {rangeStr},
		"interval": {interval},
	}
	data, err := c.getJSON(fmt.Sprintf("%s/%s", chartURL, ticker), params)
	if err != nil {
		return nil, err
	}

	chart, _ := data["chart"].(map[string]any)
	results, _ := chart["result"].([]any)
	if len(results) == 0 {
		return nil, nil
	}

	result, _ := results[0].(map[string]any)
	rawTimestamps, _ := result["timestamp"].([]any)
	if len(rawTimestamps) == 0 {
		return nil, nil
	}

	timestamps := make([]int64, len(rawTimestamps))
	for i, t := range rawTimestamps {
		timestamps[i] = int64(t.(float64))
	}

	indicators, _ := result["indicators"].(map[string]any)
	quoteArr, _ := indicators["quote"].([]any)
	if len(quoteArr) == 0 {
		return nil, fmt.Errorf("no quote data for %s", ticker)
	}
	quote, _ := quoteArr[0].(map[string]any)

	meta, _ := result["meta"].(map[string]any)
	if meta == nil {
		meta = make(map[string]any)
	}

	return &ChartData{
		Timestamps: timestamps,
		Open:       toFloatSlice(quote["open"]),
		High:       toFloatSlice(quote["high"]),
		Low:        toFloatSlice(quote["low"]),
		Close:      toFloatSlice(quote["close"]),
		Volume:     toFloatSlice(quote["volume"]),
		Meta:       meta,
	}, nil
}

func (c *Client) ValidateTicker(ticker string) bool {
	params := url.Values{
		"range":    {"1d"},
		"interval": {"1d"},
	}
	data, err := c.getJSON(fmt.Sprintf("%s/%s", chartURL, ticker), params)
	if err != nil {
		return false
	}
	chart, _ := data["chart"].(map[string]any)
	results, _ := chart["result"].([]any)
	return len(results) > 0
}

func toFloatSlice(v any) []*float64 {
	arr, ok := v.([]any)
	if !ok {
		return nil
	}
	out := make([]*float64, len(arr))
	for i, val := range arr {
		if f, ok := val.(float64); ok {
			out[i] = &f
		}
	}
	return out
}
