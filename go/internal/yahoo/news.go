package yahoo

import "net/url"

func (c *Client) FetchNews(ticker string, maxItems int) ([]NewsItem, error) {
	if maxItems <= 0 {
		maxItems = 8
	}

	params := url.Values{
		"queryRef":   {"latestNews"},
		"serviceKey": {"ncp_fin"},
	}
	body := map[string]any{
		"serviceConfig": map[string]any{
			"snippetCount": maxItems,
			"s":            []string{ticker},
		},
	}

	data, err := c.postJSON(newsURL, params, body)
	if err != nil {
		return nil, err
	}

	dataObj, _ := data["data"].(map[string]any)
	tickerStream, _ := dataObj["tickerStream"].(map[string]any)
	stream, _ := tickerStream["stream"].([]any)

	var items []NewsItem
	for _, raw := range stream {
		article, ok := raw.(map[string]any)
		if !ok {
			continue
		}
		if ads, ok := article["ad"].([]any); ok && len(ads) > 0 {
			continue
		}

		content, _ := article["content"].(map[string]any)
		if content == nil {
			content = article
		}

		title, _ := content["title"].(string)

		var providerName string
		if provider, ok := content["provider"].(map[string]any); ok {
			providerName, _ = provider["displayName"].(string)
		}

		var pubDate int64
		if pd, ok := content["pubDate"].(string); ok {
			_ = pd // stored as string, frontend will parse
		}
		if pd, ok := content["pubDate"].(float64); ok {
			pubDate = int64(pd)
		}

		articleURL := ""
		if clickThrough, ok := content["clickThroughUrl"].(map[string]any); ok {
			articleURL, _ = clickThrough["url"].(string)
		}
		if articleURL == "" {
			if canonical, ok := content["canonicalUrl"].(map[string]any); ok {
				articleURL, _ = canonical["url"].(string)
			}
		}
		if articleURL == "" {
			articleURL, _ = content["url"].(string)
		}

		if title != "" {
			items = append(items, NewsItem{
				Title:    title,
				URL:      articleURL,
				Provider: providerName,
				PubDate:  pubDate,
			})
		}
	}
	return items, nil
}
