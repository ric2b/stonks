package stockdata

import (
	"fmt"
	"math"
)

func FormatNumber(value any, fmtType string, prefix string, suffix string) string {
	var f float64
	switch v := value.(type) {
	case nil:
		return "--"
	case float64:
		f = v
	case float32:
		f = float64(v)
	case int:
		f = float64(v)
	case int64:
		f = float64(v)
	default:
		return "--"
	}

	if math.IsNaN(f) || math.IsInf(f, 0) {
		return "--"
	}

	switch fmtType {
	case "currency":
		return fmt.Sprintf("%s%s%s", prefix, formatWithCommas(f, 2), suffix)
	case "percent":
		return fmt.Sprintf("%.2f%%", f*100)
	case "decimal":
		return fmt.Sprintf("%.2f", f)
	case "number":
		if f >= 1_000_000_000 {
			return fmt.Sprintf("%.2fB", f/1_000_000_000)
		} else if f >= 1_000_000 {
			return fmt.Sprintf("%.1fM", f/1_000_000)
		} else if f >= 1_000 {
			return fmt.Sprintf("%.1fK", f/1_000)
		}
		return fmt.Sprintf("%.0f", f)
	case "large_number":
		if f >= 1_000_000_000_000 {
			return fmt.Sprintf("%s%.2fT%s", prefix, f/1_000_000_000_000, suffix)
		} else if f >= 1_000_000_000 {
			return fmt.Sprintf("%s%.2fB%s", prefix, f/1_000_000_000, suffix)
		} else if f >= 1_000_000 {
			return fmt.Sprintf("%s%.1fM%s", prefix, f/1_000_000, suffix)
		} else if f >= 1_000 {
			return fmt.Sprintf("%s%.1fK%s", prefix, f/1_000, suffix)
		}
		return fmt.Sprintf("%s%.0f%s", prefix, f, suffix)
	}
	return fmt.Sprintf("%v", f)
}

func formatWithCommas(f float64, decimals int) string {
	negative := f < 0
	if negative {
		f = -f
	}

	intPart := int64(f)
	fracPart := f - float64(intPart)

	intStr := fmt.Sprintf("%d", intPart)
	n := len(intStr)
	if n > 3 {
		groups := make([]byte, 0, n+(n-1)/3)
		for i, c := range intStr {
			if i > 0 && (n-i)%3 == 0 {
				groups = append(groups, ',')
			}
			groups = append(groups, byte(c))
		}
		intStr = string(groups)
	}

	frac := fmt.Sprintf("%.*f", decimals, fracPart)
	result := intStr + frac[1:] // frac is "0.XX", skip the leading 0

	if negative {
		return "-" + result
	}
	return result
}
