from fastapi import FastAPI
import yfinance as yf
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import pytz
import os
from twilio.rest import Client

app = FastAPI()
SYMBOL = "IBM"
cached = {"symbol": SYMBOL, "price": None, "timestamp": None}

# Function to send WhatsApp message
def send_whatsapp(price, timestamp):
    account_sid = os.getenv("TWILIO_SID")
    auth_token  = os.getenv("TWILIO_AUTH_TOKEN")
    from_whatsapp = os.getenv("TWILIO_WHATSAPP_FROM")  # Twilio sandbox number
    to_whatsapp = os.getenv("MY_WHATSAPP")             # Your phone number

    if not all([account_sid, auth_token, from_whatsapp, to_whatsapp]):
        print("Twilio WhatsApp environment variables not set")
        return

    client = Client(account_sid, auth_token)
    try:
        client.messages.create(
            body=f"IBM stock opening price: ${price} at {timestamp}",
            from_=f"whatsapp:{from_whatsapp.replace('whatsapp:', '')}",
            to=f"whatsapp:{to_whatsapp.replace('whatsapp:', '')}"
        )
        print("WhatsApp message sent successfully")
    except Exception as e:
        print(f"Error sending WhatsApp message: {e}")

# Function to fetch IBM opening price
def fetch_open_price():
    tz = pytz.timezone("US/Eastern")
    now_et = datetime.now(tz)
    ticker = yf.Ticker(SYMBOL)
    hist = ticker.history(period="1d", interval="1m")
    if not hist.empty:
        hist = hist.tz_convert("US/Eastern")
        t930 = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
        row = hist[hist.index >= t930].iloc[0] if any(hist.index >= t930) else hist.iloc[-1]
        price = float(row['Close'])
        cached.update({"price": round(price, 2), "timestamp": datetime.now(tz).isoformat()})
        send_whatsapp(cached["price"], cached["timestamp"])

# Scheduler to run at 9:30 AM ET weekdays
scheduler = BackgroundScheduler(timezone="US/Eastern")
scheduler.add_job(fetch_open_price, "cron", day_of_week="mon-fri", hour=9, minute=30)
scheduler.start()

# Root endpoint
@app.get("/")
def root():
    return {"message": "IBM Opening Price API with WhatsApp"}

# Endpoint to get cached price
@app.get("/price")
def get_price():
    return cached

# Endpoint to manually refresh and trigger WhatsApp
@app.post("/refresh")
def refresh(token: str = ""):
    fetch_open_price()
    return {"status": "ok", "cached": cached}
