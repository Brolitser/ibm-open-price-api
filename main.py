from fastapi import FastAPI
import yfinance as yf
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import pytz
import os

app = FastAPI()
SYMBOL = os.getenv("SYMBOL", "IBM")

cached = {"symbol": SYMBOL, "price": None, "timestamp": None}

def fetch_open_price():
    tz = pytz.timezone("US/Eastern")
    ticker = yf.Ticker(SYMBOL)
    hist = ticker.history(period="1d", interval="1m")
    if not hist.empty:
        hist = hist.tz_convert("US/Eastern")
        t930 = datetime.now(tz).replace(hour=9, minute=30, second=0, microsecond=0)
        if t930 in hist.index:
            row = hist.loc[t930]
        else:
            row = hist[hist.index >= t930].iloc[0] if any(hist.index >= t930) else hist.iloc[-1]
        price = float(row['Close'])
        cached.update({
            "price": round(price, 2),
            "timestamp": datetime.now(tz).isoformat()
        })

scheduler = BackgroundScheduler(timezone="US/Eastern")
scheduler.add_job(fetch_open_price, "cron", day_of_week="mon-fri", hour=9, minute=30)
scheduler.start()

@app.get("/")
def root():
    return {"message": "IBM Opening Price API"}

@app.get("/price")
def get_price():
    return cached

@app.post("/refresh")
def refresh(token: str = ""):
    secret = os.getenv("REFRESH_TOKEN", "")
    if secret and token != secret:
        return {"error": "invalid token"}, 401
    fetch_open_price()
    return {"status": "ok", "cached": cached}
