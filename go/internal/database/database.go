package database

import (
	"database/sql"
	"os"
	"path/filepath"
	"runtime"
	"strings"

	_ "modernc.org/sqlite"
)

type WatchlistEntry struct {
	Ticker   string `json:"ticker"`
	Position int    `json:"position"`
	Name     string `json:"name"`
	Currency string `json:"currency"`
}

func DefaultDBPath() string {
	if runtime.GOOS == "darwin" {
		home, _ := os.UserHomeDir()
		return filepath.Join(home, "Library", "Application Support", "stonks", "stonks.db")
	}
	dir := os.Getenv("XDG_DATA_HOME")
	if dir == "" {
		home, _ := os.UserHomeDir()
		dir = filepath.Join(home, ".local", "share")
	}
	return filepath.Join(dir, "stonks", "stonks.db")
}

func InitDB(dbPath string) (*sql.DB, error) {
	if err := os.MkdirAll(filepath.Dir(dbPath), 0o755); err != nil {
		return nil, err
	}

	db, err := sql.Open("sqlite", dbPath)
	if err != nil {
		return nil, err
	}

	if _, err := db.Exec(`
		CREATE TABLE IF NOT EXISTS watchlist (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			ticker TEXT UNIQUE NOT NULL,
			position INTEGER NOT NULL DEFAULT 0
		)
	`); err != nil {
		return nil, err
	}

	if _, err := db.Exec(`
		CREATE TABLE IF NOT EXISTS settings (
			key TEXT PRIMARY KEY,
			value TEXT NOT NULL
		)
	`); err != nil {
		return nil, err
	}

	if err := migrateWatchlistColumns(db); err != nil {
		return nil, err
	}

	return db, nil
}

func migrateWatchlistColumns(db *sql.DB) error {
	rows, err := db.Query("PRAGMA table_info(watchlist)")
	if err != nil {
		return err
	}
	defer rows.Close()

	cols := make(map[string]bool)
	for rows.Next() {
		var cid int
		var name, typ string
		var notnull int
		var dfltValue *string
		var pk int
		if err := rows.Scan(&cid, &name, &typ, &notnull, &dfltValue, &pk); err != nil {
			return err
		}
		cols[name] = true
	}

	if !cols["name"] {
		if _, err := db.Exec("ALTER TABLE watchlist ADD COLUMN name TEXT NOT NULL DEFAULT ''"); err != nil {
			return err
		}
	}
	if !cols["currency"] {
		if _, err := db.Exec("ALTER TABLE watchlist ADD COLUMN currency TEXT NOT NULL DEFAULT ''"); err != nil {
			return err
		}
	}
	return nil
}

func GetSetting(db *sql.DB, key string, defaultVal string) (string, error) {
	var value string
	err := db.QueryRow("SELECT value FROM settings WHERE key = ?", key).Scan(&value)
	if err == sql.ErrNoRows {
		return defaultVal, nil
	}
	if err != nil {
		return "", err
	}
	return value, nil
}

func SetSetting(db *sql.DB, key string, value string) error {
	_, err := db.Exec("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", key, value)
	return err
}

func GetWatchlist(db *sql.DB) ([]WatchlistEntry, error) {
	rows, err := db.Query("SELECT ticker, position, name, currency FROM watchlist ORDER BY position")
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var entries []WatchlistEntry
	for rows.Next() {
		var e WatchlistEntry
		if err := rows.Scan(&e.Ticker, &e.Position, &e.Name, &e.Currency); err != nil {
			return nil, err
		}
		entries = append(entries, e)
	}
	return entries, nil
}

func UpdateTickerMeta(db *sql.DB, ticker string, name string, currency string) error {
	_, err := db.Exec(
		"UPDATE watchlist SET name = ?, currency = ? WHERE ticker = ?",
		name, currency, strings.ToUpper(ticker),
	)
	return err
}

func AddTicker(db *sql.DB, ticker string) error {
	var maxPos int
	err := db.QueryRow("SELECT COALESCE(MAX(position), -1) FROM watchlist").Scan(&maxPos)
	if err != nil {
		return err
	}
	_, err = db.Exec(
		"INSERT OR IGNORE INTO watchlist (ticker, position) VALUES (?, ?)",
		strings.ToUpper(ticker), maxPos+1,
	)
	return err
}

func RemoveTicker(db *sql.DB, ticker string) error {
	_, err := db.Exec("DELETE FROM watchlist WHERE ticker = ?", strings.ToUpper(ticker))
	return err
}

func ReorderWatchlist(db *sql.DB, tickers []string) error {
	tx, err := db.Begin()
	if err != nil {
		return err
	}
	defer tx.Rollback()

	for position, ticker := range tickers {
		if _, err := tx.Exec(
			"UPDATE watchlist SET position = ? WHERE ticker = ?",
			position, strings.ToUpper(ticker),
		); err != nil {
			return err
		}
	}
	return tx.Commit()
}
