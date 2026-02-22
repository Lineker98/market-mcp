import yfinance as yf

def test_quote():
    ticker = yf.Ticker("AXIA3.SA")
    info = ticker.fast_info
    
    assert info.last_price > 0
    assert info.year_high > info.year_low
    print(f"✅ AXIA3.SA price: {info.last_price}")

def test_history():
    hist = yf.Ticker("AXIA3.SA").history(period="3mo")
    
    assert not hist.empty
    assert len(hist) >= 20          # need at least 20 candles for indicators
    assert "Close" in hist.columns
    print(f"✅ Candles fetched: {len(hist)}")

def test_invalid_ticker():
    hist = yf.Ticker("INVALIDXXX").history(period="1mo")
    print(f"Empty for invalid ticker: {hist.empty}")

if __name__ == "__main__":
    test_quote()
    test_history()
    test_invalid_ticker()