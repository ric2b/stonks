package yahoo

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/cookiejar"
	"net/url"
	"sync"
)

var (
	quoteURL   = "https://query1.finance.yahoo.com/v7/finance/quote"
	chartURL   = "https://query2.finance.yahoo.com/v8/finance/chart"
	summaryURL = "https://query2.finance.yahoo.com/v10/finance/quoteSummary"
	searchURL  = "https://query2.finance.yahoo.com/v1/finance/search"
	newsURL    = "https://finance.yahoo.com/xhr/ncp"
	crumbURL   = "https://query1.finance.yahoo.com/v1/test/getcrumb"
	cookieURL  = "https://fc.yahoo.com"
)

type Client struct {
	mu     sync.RWMutex
	client *http.Client
	crumb  string
}

func NewClient() *Client {
	return &Client{}
}

func (c *Client) fetchFreshSession() (*http.Client, string, error) {
	jar, _ := cookiejar.New(nil)
	client := &http.Client{Jar: jar}

	req, _ := http.NewRequest("GET", cookieURL, nil)
	req.Header.Set("User-Agent", "Mozilla/5.0")
	client.Do(req) //nolint:errcheck // expected to fail, just sets cookies

	req, _ = http.NewRequest("GET", crumbURL, nil)
	req.Header.Set("User-Agent", "Mozilla/5.0")
	resp, err := client.Do(req)
	if err != nil {
		return nil, "", fmt.Errorf("fetching crumb: %w", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, "", fmt.Errorf("reading crumb: %w", err)
	}

	return client, string(body), nil
}

func (c *Client) ensureSession() (*http.Client, string, error) {
	c.mu.RLock()
	if c.client != nil && c.crumb != "" {
		client, crumb := c.client, c.crumb
		c.mu.RUnlock()
		return client, crumb, nil
	}
	c.mu.RUnlock()

	c.mu.Lock()
	defer c.mu.Unlock()

	if c.client != nil && c.crumb != "" {
		return c.client, c.crumb, nil
	}

	client, crumb, err := c.fetchFreshSession()
	if err != nil {
		return nil, "", err
	}
	c.client, c.crumb = client, crumb
	return client, crumb, nil
}

func (c *Client) resetSession() {
	c.mu.Lock()
	c.client = nil
	c.crumb = ""
	c.mu.Unlock()
}

func (c *Client) get(baseURL string, params url.Values) ([]byte, error) {
	client, crumb, err := c.ensureSession()
	if err != nil {
		return nil, err
	}
	params.Set("crumb", crumb)
	fullURL := baseURL + "?" + params.Encode()

	req, _ := http.NewRequest("GET", fullURL, nil)
	req.Header.Set("User-Agent", "Mozilla/5.0")
	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode == 401 {
		c.resetSession()
		client, crumb, err = c.fetchFreshSession()
		if err != nil {
			return nil, err
		}
		c.mu.Lock()
		c.client, c.crumb = client, crumb
		c.mu.Unlock()

		params.Set("crumb", crumb)
		fullURL = baseURL + "?" + params.Encode()
		req, _ = http.NewRequest("GET", fullURL, nil)
		req.Header.Set("User-Agent", "Mozilla/5.0")
		resp, err = client.Do(req)
		if err != nil {
			return nil, err
		}
		defer resp.Body.Close()
	}

	if resp.StatusCode != 200 {
		return nil, fmt.Errorf("HTTP %d from %s", resp.StatusCode, baseURL)
	}

	return io.ReadAll(resp.Body)
}

func (c *Client) getJSON(baseURL string, params url.Values) (map[string]any, error) {
	data, err := c.get(baseURL, params)
	if err != nil {
		return nil, err
	}
	var result map[string]any
	if err := json.Unmarshal(data, &result); err != nil {
		return nil, fmt.Errorf("parsing JSON from %s: %w", baseURL, err)
	}
	return result, nil
}

func (c *Client) post(baseURL string, params url.Values, body any) ([]byte, error) {
	client, crumb, err := c.ensureSession()
	if err != nil {
		return nil, err
	}
	params.Set("crumb", crumb)
	fullURL := baseURL + "?" + params.Encode()

	jsonBody, err := json.Marshal(body)
	if err != nil {
		return nil, err
	}

	req, _ := http.NewRequest("POST", fullURL, bytes.NewReader(jsonBody))
	req.Header.Set("User-Agent", "Mozilla/5.0")
	req.Header.Set("Content-Type", "application/json")
	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode == 401 {
		c.resetSession()
		client, crumb, err = c.fetchFreshSession()
		if err != nil {
			return nil, err
		}
		c.mu.Lock()
		c.client, c.crumb = client, crumb
		c.mu.Unlock()

		params.Set("crumb", crumb)
		fullURL = baseURL + "?" + params.Encode()
		req, _ = http.NewRequest("POST", fullURL, bytes.NewReader(jsonBody))
		req.Header.Set("User-Agent", "Mozilla/5.0")
		req.Header.Set("Content-Type", "application/json")
		resp, err = client.Do(req)
		if err != nil {
			return nil, err
		}
		defer resp.Body.Close()
	}

	if resp.StatusCode != 200 {
		return nil, fmt.Errorf("HTTP %d from %s", resp.StatusCode, baseURL)
	}

	return io.ReadAll(resp.Body)
}

func (c *Client) postJSON(baseURL string, params url.Values, body any) (map[string]any, error) {
	data, err := c.post(baseURL, params, body)
	if err != nil {
		return nil, err
	}
	var result map[string]any
	if err := json.Unmarshal(data, &result); err != nil {
		return nil, fmt.Errorf("parsing JSON from %s: %w", baseURL, err)
	}
	return result, nil
}
