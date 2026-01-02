import streamlit as st
import requests, json, os
import pandas as pd
from datetime import datetime

# ================= CONFIG =================
st.set_page_config(page_title="World Class Multi Strategy Scanner", layout="wide")

APP_PASSWORD = "uatpjexk2a@9988"
API_URL = "https://api.delta.exchange/v2/tickers"
DATA_FILE = "trades.json"
OI_FILE = "oi_snapshot.json"

# ================= PASSWORD =================
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
def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r") as f:
            return json.load(f)
    except:
        return default

def save_json(path, data):
    with open(path, "w") as f:
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
        try:
            rows.append({
                "Symbol": d.get("symbol"),
                "Price": float(d.get("mark_price", 0)),
                "Volume": float(d.get("volume", 0)),
                "OI": float(d.get("oi", 0)),
                "Funding": float(d.get("funding_rate", 0)),
                "High": float(d.get("high", 0)),
                "Low": float(d.get("low", 0))
            })
        except:
            continue
    return pd.DataFrame(rows)

# ================= EXPECTED TIME =================
EXPECTED_TIME = {
    "BLAST": "5–20 min",
    "SCALP": "1–5 min",
    "INTRADAY": "30–90 min",
    "SWING": "1–5 days",
    "REVERSAL": "15–60 min",
    "TREND": "2–7 days",
    "LIQUIDITY": "5–30 min",
    "RANGE": "10–45 min",
    "EVENT": "1–10 min"
}

# ================= SAFE TP LOGIC =================
def calc_tp(price, direction, mode):
    if price < 0.001:
        p1, p2, d = 0.08, 0.15, 8
    elif price < 0.01:
        p1, p2, d = 0.05, 0.10, 7
    elif price < 1:
        p1, p2, d = 0.03, 0.06, 6
    else:
        p1, p2, d = 0.015, 0.03, 4

    if mode in ["SCALP", "RANGE"]:
        p1, p2 = p1 * 0.5, p2 * 0.5
    elif mode in ["SWING", "TREND"]:
        p1, p2 = p1 * 2, p2 * 2

    if direction == "LONG":
        tp1 = round(price * (1 + p1), d)
        tp2 = round(price * (1 + p2), d)
    else:
        tp1 = round(price * (1 - p1), d)
        tp2 = round(price * (1 - p2), d)

    if tp1 == price:
        tp1 = round(price * (1.01 if direction == "LONG" else 0.99), d)
    if tp2 == price or tp2 == tp1:
        tp2 = round(price * (1.02 if direction == "LONG" else 0.98), d)

    return tp1, tp2

# ================= BUILD TRADE =================
def build_trade(r, direction, tp1, tp2, category, note):
    return {
        "Time": datetime.now().strftime("%H:%M:%S"),
        "Symbol": r["Symbol"],
        "Category": category,
        "Direction": direction,
        "Entry": round(r["Price"], 8),
        "TP1": tp1,
        "TP2": tp2,
        "Expected Time": EXPECTED_TIME.get(category, "-"),
        "Status": "RUNNING",
        "Note": note
    }

# ================= STRATEGY (GENERIC ENGINE) =================
def scan_generic(df, oi_prev, category):
    for _, r in df.iterrows():
        if r["OI"] < 500:
            continue

        prev_oi = oi_prev.get(r["Symbol"], 0)
        oi_change = r["OI"] - prev_oi

        direction = "LONG" if r["Funding"] <= 0 else "SHORT"

        if category == "BLAST" and oi_change <= r["OI"] * 0.01:
            continue
        if category == "REVERSAL" and oi_change >= 0:
            continue

        tp1, tp2 = calc_tp(r["Price"], direction, category)
        return build_trade(r, direction, tp1, tp2, category, f"{category} setup")

    return None

# ================= STATUS UPDATE =================
def update_status(trade, price):
    if trade["Status"] != "RUNNING":
        return

    if trade["Direction"] == "LONG":
        if price >= trade["TP2"]:
            trade["Status"] = "TP ACHIEVED ✅"
        elif price >= trade["TP1"]:
            trade["Status"] = "TP1 HIT 🟢"
    else:
        if price <= trade["TP2"]:
            trade["Status"] = "TP ACHIEVED ✅"
        elif price <= trade["TP1"]:
            trade["Status"] = "TP1 HIT 🟢"

# ================= UI =================
st.markdown("## 🚀 World Class Multi-Strategy Scanner")

mode = st.radio(
    "🧠 Select Trade Type",
    ["💣 BLAST","⚡ SCALP","🧭 INTRADAY","🏹 SWING","🔄 REVERSAL","📈 TREND","🪤 LIQUIDITY","↔️ RANGE","📰 EVENT"],
    horizontal=True
)

trades = load_json(DATA_FILE, [])
oi_prev = load_json(OI_FILE, {})

df = prepare_df(fetch_data())
price_map = dict(zip(df["Symbol"], df["Price"]))

# Auto TP check
for t in trades:
    if t["Status"] == "RUNNING" and t["Symbol"] in price_map:
        update_status(t, price_map[t["Symbol"]])

save_json(DATA_FILE, trades)
save_json(OI_FILE, dict(zip(df["Symbol"], df["OI"])))


if st.button("🔥 GET HIGH PROBABILITY TRADE", use_container_width=True):
    category = mode.split(" ")[1]
    trade = scan_generic(df, oi_prev, category)
    if trade:
        trades.insert(0, trade)
        save_json(DATA_FILE, trades)
        st.success(f"✅ {category} TRADE ADDED")
    else:
        st.warning("❌ No setup now")

st.divider()

# ================= RUNNING =================
st.subheader("🟢 RUNNING TRADES")

running = [t for t in trades if t["Status"] == "RUNNING"]

if not running:
    st.info("No running trades")
else:
    for i, t in enumerate(running):
        c1,c2,c3,c4,c5,c6,c7,c8,c9,c10 = st.columns([1,1.4,1.1,1,1.2,1.2,1.4,1.4,1.3,1.2])
        c1.write(t["Time"])
        c2.write(t["Symbol"])
        c3.write(t["Category"])
        c4.write(t["Direction"])
        c5.write(t["Entry"])
        c6.write(t["TP1"])
        c7.write(t["TP2"])
        c8.write(t["Expected Time"])
        c9.write(t["Status"])
        if c10.button("🛑 CLOSE", key=f"close_{i}"):
            t["Status"] = "MANUALLY CLOSED ❌"
            save_json(DATA_FILE, trades)
            st.rerun()

st.divider()

st.subheader("📜 TRADE HISTORY")
if trades:
    st.dataframe(pd.DataFrame(trades), use_container_width=True)
else:
    st.info("No trades yet")

st.caption("⚠️ Futures risky hote hain | Multi-strategy engine | Expected Time enabled")
