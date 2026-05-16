package yahoo

import (
	"fmt"
	"net/url"
)

func (c *Client) FetchQuoteSummary(ticker string, modules string) (map[string]any, error) {
	if modules == "" {
		modules = "price,summaryDetail,defaultKeyStatistics"
	}

	params := url.Values{"modules": {modules}}
	data, err := c.getJSON(fmt.Sprintf("%s/%s", summaryURL, ticker), params)
	if err != nil {
		return nil, err
	}

	qs, _ := data["quoteSummary"].(map[string]any)
	results, _ := qs["result"].([]any)
	if len(results) == 0 {
		return map[string]any{}, nil
	}

	first, _ := results[0].(map[string]any)
	merged := make(map[string]any)
	for _, moduleData := range first {
		mod, ok := moduleData.(map[string]any)
		if !ok {
			continue
		}
		for k, v := range mod {
			switch val := v.(type) {
			case map[string]any:
				if raw, ok := val["raw"]; ok {
					merged[k] = raw
				}
			case []any:
				merged[k] = val
			default:
				merged[k] = val
			}
		}
	}
	return merged, nil
}
