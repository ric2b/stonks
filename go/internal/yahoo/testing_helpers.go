package yahoo

import "net/http"

func setQuoteURL(u string)   { quoteURL = u }
func setChartURL(u string)   { chartURL = u }
func setSummaryURL(u string) { summaryURL = u }
func setSearchURL(u string)  { searchURL = u }
func setNewsURL(u string)    { newsURL = u }
func setCrumbURL(u string)   { crumbURL = u }
func setCookieURL(u string)  { cookieURL = u }

// SetTestEndpoints configures all endpoints to use a test server base URL.
// It also sets up the client with a working HTTP client and crumb so no
// real session fetch is needed.
func (c *Client) SetTestEndpoints(baseURL string) {
	quoteURL = baseURL + "/v7/finance/quote"
	chartURL = baseURL + "/v8/finance/chart"
	summaryURL = baseURL + "/v10/finance/quoteSummary"
	searchURL = baseURL + "/v1/finance/search"
	newsURL = baseURL + "/xhr/ncp"
	crumbURL = baseURL + "/v1/test/getcrumb"
	cookieURL = baseURL + "/fc"
	c.client = &http.Client{}
	c.crumb = "test-crumb"
}
