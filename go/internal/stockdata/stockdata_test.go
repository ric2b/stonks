package stockdata

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"stonks/internal/yahoo"
)

func setupTestService(handler http.Handler) (*Service, *httptest.Server) {
	server := httptest.NewServer(handler)
	client := yahoo.NewClient()
	client.SetTestEndpoints(server.URL)
	svc := NewService(client)
	return svc, server
}

func TestFetchHistoryCaching(t *testing.T) {
	callCount := 0
	mux := http.NewServeMux()
	mux.HandleFunc("/v8/finance/chart/AAPL", func(w http.ResponseWriter, r *http.Request) {
		callCount++
		json.NewEncoder(w).Encode(map[string]any{
			"chart": map[string]any{
				"result": []any{
					map[string]any{
						"timestamp": []any{1.0, 2.0},
						"indicators": map[string]any{
							"quote": []any{
								map[string]any{
									"open":   []any{100.0, 101.0},
									"high":   []any{102.0, 103.0},
									"low":    []any{99.0, 100.0},
									"close":  []any{101.0, 102.0},
									"volume": []any{1000.0, 2000.0},
								},
							},
						},
						"meta": map[string]any{},
					},
				},
			},
		})
	})

	svc, server := setupTestService(mux)
	defer server.Close()

	data1, err := svc.FetchHistory("AAPL", "1d", "2m")
	if err != nil {
		t.Fatal(err)
	}
	if data1 == nil {
		t.Fatal("expected data")
	}
	if len(data1.Timestamps) != 2 {
		t.Fatalf("expected 2 timestamps, got %d", len(data1.Timestamps))
	}

	// Second call should be cached
	data2, err := svc.FetchHistory("AAPL", "1d", "2m")
	if err != nil {
		t.Fatal(err)
	}
	if data2 == nil {
		t.Fatal("expected cached data")
	}
	if callCount != 1 {
		t.Errorf("expected 1 API call (cached), got %d", callCount)
	}
}

func TestIsHistoryCached(t *testing.T) {
	mux := http.NewServeMux()
	mux.HandleFunc("/v8/finance/chart/AAPL", func(w http.ResponseWriter, r *http.Request) {
		json.NewEncoder(w).Encode(map[string]any{
			"chart": map[string]any{
				"result": []any{
					map[string]any{
						"timestamp":  []any{1.0},
						"indicators": map[string]any{"quote": []any{map[string]any{"close": []any{100.0}}}},
						"meta":       map[string]any{},
					},
				},
			},
		})
	})

	svc, server := setupTestService(mux)
	defer server.Close()

	if svc.IsHistoryCached("AAPL", "1d", "2m") {
		t.Error("should not be cached before fetch")
	}

	svc.FetchHistory("AAPL", "1d", "2m")

	if !svc.IsHistoryCached("AAPL", "1d", "2m") {
		t.Error("should be cached after fetch")
	}
}

func TestFetchPrices(t *testing.T) {
	mux := http.NewServeMux()
	mux.HandleFunc("/v7/finance/quote", func(w http.ResponseWriter, r *http.Request) {
		json.NewEncoder(w).Encode(map[string]any{
			"quoteResponse": map[string]any{
				"result": []any{
					map[string]any{
						"symbol":                     "AAPL",
						"regularMarketPrice":         150.0,
						"regularMarketChangePercent": 2.5,
					},
					map[string]any{
						"symbol":                       "MSFT",
						"regularMarketPrice":           300.0,
						"regularMarketPreviousClose":   290.0,
					},
				},
			},
		})
	})

	svc, server := setupTestService(mux)
	defer server.Close()

	prices, err := svc.FetchPrices([]string{"AAPL", "MSFT"})
	if err != nil {
		t.Fatal(err)
	}
	if prices["AAPL"].Price != 150.0 {
		t.Errorf("AAPL price: got %f, want 150", prices["AAPL"].Price)
	}
	if prices["AAPL"].ChangePct != 2.5 {
		t.Errorf("AAPL change: got %f, want 2.5", prices["AAPL"].ChangePct)
	}
	// MSFT should calculate change from previous close
	expectedChange := ((300.0 - 290.0) / 290.0) * 100
	if prices["MSFT"].ChangePct < expectedChange-0.01 || prices["MSFT"].ChangePct > expectedChange+0.01 {
		t.Errorf("MSFT change: got %f, want ~%f", prices["MSFT"].ChangePct, expectedChange)
	}
}

func TestFetchNames(t *testing.T) {
	mux := http.NewServeMux()
	mux.HandleFunc("/v7/finance/quote", func(w http.ResponseWriter, r *http.Request) {
		json.NewEncoder(w).Encode(map[string]any{
			"quoteResponse": map[string]any{
				"result": []any{
					map[string]any{"symbol": "AAPL", "longName": "Apple Inc."},
					map[string]any{"symbol": "MSFT", "shortName": "Microsoft Corp"},
				},
			},
		})
	})

	svc, server := setupTestService(mux)
	defer server.Close()

	names := svc.FetchNames([]string{"AAPL", "MSFT"})
	if names["AAPL"] != "Apple Inc." {
		t.Errorf("AAPL: got %q", names["AAPL"])
	}
	if names["MSFT"] != "Microsoft Corp" {
		t.Errorf("MSFT: got %q", names["MSFT"])
	}
}

func TestBatchFetchHistory(t *testing.T) {
	mux := http.NewServeMux()
	handler := func(w http.ResponseWriter, r *http.Request) {
		json.NewEncoder(w).Encode(map[string]any{
			"chart": map[string]any{
				"result": []any{
					map[string]any{
						"timestamp":  []any{1.0, 2.0},
						"indicators": map[string]any{"quote": []any{map[string]any{"close": []any{100.0, 101.0}}}},
						"meta":       map[string]any{},
					},
				},
			},
		})
	}
	mux.HandleFunc("/v8/finance/chart/AAPL", handler)
	mux.HandleFunc("/v8/finance/chart/MSFT", handler)
	mux.HandleFunc("/v8/finance/chart/GOOGL", handler)

	svc, server := setupTestService(mux)
	defer server.Close()

	results := svc.BatchFetchHistory([]string{"AAPL", "MSFT", "GOOGL"}, "1d", "2m")
	if len(results) != 3 {
		t.Errorf("expected 3 results, got %d", len(results))
	}
}

func TestTimeRangesOrder(t *testing.T) {
	expected := []string{"1D", "1W", "1M", "3M", "6M", "YTD", "1Y", "5Y", "10Y", "ALL"}
	if len(TimeRanges) != len(expected) {
		t.Fatalf("expected %d ranges, got %d", len(expected), len(TimeRanges))
	}
	for i, tr := range TimeRanges {
		if tr.Label != expected[i] {
			t.Errorf("position %d: got %s, want %s", i, tr.Label, expected[i])
		}
	}
}
