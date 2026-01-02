import streamlit as st
import requests
import pandas as pd
import json, os
from datetime import datetime

# ================= BASIC CONFIG =================
st.set_page_config(
    page_title="World Class Futures Scanner",
    layout="wide"
)

APP_PASSWORD = "uatpjexk2a@9988"

API_URL = "https://api.delta.exchange/v2/tickers"
DATA_FILE = "trades.json"
OI_FILE = "oi_snapshot.json"

# ================= PASSWORD GATE =================
if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    st.markdown("## 🔐 Login Required")
    pwd = st.text_input("Enter Password", type="password")
    if st.button("LOGIN", use_container_width=True):
        if pwd == APP_PASSWORD:
            st.session_state.auth = True
            st.rerun()
        else:
            st.error("❌ Wrong password")
    st.stop()

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
            "Funding": float(d.get("funding_rate", 0) or 0),
            # ✅ STEP 1: price change added
            "Change": float(d.get("price_change_percent", 0) or 0)
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
        oi_delta = r["OI"] - prev_oi
        if oi_delta <= 0:
            continue

        # ✅ STEP 2: balanced direction logic
        if oi_delta > 0 and r["Change"] > 0:
            direction = "LONG"
        elif oi_delta > 0 and r["Change"] < 0:
            direction = "SHORT"
        else:
            continue

        # ✅ STEP 3: smart funding filter
        if direction == "LONG" and r["Funding"] > 0.01:
            continue
        if direction == "SHORT" and r["Funding"] < -0.01:
            continue

        # ✅ STEP 4: neutral score
        score = (r["Volume"] * oi_delta) / (abs(r["Change"]) + 0.001)

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
st.markdown("## 🚀 World Class Futures Scanner")

trades = load_trades()
oi_prev = load_oi()

df = prepare_df(fetch_data())
price_map = dict(zip(df["Symbol"], df["Price"]))

for t in trades:
    if t["Status"] == "RUNNING" and t["Symbol"] in price_map:
        update_status(t, price_map[t["Symbol"]])

save_trades(trades)
save_oi(dict(zip(df["Symbol"], df["OI"])))

st.caption(f"📊 Markets scanned: {len(df)}")

# ================= GET TRADE =================
if st.button("🔥 GET BEST TRADE", use_container_width=True):
    trade = find_trade(df, oi_prev)
    if trade:
        trades.insert(0, trade)
        save_trades(trades)
        st.success("✅ High probability trade added")
    else:
        st.warning("❌ No mota paisa trade now")

st.divider()

# ================= RUNNING TRADES =================
st.subheader("🟢 RUNNING TRADES")

running = [t for t in trades if t["Status"] == "RUNNING"]

if not running:
    st.info("No running trades")
else:
    for i, t in enumerate(running):
        c1, c2, c3, c4, c5, c6, c7 = st.columns([1.1,1.4,0.9,1.4,1.4,1.4,1.8])
        c1.write(t["Time"])
        c2.write(t["Symbol"])
        c3.write(t["Direction"])
        c4.write(t["Entry"])
        c5.write(t["TP1"])
        c6.write(t["TP2"])

        if c7.button("🛑 CLOSE", key=f"close_{i}"):
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

st.caption("⚠️ Futures risky hote hain | Mobile optimized | Secure login enabled")
