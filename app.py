import streamlit as st
import requests
import pandas as pd
import json, os
from datetime import datetime

# ================= CONFIG =================
st.set_page_config(
    page_title="World Class Futures Scanner",
    layout="wide"
)

API_URL = "https://api.delta.exchange/v2/tickers"
DATA_FILE = "trades.json"
OI_FILE = "oi_snapshot.json"

# ================= FILE HELPERS =================
def load_trades():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_trades(trades):
    with open(DATA_FILE, "w") as f:
        json.dump(trades, f, indent=2)

def load_oi():
    if not os.path.exists(OI_FILE):
        return {}
    with open(OI_FILE, "r") as f:
        return json.load(f)

def save_oi(data):
    with open(OI_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ================= FETCH =================
@st.cache_data(ttl=5)
def fetch_data():
    r = requests.get(API_URL, timeout=10)
    data = r.json().get("result", [])
    if isinstance(data, dict):
        data = list(data.values())
    return data

# ================= PROCESS =================
def prepare_df(data):
    rows = []
    for d in data:
        symbol = d.get("symbol")
        mark = d.get("mark_price")
        if not symbol or not mark:
            continue
        try:
            price = float(mark)
        except:
            continue

        rows.append({
            "Symbol": symbol,
            "Price": price,
            "Volume": float(d.get("volume", 0) or 0),
            "OI": float(d.get("oi", 0) or 0),
            "Funding": float(d.get("funding_rate", 0) or 0)
        })
    return pd.DataFrame(rows)

# ================= TP LOGIC =================
def calc_tp(price, direction):
    if price < 0.001:
        p1, p2, d = 0.05, 0.10, 8
    elif price < 0.01:
        p1, p2, d = 0.03, 0.06, 7
    elif price < 1:
        p1, p2, d = 0.02, 0.04, 6
    else:
        p1, p2, d = 0.01, 0.02, 4

    if direction == "LONG":
        return round(price*(1+p1), d), round(price*(1+p2), d)
    else:
        return round(price*(1-p1), d), round(price*(1-p2), d)

# ================= STRATEGY =================
def find_trade(df, oi_prev):
    if df.empty:
        return None

    df = df.sort_values("Volume", ascending=False).head(25)

    best, best_score = None, 0
    for _, r in df.iterrows():
        if r["Volume"] < 1000 or r["OI"] < 1000:
            continue

        prev_oi = oi_prev.get(r["Symbol"], 0)
        oi_change = r["OI"] - prev_oi

        # 🔥 OI CHANGE FILTER
        if oi_change <= 0:
            continue

        # 🔥 DIRECTION
        if r["Volume"] > r["OI"]:
            direction = "LONG"
            score = r["Volume"] / (r["OI"]+1)
            # FUNDING FILTER
            if r["Funding"] > 0:
                continue
        else:
            direction = "SHORT"
            score = r["OI"] / (r["Volume"]+1)
            if r["Funding"] < 0:
                continue

        if score > best_score:
            tp1, tp2 = calc_tp(r["Price"], direction)
            best = {
                "Time": datetime.now().strftime("%H:%M:%S"),
                "Symbol": r["Symbol"],
                "Direction": direction,
                "Entry": f"{r['Price']:.8f}",
                "TP1": f"{tp1:.8f}",
                "TP2": f"{tp2:.8f}",
                "Status": "RUNNING"
            }
            best_score = score

    return best

# ================= STATUS UPDATE =================
def update_status(trade, price):
    if trade["Status"] != "RUNNING":
        return trade

    tp1, tp2 = float(trade["TP1"]), float(trade["TP2"])

    if trade["Direction"] == "LONG":
        if price >= tp2:
            trade["Status"] = "TP ACHIEVED ✅"
        elif price >= tp1:
            trade["Status"] = "TP1 HIT 🟢"
    else:
        if price <= tp2:
            trade["Status"] = "TP ACHIEVED ✅"
        elif price <= tp1:
            trade["Status"] = "TP1 HIT 🟢"

    return trade

# ================= UI =================
st.title("🚀 World Class Futures Scanner")

trades = load_trades()
oi_prev = load_oi()

df = prepare_df(fetch_data())
price_map = dict(zip(df["Symbol"], df["Price"]))

# Update running trades
for t in trades:
    if t["Status"] == "RUNNING" and t["Symbol"] in price_map:
        update_status(t, price_map[t["Symbol"]])

save_trades(trades)

# Save latest OI snapshot
save_oi(dict(zip(df["Symbol"], df["OI"])))

st.caption(f"📊 Markets scanned: {len(df)}")

# ================= GET TRADE =================
if st.button("🔥 GET BEST TRADE", use_container_width=True):
    new_trade = find_trade(df, oi_prev)
    if new_trade:
        trades.insert(0, new_trade)
        save_trades(trades)
        st.success("✅ High probability trade added (OI + Funding confirmed)")
    else:
        st.warning("❌ No mota paisa trade right now")

st.divider()

# ================= RUNNING TRADES PANEL =================
st.subheader("🟢 RUNNING TRADES")

running_trades = [t for t in trades if t["Status"] == "RUNNING"]

if not running_trades:
    st.info("No running trades")
else:
    for idx, t in enumerate(running_trades):
        c1, c2, c3, c4, c5, c6, c7 = st.columns([1.2, 1.5, 1, 1.5, 1.5, 1.5, 1.8])
        c1.write(t["Time"])
        c2.write(t["Symbol"])
        c3.write(t["Direction"])
        c4.write(t["Entry"])
        c5.write(t["TP1"])
        c6.write(t["TP2"])

        if c7.button("🛑 CLOSE", key=f"close_{idx}"):
            t["Status"] = "MANUALLY CLOSED ❌"
            save_trades(trades)
            st.rerun()

st.divider()

# ================= HISTORY =================
st.subheader("📜 Trade Scan History")
if trades:
    st.dataframe(pd.DataFrame(trades), use_container_width=True)
else:
    st.info("No trades yet")

st.caption("⚠️ Futures risky hote hain | OI Change + Funding Rate Filter Enabled")
