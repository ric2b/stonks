package stockdata

import "testing"

func TestNilReturnsPlaceholder(t *testing.T) {
	if FormatNumber(nil, "currency", "", "") != "--" {
		t.Error("nil currency should return --")
	}
	if FormatNumber(nil, "number", "", "") != "--" {
		t.Error("nil number should return --")
	}
}

func TestCurrency(t *testing.T) {
	tests := []struct {
		value    any
		prefix   string
		suffix   string
		expected string
	}{
		{1234.5, "", "", "1,234.50"},
		{0.0, "", "", "0.00"},
		{1234.5, "$", "", "$1,234.50"},
		{0.0, "£", "", "£0.00"},
		{1234.5, "", "€", "1,234.50€"},
		{0.0, "", "kr", "0.00kr"},
	}
	for _, tt := range tests {
		got := FormatNumber(tt.value, "currency", tt.prefix, tt.suffix)
		if got != tt.expected {
			t.Errorf("FormatNumber(%v, currency, %q, %q) = %q, want %q",
				tt.value, tt.prefix, tt.suffix, got, tt.expected)
		}
	}
}

func TestPercent(t *testing.T) {
	if got := FormatNumber(0.05, "percent", "", ""); got != "5.00%" {
		t.Errorf("got %q, want 5.00%%", got)
	}
	if got := FormatNumber(0.0, "percent", "", ""); got != "0.00%" {
		t.Errorf("got %q, want 0.00%%", got)
	}
}

func TestDecimal(t *testing.T) {
	if got := FormatNumber(32.567, "decimal", "", ""); got != "32.57" {
		t.Errorf("got %q, want 32.57", got)
	}
}

func TestNumberRaw(t *testing.T) {
	if got := FormatNumber(999.0, "number", "", ""); got != "999" {
		t.Errorf("got %q, want 999", got)
	}
}

func TestNumberThousands(t *testing.T) {
	if got := FormatNumber(1500.0, "number", "", ""); got != "1.5K" {
		t.Errorf("got %q, want 1.5K", got)
	}
}

func TestNumberMillions(t *testing.T) {
	if got := FormatNumber(2500000.0, "number", "", ""); got != "2.5M" {
		t.Errorf("got %q, want 2.5M", got)
	}
}

func TestNumberBillions(t *testing.T) {
	if got := FormatNumber(1800000000.0, "number", "", ""); got != "1.80B" {
		t.Errorf("got %q, want 1.80B", got)
	}
}

func TestLargeNumberTrillions(t *testing.T) {
	if got := FormatNumber(3100000000000.0, "large_number", "", ""); got != "3.10T" {
		t.Errorf("got %q, want 3.10T", got)
	}
}

func TestLargeNumberWithPrefix(t *testing.T) {
	if got := FormatNumber(3100000000000.0, "large_number", "$", ""); got != "$3.10T" {
		t.Errorf("got %q, want $3.10T", got)
	}
	if got := FormatNumber(2500000000.0, "large_number", "£", ""); got != "£2.50B" {
		t.Errorf("got %q, want £2.50B", got)
	}
}

func TestLargeNumberWithSuffix(t *testing.T) {
	if got := FormatNumber(3100000000000.0, "large_number", "", "€"); got != "3.10T€" {
		t.Errorf("got %q, want 3.10T€", got)
	}
	if got := FormatNumber(2500000.0, "large_number", "", "€"); got != "2.5M€" {
		t.Errorf("got %q, want 2.5M€", got)
	}
}

func TestLargeNumberBillions(t *testing.T) {
	if got := FormatNumber(2500000000.0, "large_number", "", ""); got != "2.50B" {
		t.Errorf("got %q, want 2.50B", got)
	}
}

func TestIntegerInputAccepted(t *testing.T) {
	types := []string{"currency", "percent", "decimal", "number", "large_number"}
	for _, ft := range types {
		got := FormatNumber(100, ft, "", "")
		if got == "--" {
			t.Errorf("int input with type %q returned placeholder", ft)
		}
	}
}

func TestCurrencyFormatPrefix(t *testing.T) {
	prefix, suffix := CurrencyFormat("USD")
	if prefix != "$" || suffix != "" {
		t.Errorf("USD: got (%q, %q), want ($, \"\")", prefix, suffix)
	}
}

func TestCurrencyFormatSuffix(t *testing.T) {
	prefix, suffix := CurrencyFormat("EUR")
	if prefix != "" || suffix != "€" {
		t.Errorf("EUR: got (%q, %q), want (\"\", €)", prefix, suffix)
	}
}

func TestCurrencyFormatUnknown(t *testing.T) {
	prefix, suffix := CurrencyFormat("XYZ")
	if prefix != "" || suffix != "" {
		t.Errorf("XYZ: got (%q, %q), want (\"\", \"\")", prefix, suffix)
	}
}
