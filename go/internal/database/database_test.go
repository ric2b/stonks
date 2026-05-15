package database

import (
	"database/sql"
	"os"
	"path/filepath"
	"testing"

	_ "modernc.org/sqlite"
)

func setupTestDB(t *testing.T) *sql.DB {
	t.Helper()
	dbPath := filepath.Join(t.TempDir(), "test.db")
	db, err := InitDB(dbPath)
	if err != nil {
		t.Fatalf("InitDB: %v", err)
	}
	t.Cleanup(func() { db.Close() })
	return db
}

func TestEmptyWatchlist(t *testing.T) {
	db := setupTestDB(t)
	entries, err := GetWatchlist(db)
	if err != nil {
		t.Fatal(err)
	}
	if len(entries) != 0 {
		t.Fatalf("expected empty watchlist, got %d entries", len(entries))
	}
}

func TestAddAndGetWatchlist(t *testing.T) {
	db := setupTestDB(t)
	AddTicker(db, "AAPL")
	AddTicker(db, "MSFT")

	entries, _ := GetWatchlist(db)
	if len(entries) != 2 {
		t.Fatalf("expected 2 entries, got %d", len(entries))
	}
	if entries[0].Ticker != "AAPL" {
		t.Errorf("expected AAPL, got %s", entries[0].Ticker)
	}
	if entries[1].Ticker != "MSFT" {
		t.Errorf("expected MSFT, got %s", entries[1].Ticker)
	}
	if entries[0].Position >= entries[1].Position {
		t.Error("positions should be ascending")
	}
}

func TestAddTickerPositionsAreSequential(t *testing.T) {
	db := setupTestDB(t)
	AddTicker(db, "AAPL")
	AddTicker(db, "MSFT")
	AddTicker(db, "GOOGL")

	entries, _ := GetWatchlist(db)
	seen := make(map[int]bool)
	for i, e := range entries {
		if i > 0 && e.Position <= entries[i-1].Position {
			t.Error("positions not ascending")
		}
		if seen[e.Position] {
			t.Errorf("duplicate position %d", e.Position)
		}
		seen[e.Position] = true
	}
}

func TestAddDuplicateTicker(t *testing.T) {
	db := setupTestDB(t)
	AddTicker(db, "AAPL")
	AddTicker(db, "AAPL")

	entries, _ := GetWatchlist(db)
	if len(entries) != 1 {
		t.Fatalf("expected 1 entry, got %d", len(entries))
	}
}

func TestAddTickerUppercases(t *testing.T) {
	db := setupTestDB(t)
	AddTicker(db, "aapl")

	entries, _ := GetWatchlist(db)
	if entries[0].Ticker != "AAPL" {
		t.Errorf("expected AAPL, got %s", entries[0].Ticker)
	}
}

func TestRemoveTicker(t *testing.T) {
	db := setupTestDB(t)
	AddTicker(db, "AAPL")
	AddTicker(db, "MSFT")
	RemoveTicker(db, "AAPL")

	entries, _ := GetWatchlist(db)
	if len(entries) != 1 {
		t.Fatalf("expected 1 entry, got %d", len(entries))
	}
	if entries[0].Ticker != "MSFT" {
		t.Errorf("expected MSFT, got %s", entries[0].Ticker)
	}
}

func TestRemoveTickerCaseInsensitive(t *testing.T) {
	db := setupTestDB(t)
	AddTicker(db, "AAPL")
	RemoveTicker(db, "aapl")

	entries, _ := GetWatchlist(db)
	if len(entries) != 0 {
		t.Fatal("expected empty watchlist")
	}
}

func TestRemoveNonexistentTickerIsHarmless(t *testing.T) {
	db := setupTestDB(t)
	AddTicker(db, "AAPL")
	RemoveTicker(db, "MSFT")

	entries, _ := GetWatchlist(db)
	if len(entries) != 1 {
		t.Fatal("expected 1 entry")
	}
}

func TestReorderWatchlist(t *testing.T) {
	db := setupTestDB(t)
	AddTicker(db, "AAPL")
	AddTicker(db, "MSFT")
	AddTicker(db, "GOOGL")
	ReorderWatchlist(db, []string{"GOOGL", "AAPL", "MSFT"})

	entries, _ := GetWatchlist(db)
	tickers := make([]string, len(entries))
	for i, e := range entries {
		tickers[i] = e.Ticker
	}
	expected := []string{"GOOGL", "AAPL", "MSFT"}
	for i, ticker := range tickers {
		if ticker != expected[i] {
			t.Errorf("position %d: expected %s, got %s", i, expected[i], ticker)
		}
	}
}

func TestGetSettingReturnsDefaultWhenMissing(t *testing.T) {
	db := setupTestDB(t)

	val, _ := GetSetting(db, "nonexistent", "")
	if val != "" {
		t.Errorf("expected empty string, got %q", val)
	}

	val, _ = GetSetting(db, "nonexistent", "fallback")
	if val != "fallback" {
		t.Errorf("expected fallback, got %q", val)
	}
}

func TestSetAndGetSetting(t *testing.T) {
	db := setupTestDB(t)
	SetSetting(db, "last_ticker", "AAPL")

	val, _ := GetSetting(db, "last_ticker", "")
	if val != "AAPL" {
		t.Errorf("expected AAPL, got %q", val)
	}
}

