import asyncio
import sqlite3
from typing import List, Optional
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import yfinance as yf
import pandas_ta as ta

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# --- DATABASE SETUP (SQLite) ---
DB_FILE = "scanner.db"

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS app_state (
                id INTEGER PRIMARY KEY,
                account_size REAL DEFAULT 10000,
                risk_pct REAL DEFAULT 1.0,
                tickers TEXT DEFAULT 'AAPL, TSLA, MSFT, BTC-USD'
            )
        """)
        conn.execute("INSERT OR IGNORE INTO app_state (id) VALUES (1)")

init_db()

def get_state():
    with sqlite3.connect(DB_FILE) as conn:
        row = conn.execute("SELECT account_size, risk_pct, tickers FROM app_state WHERE id=1").fetchone()
        return {"account_size": row[0], "risk_pct": row[1], "tickers": row[2]}

def save_state(account_size: float, risk_pct: float, tickers: str):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("UPDATE app_state SET account_size=?, risk_pct=?, tickers=? WHERE id=1", 
                     (account_size, risk_pct, tickers))

# --- DATA MODELS ---
class StockResult(BaseModel):
    ticker: str
    price: float
    # Technicals
    ema_200: float
    rsi: float
    adx: float           # <--- NEW: Trend Strength
    macd: float
    macd_signal: float
    atr: float
    volume: int
    avg_volume: int
    
    # Analysis
    trend: str
    signal: str
    reason: str
    
    # Trade Plan
    stop_loss: float
    take_profit: float
    risk_reward: float
    
    # Position Sizing
    shares_to_buy: int
    position_cost: float
    affordable: bool
    actual_risk: float
    
    error: Optional[str] = None

# --- CORE LOGIC ---
async def fetch_data(ticker: str, account_size: float, risk_pct: float) -> Optional[StockResult]:
    try:
        def get_stock_data_sync():
            dat = yf.Ticker(ticker)
            df = dat.history(period="2y")
            return df

        df = await asyncio.to_thread(get_stock_data_sync)
        
        if df.empty or len(df) < 200:
            return StockResult(
                ticker=ticker.upper(), price=0, ema_200=0, rsi=0, adx=0, macd=0, macd_signal=0, atr=0, volume=0, avg_volume=0,
                trend="N/A", signal="N/A", reason="Insufficient Data", stop_loss=0, take_profit=0, risk_reward=0,
                shares_to_buy=0, position_cost=0, affordable=False, actual_risk=0, error="No Data"
            )

        # 1. Indicators
        df.ta.ema(length=200, append=True)
        df.ta.rsi(length=14, append=True)
        df.ta.atr(length=14, append=True)
        df.ta.macd(fast=12, slow=26, signal=9, append=True) 
        df.ta.adx(length=14, append=True)  # <--- NEW: Calculate ADX

        latest = df.iloc[-1]
        price = float(latest["Close"])
        ema_200 = float(latest.get("EMA_200", 0))
        rsi = float(latest.get("RSI_14", 50))
        atr = float(latest.get("ATRr_14", 0))
        volume = int(latest.get("Volume", 0))
        avg_volume = int(df["Volume"].tail(20).mean())

        # Dynamic Column Fetching (Safe extraction)
        macd_col = next((c for c in df.columns if c.startswith("MACD_") and "MACDs" not in c and "MACDh" not in c), None)
        signal_col = next((c for c in df.columns if c.startswith("MACDs_")), None)
        adx_col = next((c for c in df.columns if c.startswith("ADX_") and "DMP" not in c and "DMN" not in c), None)

        macd = float(latest[macd_col]) if macd_col else 0.0
        macd_signal = float(latest[signal_col]) if signal_col else 0.0
        adx = float(latest[adx_col]) if adx_col else 0.0  # <--- NEW: Extract ADX

        # 2. Decision Engine
        trend = "Uptrend" if price > ema_200 else "Downtrend"
        signal = "WAIT"
        reason = "No setup."

        if trend == "Uptrend":
            # --- NEW: CHOP FILTER ---
            if adx < 20:
                signal = "AVOID"
                reason = f"Weak Trend (ADX {round(adx)}). Chop Zone."
            else:
                # Normal Logic (Only runs if ADX >= 20)
                if rsi < 30:
                    signal = "STRONG BUY"
                    reason = f"Extreme Oversold (<30). ADX {round(adx)}."
                elif rsi < 50:
                    if macd > macd_signal:
                        signal = "BUY SIGNAL"
                        reason = f"Pullback + MACD Cross. ADX {round(adx)}."
                    else:
                        signal = "WATCHLIST"
                        reason = f"Pullback active. Wait for turn. ADX {round(adx)}."
                else:
                    reason = f"In Uptrend, but expensive. ADX {round(adx)}."
        else:
            signal = "AVOID"
            reason = "Downtrend (Below 200 EMA)."

        # 3. Trade Plan & Position Sizing
        stop_loss = round(price - (2 * atr), 2)
        take_profit = round(price + (3 * atr), 2)
        
        risk_per_share = price - stop_loss
        max_risk_dollars = account_size * (risk_pct / 100)
        
        shares = 0
        if risk_per_share > 0:
            shares = int(max_risk_dollars / risk_per_share)
        
        position_cost = round(shares * price, 2)
        actual_risk = round(shares * risk_per_share, 2)
        affordable = position_cost <= account_size
        rr_ratio = round((take_profit - price) / (price - stop_loss), 2) if risk_per_share > 0 else 0

        return StockResult(
            ticker=ticker.upper(),
            price=round(price, 2),
            ema_200=round(ema_200, 2),
            rsi=round(rsi, 2),
            adx=round(adx, 2),  # <--- Return ADX
            macd=round(macd, 2),
            macd_signal=round(macd_signal, 2),
            atr=round(atr, 2),
            volume=volume,
            avg_volume=avg_volume,
            trend=trend,
            signal=signal,
            reason=reason,
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_reward=rr_ratio,
            shares_to_buy=shares,
            position_cost=position_cost,
            affordable=affordable,
            actual_risk=actual_risk
        )

    except Exception as e:
        return StockResult(
            ticker=ticker.upper(), price=0, ema_200=0, rsi=0, adx=0, macd=0, macd_signal=0, atr=0, volume=0, avg_volume=0,
            trend="Error", signal="Error", reason=str(e), stop_loss=0, take_profit=0, risk_reward=0,
            shares_to_buy=0, position_cost=0, affordable=False, actual_risk=0, error="Calc Error"
        )

# --- ROUTES ---

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    state = get_state()
    return templates.TemplateResponse("index.html", {
        "request": request,
        "state": state
    })

@app.post("/scan", response_class=HTMLResponse)
async def scan_stocks(
    request: Request, 
    tickers: str = Form(...), 
    account_size: float = Form(...), 
    risk_pct: float = Form(...)
):
    # OPTIMIZATION: Non-blocking DB Save
    await asyncio.to_thread(save_state, account_size, risk_pct, tickers)

    ticker_list = [t.strip() for t in tickers.split(",") if t.strip()]
    
    if not ticker_list:
        return templates.TemplateResponse("partials/results.html", {"request": request, "results": []})

    tasks = [fetch_data(t, account_size, risk_pct) for t in ticker_list]
    results = await asyncio.gather(*tasks)
    
    priority = {"STRONG BUY": 0, "BUY SIGNAL": 1, "WATCHLIST": 2, "WAIT": 3, "AVOID": 4, "Error": 5}
    results.sort(key=lambda x: priority.get(x.signal, 5))

    return templates.TemplateResponse("partials/results.html", {"request": request, "results": results})