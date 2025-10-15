from fastapi import FastAPI
import yfinance as yf
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import pytz
import os
from twilio.rest import Client

app = FastAPI()
SYMBOL = os.getenv("SYMBOL", "IBM")

# store last fetched opening price
cached = {"symbol": SYMBOL, "price": None, "timestamp": None}

# ---------------- WhatsApp Function ----------------
def send_whatsapp(price, timestamp):
    account_sid = os.getenv("TWILIO_SID")
    auth_token  = os.getenv("TWILIO_AUTH_TOKEN")
    from_whatsapp = os.getenv("TWILIO_WHATSAPP_FROM")  # Twilio sandbox number
    to_whatsapp = os.getenv("MY_WHATSAPP")             # Your verified number

    if not all([account_sid, auth_token, from_whatsapp, to_whatsapp]):
        print("Twilio WhatsApp env vars not set, skipping message")
        return

    client = Client(account_sid, auth_token)
    message = f"IBM stock opening price: ${price} at {timestamp}"
    client.messages.create(
        body=message,
        from_=f"whatsapp:{from_whatsapp}",
        to=f"whatsapp:{to_whatsapp}"
    )
# ---------------------------------------------------

def fetch_open_price():
    """Fetch today's IBM price and send WhatsApp notification."""
    tz = pytz.timezone("US/Eastern")
    now_et = datetime.now(tz)
    ticker = yf.Ticker(SYMBOL)
    hist = ticker.history(period="1d", interval="1m")

    if not hist.empty:
        hist = hist.tz_convert("US/Eastern")
        t930 = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
        if t930 in hist.index:
            row = hist.loc[t930]
        else:
            # fallback: first row >= 9:30 or last available
            row = hist[hist.index >= t930].iloc[0] if any(hist.index >= t930) else hist.iloc[-1]

        price = float(row['Close'])
        cached.update({
            "price": round(price, 2),
            "timestamp": datetime.now(tz).isoformat()
        })

        # Send WhatsApp message
        send_whatsapp(cached["price"], cached["timestamp"])

# Scheduler: weekdays at 9:30 AM US/Eastern
scheduler = BackgroundScheduler(timezone="US/Eastern")
scheduler.add_job(fetch_open_price, "cron", day_of_week="mon-fri", hour=9, minute=30)
scheduler.start()

@app.get("/")
def root():
    return {"message": "IBM Opening Price API with WhatsApp"}

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
