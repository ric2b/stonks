package yahoo

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"
)

func newTestClient(handler http.Handler) (*Client, *httptest.Server) {
	server := httptest.NewServer(handler)
	c := NewClient()
	c.client = server.Client()
	c.crumb = "test-crumb"
	return c, server
}

func TestBatchQuote(t *testing.T) {
	mux := http.NewServeMux()
	mux.HandleFunc("/v7/finance/quote", func(w http.ResponseWriter, r *http.Request) {
		json.NewEncoder(w).Encode(map[string]any{
			"quoteResponse": map[string]any{
				"result": []any{
					map[string]any{
						"symbol":               "AAPL",
						"regularMarketPrice":    150.0,
						"regularMarketDayHigh":  152.0,
						"regularMarketDayLow":   148.0,
						"regularMarketVolume":   1000000.0,
						"averageDailyVolume3Month": 2000000.0,
					},
					map[string]any{
						"symbol":            "MSFT",
						"regularMarketPrice": 300.0,
					},
				},
			},
		})
	})

	c, server := newTestClient(mux)
	defer server.Close()

	// Override URLs to point to test server
	origQuoteURL := quoteURL
	defer func() { setQuoteURL(origQuoteURL) }()
	setQuoteURL(server.URL + "/v7/finance/quote")

	results, err := c.BatchQuote([]string{"AAPL", "MSFT"})
	if err != nil {
		t.Fatal(err)
	}
	if len(results) != 2 {
		t.Fatalf("expected 2 results, got %d", len(results))
	}
	if results["AAPL"]["regularMarketPrice"] != 150.0 {
		t.Error("wrong AAPL price")
	}
	// Check field normalization
	if results["AAPL"]["dayHigh"] != 152.0 {
		t.Error("dayHigh not normalized")
	}
	if results["AAPL"]["dayLow"] != 148.0 {
		t.Error("dayLow not normalized")
	}
	if results["AAPL"]["volume"] != 1000000.0 {
		t.Error("volume not normalized")
	}
	if results["AAPL"]["averageVolume"] != 2000000.0 {
		t.Error("averageVolume not normalized")
	}
}

func TestBatchQuoteEmpty(t *testing.T) {
	c := NewClient()
	results, err := c.BatchQuote([]string{})
	if err != nil {
		t.Fatal(err)
	}
	if len(results) != 0 {
		t.Fatal("expected empty results")
	}
}

func TestFetchChart(t *testing.T) {
	mux := http.NewServeMux()
	mux.HandleFunc("/v8/finance/chart/AAPL", func(w http.ResponseWriter, r *http.Request) {
		json.NewEncoder(w).Encode(map[string]any{
			"chart": map[string]any{
				"result": []any{
					map[string]any{
						"timestamp": []any{1700000000.0, 1700000060.0, 1700000120.0},
						"indicators": map[string]any{
							"quote": []any{
								map[string]any{
									"open":   []any{150.0, 151.0, 152.0},
									"high":   []any{151.0, 152.0, 153.0},
									"low":    []any{149.0, 150.0, 151.0},
									"close":  []any{150.5, 151.5, 152.5},
									"volume": []any{1000.0, 2000.0, 3000.0},
								},
							},
						},
						"meta": map[string]any{
							"currency": "USD",
						},
					},
				},
			},
		})
	})

	c, server := newTestClient(mux)
	defer server.Close()

	origChartURL := chartURL
	defer func() { setChartURL(origChartURL) }()
	setChartURL(server.URL + "/v8/finance/chart")

	chart, err := c.FetchChart("AAPL", "1d", "2m")
	if err != nil {
		t.Fatal(err)
	}
	if chart == nil {
		t.Fatal("expected chart data")
	}
	if len(chart.Timestamps) != 3 {
		t.Fatalf("expected 3 timestamps, got %d", len(chart.Timestamps))
	}
	if chart.Timestamps[0] != 1700000000 {
		t.Error("wrong first timestamp")
	}
	if len(chart.Close) != 3 || *chart.Close[0] != 150.5 {
		t.Error("wrong close data")
	}
	if chart.Meta["currency"] != "USD" {
		t.Error("missing meta currency")
	}
}

func TestFetchChartNoData(t *testing.T) {
	mux := http.NewServeMux()
	mux.HandleFunc("/v8/finance/chart/FAKE", func(w http.ResponseWriter, r *http.Request) {
		json.NewEncoder(w).Encode(map[string]any{
			"chart": map[string]any{
				"result": nil,
			},
		})
	})

	c, server := newTestClient(mux)
	defer server.Close()

	origChartURL := chartURL
	defer func() { setChartURL(origChartURL) }()
	setChartURL(server.URL + "/v8/finance/chart")

	chart, err := c.FetchChart("FAKE", "1d", "2m")
	if err != nil {
		t.Fatal(err)
	}
	if chart != nil {
		t.Error("expected nil for no data")
	}
}

