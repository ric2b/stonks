package yahoo

import (
	"fmt"
	"net/url"
)

func (c *Client) Search(query string, maxResults int) ([]SearchResult, error) {
	if maxResults <= 0 {
		maxResults = 5
	}

	params := url.Values{
		"q":           {query},
		"quotesCount": {fmt.Sprintf("%d", maxResults)},
	}
	data, err := c.getJSON(searchURL, params)
	if err != nil {
		return nil, err
	}

	quotes, _ := data["quotes"].([]any)
	results := make([]SearchResult, 0, len(quotes))
	for _, raw := range quotes {
		q, ok := raw.(map[string]any)
		if !ok {
			continue
		}
		symbol, _ := q["symbol"].(string)
		shortname, _ := q["shortname"].(string)
		longname, _ := q["longname"].(string)
		exchDisp, _ := q["exchDisp"].(string)

		name := longname
		if name == "" {
			name = shortname
		}

		results = append(results, SearchResult{
			Symbol:   symbol,
			Name:     name,
			Exchange: exchDisp,
		})
		if len(results) >= maxResults {
			break
		}
	}
	return results, nil
}