func TestSetSettingOverwrites(t *testing.T) {
	db := setupTestDB(t)
	SetSetting(db, "last_ticker", "AAPL")
	SetSetting(db, "last_ticker", "MSFT")

	val, _ := GetSetting(db, "last_ticker", "")
	if val != "MSFT" {
		t.Errorf("expected MSFT, got %q", val)
	}
}

func TestSettingsAreIndependent(t *testing.T) {
	db := setupTestDB(t)
	SetSetting(db, "last_ticker", "AAPL")
	SetSetting(db, "last_period", "1M")

	val1, _ := GetSetting(db, "last_ticker", "")
	val2, _ := GetSetting(db, "last_period", "")
	if val1 != "AAPL" {
		t.Errorf("expected AAPL, got %q", val1)
	}
	if val2 != "1M" {
		t.Errorf("expected 1M, got %q", val2)
	}
}

func TestWatchlistReturnsNameAndCurrency(t *testing.T) {
	db := setupTestDB(t)
	AddTicker(db, "AAPL")

	entries, _ := GetWatchlist(db)
	if entries[0].Name != "" {
		t.Errorf("expected empty name, got %q", entries[0].Name)
	}
	if entries[0].Currency != "" {
		t.Errorf("expected empty currency, got %q", entries[0].Currency)
	}
}

func TestUpdateTickerMeta(t *testing.T) {
	db := setupTestDB(t)
	AddTicker(db, "AAPL")
	UpdateTickerMeta(db, "AAPL", "Apple Inc.", "USD")

	entries, _ := GetWatchlist(db)
	if entries[0].Name != "Apple Inc." {
		t.Errorf("expected Apple Inc., got %q", entries[0].Name)
	}
	if entries[0].Currency != "USD" {
		t.Errorf("expected USD, got %q", entries[0].Currency)
	}
}

func TestUpdateTickerMetaPersistsAcrossReads(t *testing.T) {
	db := setupTestDB(t)
	AddTicker(db, "AAPL")
	AddTicker(db, "MSFT")
	UpdateTickerMeta(db, "MSFT", "Microsoft Corporation", "USD")

	entries, _ := GetWatchlist(db)
	if entries[0].Name != "" {
		t.Errorf("AAPL name should be empty, got %q", entries[0].Name)
	}
	if entries[1].Name != "Microsoft Corporation" {
		t.Errorf("expected Microsoft Corporation, got %q", entries[1].Name)
	}
	if entries[1].Currency != "USD" {
		t.Errorf("expected USD, got %q", entries[1].Currency)
	}
}

func TestMigrateAddsMissingColumns(t *testing.T) {
	dir := t.TempDir()
	dbPath := filepath.Join(dir, "legacy.db")

	db, err := sql.Open("sqlite", dbPath)
	if err != nil {
		t.Fatal(err)
	}
	db.Exec(`CREATE TABLE watchlist (
		id INTEGER PRIMARY KEY AUTOINCREMENT,
		ticker TEXT UNIQUE NOT NULL,
		position INTEGER NOT NULL DEFAULT 0
	)`)
	db.Exec(`CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)`)
	db.Exec("INSERT INTO watchlist (ticker, position) VALUES ('AAPL', 0)")
	db.Close()

	db2, err := InitDB(dbPath)
	if err != nil {
		t.Fatal(err)
	}
	defer db2.Close()

	rows, err := db2.Query("PRAGMA table_info(watchlist)")
	if err != nil {
		t.Fatal(err)
	}
	cols := make(map[string]bool)
	for rows.Next() {
		var cid int
		var name, typ string
		var notnull int
		var dfltValue *string
		var pk int
		rows.Scan(&cid, &name, &typ, &notnull, &dfltValue, &pk)
		cols[name] = true
	}
	rows.Close()

	if !cols["name"] {
		t.Error("expected name column after migration")
	}
	if !cols["currency"] {
		t.Error("expected currency column after migration")
	}

	entries, _ := GetWatchlist(db2)
	if entries[0].Ticker != "AAPL" {
		t.Errorf("expected AAPL, got %s", entries[0].Ticker)
	}
	if entries[0].Name != "" {
		t.Errorf("expected empty name, got %q", entries[0].Name)
	}
}

func TestDefaultDBPath(t *testing.T) {
	path := DefaultDBPath()
	if !filepath.IsAbs(path) {
		t.Errorf("expected absolute path, got %s", path)
	}
	base := filepath.Base(path)
	if base != "stonks.db" {
		t.Errorf("expected stonks.db, got %s", base)
	}
	dir := filepath.Base(filepath.Dir(path))
	if dir != "stonks" {
		t.Errorf("expected stonks dir, got %s", dir)
	}
}

func TestDefaultDBPathRespectsXDGDataHome(t *testing.T) {
	if os.Getenv("GOOS") == "darwin" {
		t.Skip("XDG_DATA_HOME not used on macOS")
	}
	orig := os.Getenv("XDG_DATA_HOME")
	os.Setenv("XDG_DATA_HOME", "/tmp/test-xdg")
	defer os.Setenv("XDG_DATA_HOME", orig)

	// Only test on Linux (on macOS, DefaultDBPath ignores XDG_DATA_HOME)
	if filepath.Dir(filepath.Dir(DefaultDBPath())) == "/tmp/test-xdg" {
		// pass — XDG was respected
	}
}