func TestValidateTicker(t *testing.T) {
	mux := http.NewServeMux()
	mux.HandleFunc("/v8/finance/chart/AAPL", func(w http.ResponseWriter, r *http.Request) {
		json.NewEncoder(w).Encode(map[string]any{
			"chart": map[string]any{
				"result": []any{map[string]any{"timestamp": []any{1.0}}},
			},
		})
	})
	mux.HandleFunc("/v8/finance/chart/FAKE", func(w http.ResponseWriter, r *http.Request) {
		json.NewEncoder(w).Encode(map[string]any{
			"chart": map[string]any{"result": nil},
		})
	})

	c, server := newTestClient(mux)
	defer server.Close()

	origChartURL := chartURL
	defer func() { setChartURL(origChartURL) }()
	setChartURL(server.URL + "/v8/finance/chart")

	if !c.ValidateTicker("AAPL") {
		t.Error("AAPL should be valid")
	}
	if c.ValidateTicker("FAKE") {
		t.Error("FAKE should be invalid")
	}
}

func TestSearch(t *testing.T) {
	mux := http.NewServeMux()
	mux.HandleFunc("/v1/finance/search", func(w http.ResponseWriter, r *http.Request) {
		json.NewEncoder(w).Encode(map[string]any{
			"quotes": []any{
				map[string]any{
					"symbol":    "AAPL",
					"shortname": "Apple Inc.",
					"longname":  "Apple Inc.",
					"exchDisp":  "NASDAQ",
				},
				map[string]any{
					"symbol":    "AAPLX",
					"shortname": "Apple Fund",
					"exchDisp":  "FUND",
				},
			},
		})
	})

	c, server := newTestClient(mux)
	defer server.Close()

	origSearchURL := searchURL
	defer func() { setSearchURL(origSearchURL) }()
	setSearchURL(server.URL + "/v1/finance/search")

	results, err := c.Search("AAPL", 5)
	if err != nil {
		t.Fatal(err)
	}
	if len(results) != 2 {
		t.Fatalf("expected 2 results, got %d", len(results))
	}
	if results[0].Symbol != "AAPL" {
		t.Error("wrong symbol")
	}
	if results[0].Name != "Apple Inc." {
		t.Error("wrong name")
	}
	if results[0].Exchange != "NASDAQ" {
		t.Error("wrong exchange")
	}
}

func TestQuoteSummary(t *testing.T) {
	mux := http.NewServeMux()
	mux.HandleFunc("/v10/finance/quoteSummary/AAPL", func(w http.ResponseWriter, r *http.Request) {
		json.NewEncoder(w).Encode(map[string]any{
			"quoteSummary": map[string]any{
				"result": []any{
					map[string]any{
						"price": map[string]any{
							"regularMarketPrice": map[string]any{"raw": 150.0},
							"marketState":        "REGULAR",
						},
						"summaryDetail": map[string]any{
							"trailingPE": map[string]any{"raw": 25.5},
							"volume":     map[string]any{"raw": 1000000.0},
						},
					},
				},
			},
		})
	})

	c, server := newTestClient(mux)
	defer server.Close()

	origSummaryURL := summaryURL
	defer func() { setSummaryURL(origSummaryURL) }()
	setSummaryURL(server.URL + "/v10/finance/quoteSummary")

	info, err := c.FetchQuoteSummary("AAPL", "price,summaryDetail")
	if err != nil {
		t.Fatal(err)
	}
	if info["regularMarketPrice"] != 150.0 {
		t.Errorf("wrong price: %v", info["regularMarketPrice"])
	}
	if info["marketState"] != "REGULAR" {
		t.Errorf("wrong market state: %v", info["marketState"])
	}
	if info["trailingPE"] != 25.5 {
		t.Errorf("wrong PE: %v", info["trailingPE"])
	}
}

func TestRetryOn401(t *testing.T) {
	callCount := 0
	mux := http.NewServeMux()
	mux.HandleFunc("/v1/test/getcrumb", func(w http.ResponseWriter, r *http.Request) {
		fmt.Fprint(w, "new-crumb")
	})
	mux.HandleFunc("/v7/finance/quote", func(w http.ResponseWriter, r *http.Request) {
		callCount++
		if callCount == 1 {
			w.WriteHeader(401)
			return
		}
		json.NewEncoder(w).Encode(map[string]any{
			"quoteResponse": map[string]any{
				"result": []any{
					map[string]any{"symbol": "AAPL", "regularMarketPrice": 150.0},
				},
			},
		})
	})

	server := httptest.NewServer(mux)
	defer server.Close()

	c := NewClient()
	c.client = server.Client()
	c.crumb = "old-crumb"

	origQuoteURL := quoteURL
	defer func() { setQuoteURL(origQuoteURL) }()
	setQuoteURL(server.URL + "/v7/finance/quote")

	// Override crumb URL for retry
	origCrumbURL := crumbURL
	origCookieURL := cookieURL
	defer func() {
		setCrumbURL(origCrumbURL)
		setCookieURL(origCookieURL)
	}()
	setCrumbURL(server.URL + "/v1/test/getcrumb")
	setCookieURL(server.URL + "/fc")

	results, err := c.BatchQuote([]string{"AAPL"})
	if err != nil {
		t.Fatal(err)
	}
	if callCount != 2 {
		t.Errorf("expected 2 calls (first 401, then success), got %d", callCount)
	}
	if len(results) != 1 {
		t.Fatal("expected 1 result after retry")
	}
}
