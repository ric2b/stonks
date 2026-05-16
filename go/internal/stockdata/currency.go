package stockdata

var CurrencySymbols = map[string]string{
	"USD": "$",
	"EUR": "€",
	"GBP": "£",
	"JPY": "¥",
	"CNY": "¥",
	"CAD": "CA$",
	"AUD": "A$",
	"NZD": "NZ$",
	"HKD": "HK$",
	"SGD": "S$",
	"TWD": "NT$",
	"INR": "₹",
	"KRW": "₩",
	"BRL": "R$",
	"ILS": "₪",
	"MXN": "MX$",
	"THB": "฿",
	"TRY": "₺",
	"PHP": "₱",
	"RUB": "₽",
	"SEK": "kr",
	"NOK": "kr",
	"DKK": "kr",
	"CZK": "Kč",
	"PLN": "zł",
	"HUF": "Ft",
	"GBp": "p",
}

var suffixCurrencies = map[string]bool{
	"EUR": true,
	"SEK": true,
	"NOK": true,
	"DKK": true,
	"CZK": true,
	"PLN": true,
	"HUF": true,
	"GBp": true,
}

func CurrencyFormat(code string) (prefix string, suffix string) {
	symbol, ok := CurrencySymbols[code]
	if !ok {
		return "", ""
	}
	if suffixCurrencies[code] {
		return "", symbol
	}
	return symbol, ""
}
