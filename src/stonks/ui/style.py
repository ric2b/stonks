DARK_STYLE = """
/* ── Global ─────────────────────────────────────────── */
QWidget {
    font-size: 13px;
    color: rgba(255, 255, 255, 235);
    background-color: #1e1e1e;
}
QMainWindow {
    background-color: #1e1e1e;
}

/* ── Chart area background ──────────────────────────── */
QWidget#rightPane,
QWidget#chartHeader,
QWidget#tabWrap {
    background-color: #242424;
}

/* ── Splitter ────────────────────────────────────────── */
QSplitter::handle:horizontal {
    width: 1px;
    background-color: rgba(255, 255, 255, 20);
}
QSplitter::handle:vertical {
    height: 1px;
    background-color: rgba(255, 255, 255, 20);
}

/* ── Sidebar list ────────────────────────────────────── */
QListWidget {
    background-color: #1c1c1c;
    border: none;
    outline: none;
    padding: 0px 8px 0px 8px;
}
QListWidget::item {
    border-radius: 8px;
    border: 1px solid transparent;
    padding: 0px;
    margin: 1px 0px;
}
QListWidget::item:hover {
    background-color: rgba(255, 255, 255, 13);
}
QListWidget::item:selected {
    background-color: rgba(255, 255, 255, 26);
    border: 1px solid rgba(255, 255, 255, 36);
}
QListWidget::item:selected:active {
    background-color: rgba(255, 255, 255, 26);
    border: 1px solid rgba(255, 255, 255, 36);
}

/* ── Inputs ──────────────────────────────────────────── */
QLineEdit {
    background-color: #303030;
    border: 1px solid rgba(255, 255, 255, 20);
    border-radius: 8px;
    padding: 7px 10px;
    color: rgba(255, 255, 255, 235);
    selection-background-color: rgba(255, 255, 255, 80);
}
QLineEdit:focus {
    border: 1px solid rgba(255, 255, 255, 80);
}
QLineEdit:disabled {
    color: rgba(255, 255, 255, 80);
}

/* ── Watchlist section header ────────────────────────── */
QLabel#watchlistHeader {
    color: rgba(255, 255, 255, 107);
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.6px;
    text-transform: uppercase;
    background-color: transparent;
}

/* ── Sidebar row labels ──────────────────────────────── */
QLabel#sidebarTicker {
    font-size: 13px;
    font-weight: 600;
    color: rgba(255, 255, 255, 235);
    background-color: transparent;
}
QLabel#sidebarPrice {
    font-family: "Courier New";
    font-size: 13px;
    font-weight: 500;
    color: rgba(255, 255, 255, 235);
    background-color: transparent;
}
QLabel#sidebarName {
    font-size: 11px;
    color: rgba(255, 255, 255, 158);
    background-color: transparent;
}
QLabel#sidebarChange {
    font-family: "Courier New";
    font-size: 11px;
    font-weight: 600;
    background-color: transparent;
}

/* ── Add ticker button ───────────────────────────────── */
QPushButton#addTickerBtn {
    background-color: #303030;
    border: 1px solid rgba(255, 255, 255, 20);
    border-radius: 8px;
    padding: 9px 12px;
    color: rgba(255, 255, 255, 235);
    font-size: 13px;
    font-weight: 500;
    text-align: center;
}
QPushButton#addTickerBtn:hover {
    background-color: #383838;
}
QPushButton#addTickerBtn:pressed {
    background-color: #2a2a2a;
}

/* ── Range tab pill container ────────────────────────── */
QFrame#rangeTabBar {
    background-color: #1e1e1e;
    border: 1px solid rgba(255, 255, 255, 36);
    border-radius: 16px;
    padding: 3px;
}
QPushButton#rangeBtn {
    background-color: transparent;
    border: none;
    border-radius: 12px;
    padding: 6px 14px;
    color: rgba(255, 255, 255, 158);
    font-size: 12px;
    font-weight: 500;
    min-width: 28px;
}
QPushButton#rangeBtn:hover {
    color: rgba(255, 255, 255, 220);
    background-color: rgba(255, 255, 255, 13);
}
QPushButton#rangeBtn:checked {
    background-color: #4a4a4a;
    border: 1px solid rgba(255, 255, 255, 50);
    color: rgba(255, 255, 255, 235);
    font-weight: 600;
}

/* ── Chart header labels ─────────────────────────────── */
QLabel#chartSymbol {
    font-size: 26px;
    font-weight: 700;
    color: rgba(255, 255, 255, 235);
    background-color: transparent;
    letter-spacing: -0.4px;
}
QLabel#chartCompany {
    font-size: 13px;
    color: rgba(255, 255, 255, 158);
    background-color: transparent;
}
QLabel#chartPrice {
    font-family: "Courier New";
    font-size: 22px;
    font-weight: 600;
    color: rgba(255, 255, 255, 235);
    background-color: transparent;
}
QLabel#chartChange {
    font-family: "Courier New";
    font-size: 13px;
    font-weight: 600;
    background-color: transparent;
}
QLabel#chartHoverDate {
    font-family: "Courier New";
    font-size: 11px;
    color: rgba(255, 255, 255, 158);
    background-color: transparent;
}
QLabel#chartHoverPrice {
    font-family: "Courier New";
    font-size: 11px;
    font-weight: 500;
    color: rgba(255, 255, 255, 235);
    background-color: rgba(42, 42, 42, 220);
    border: 1px solid rgba(255, 255, 255, 36);
    border-radius: 4px;
    padding: 0px 5px;
}
QLabel#chartExchange {
    font-family: "Courier New";
    font-size: 11px;
    color: rgba(255, 255, 255, 107);
    background-color: transparent;
    letter-spacing: 0.3px;
}

/* ── Stats grid labels ───────────────────────────────── */
QLabel#statLabel {
    font-size: 12px;
    color: rgba(255, 255, 255, 158);
    background-color: transparent;
}
QLabel#statValue {
    font-family: "Courier New";
    font-size: 12px;
    font-weight: 500;
    color: rgba(255, 255, 255, 235);
    background-color: transparent;
}

/* ── News section ───────────────────────────────────── */
QLabel#newsHeader {
    font-size: 11px;
    font-weight: 600;
    color: rgba(255, 255, 255, 107);
    background-color: transparent;
    letter-spacing: 0.6px;
    text-transform: uppercase;
}
QLabel#newsTitle {
    font-size: 12px;
    font-weight: 500;
    color: rgba(255, 255, 255, 220);
    background-color: transparent;
    line-height: 1.3;
}
QLabel#newsMeta {
    font-size: 11px;
    color: rgba(255, 255, 255, 107);
    background-color: transparent;
}

/* ── Status bar ──────────────────────────────────────── */
QWidget#statusBar {
    background-color: #2a2a2a;
    border-top: 1px solid rgba(255, 255, 255, 20);
}
QLabel#statusText {
    font-family: "Courier New";
    font-size: 10px;
    color: rgba(255, 255, 255, 107);
    background-color: transparent;
    letter-spacing: 0.3px;
}
QLabel#liveDot {
    background-color: #4cd278;
    border-radius: 3px;
}

/* ── Horizontal separator ────────────────────────────── */
QFrame#separator {
    background-color: rgba(255, 255, 255, 20);
    border: none;
    max-height: 1px;
    min-height: 1px;
}

/* ── Search results list ─────────────────────────────── */
QListWidget#searchResults {
    background-color: #2a2a2a;
    border: 1px solid rgba(255, 255, 255, 36);
    border-radius: 8px;
    outline: none;
    padding: 3px;
}
QListWidget#searchResults::item {
    border-radius: 6px;
    padding: 0px;
    margin: 1px 0px;
}
QListWidget#searchResults::item:hover {
    background-color: rgba(255, 255, 255, 13);
}
QListWidget#searchResults::item:selected {
    background-color: rgba(255, 255, 255, 20);
}
QLabel#searchResultSymbol {
    font-size: 13px;
    font-weight: 600;
    color: rgba(255, 255, 255, 235);
    background-color: transparent;
}
QLabel#searchResultName {
    font-size: 11px;
    color: rgba(255, 255, 255, 158);
    background-color: transparent;
}
QLabel#searchResultExchange {
    font-family: "Courier New";
    font-size: 10px;
    color: rgba(255, 255, 255, 107);
    background-color: transparent;
    letter-spacing: 0.3px;
}

/* ── Empty state ─────────────────────────────────────── */
QLabel#emptyStateIcon {
    font-size: 32px;
    background-color: rgba(255, 255, 255, 13);
    border-radius: 16px;
    padding: 12px;
    max-width: 56px;
    min-width: 56px;
    max-height: 56px;
    min-height: 56px;
    qproperty-alignment: AlignCenter;
}
QLabel#emptyStateHeading {
    font-size: 18px;
    font-weight: 600;
    color: rgba(255, 255, 255, 235);
    background-color: transparent;
}
QLabel#emptyStateDesc {
    font-size: 13px;
    color: rgba(255, 255, 255, 107);
    background-color: transparent;
    line-height: 1.4;
}

/* ── Scrollbars ──────────────────────────────────────── */
QScrollBar:vertical {
    background-color: transparent;
    width: 6px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background-color: rgba(255, 255, 255, 50);
    border-radius: 3px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover {
    background-color: rgba(255, 255, 255, 80);
}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {
    background: transparent;
}
"""
