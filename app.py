import streamlit as st
import requests, json, os
import pandas as pd
from datetime import datetime

# ================= BASIC CONFIG =================
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

# ================= TP LOGIC =================
def calc_tp(price, direction, mode):
    if mode == "SCALP":
        p1, p2 = 0.005, 0.01
    elif mode == "INTRADAY":
        p1, p2 = 0.015, 0.03
    elif mode == "SWING":
        p1, p2 = 0.04, 0.08
    else:  # BLAST
        p1, p2 = 0.02, 0.04

    if direction == "LONG":
        return price*(1+p1), price*(1+p2)
    else:
        return price*(1-p1), price*(1-p2)

# ================= STRATEGIES =================

def scan_blast(df, oi_prev):
    for _, r in df.iterrows():
        prev_oi = oi_prev.get(r["Symbol"], 0)
        oi_change = r["OI"] - prev_oi
        if oi_change <= r["OI"]*0.01:
            continue
        if r["High"] <= 0 or r["Low"] <= 0:
            continue

        range_pct = (r["High"] - r["Low"]) / r["Price"]
        if range_pct > 0.012:
            continue

        if r["Funding"] < 0:
            direction = "LONG"
        elif r["Funding"] > 0:
            direction = "SHORT"
        else:
            continue

        tp1, tp2 = calc_tp(r["Price"], direction, "BLAST")
        return build_trade(r, direction, tp1, tp2, "BLAST", "Pre-Blast Expansion")
    return None

def scan_scalp(df):
    for _, r in df.sort_values("Volume", ascending=False).head(20).iterrows():
        if r["Volume"] > r["OI"]*0.8:
            direction = "LONG"
        else:
            direction = "SHORT"

        tp1, tp2 = calc_tp(r["Price"], direction, "SCALP")
        return build_trade(r, direction, tp1, tp2, "SCALP", "Quick momentum")
    return None

def scan_intraday(df):
    for _, r in df.iterrows():
        if abs(r["Funding"]) < 0.005 and r["Volume"] > r["OI"]*0.4:
            direction = "LONG"
            tp1, tp2 = calc_tp(r["Price"], direction, "INTRADAY")
            return build_trade(r, direction, tp1, tp2, "INTRADAY", "Intraday trend")
    return None

def scan_swing(df):
    for _, r in df.iterrows():
        if r["OI"] > 10000 and abs(r["Funding"]) < 0.01 and r["Volume"] > r["OI"]*0.25:
            direction = "LONG"
            tp1, tp2 = calc_tp(r["Price"], direction, "SWING")
            return build_trade(r, direction, tp1, tp2, "SWING", "High probability swing")
    return None

def build_trade(r, direction, tp1, tp2, category, note):
    return {
        "Time": datetime.now().strftime("%H:%M:%S"),
        "Symbol": r["Symbol"],
        "Category": category,
        "Direction": direction,
        "Entry": f"{r['Price']:.6f}",
        "TP1": f"{tp1:.6f}",
        "TP2": f"{tp2:.6f}",
        "Status": "RUNNING",
        "Note": note
    }

# ================= UI =================
st.markdown("## 🚀 World Class Multi-Strategy Scanner")

mode = st.radio(
    "🧠 Select Trade Category",
    ["💣 BLAST", "⚡ SCALP", "🧭 INTRADAY", "🏹 SWING (HIGH PROB)"],
    horizontal=True
)

trades = load_json(DATA_FILE, [])
oi_prev = load_json(OI_FILE, {})

df = prepare_df(fetch_data())
save_json(OI_FILE, dict(zip(df["Symbol"], df["OI"])))

if st.button("🔥 GET HIGH PROBABILITY TRADE", use_container_width=True):
    if mode.startswith("💣"):
        trade = scan_blast(df, oi_prev)
    elif mode.startswith("⚡"):
        trade = scan_scalp(df)
    elif mode.startswith("🧭"):
        trade = scan_intraday(df)
    else:
        trade = scan_swing(df)

    if trade:
        trades.insert(0, trade)
        save_json(DATA_FILE, trades)
        st.success(f"✅ {trade['Category']} TRADE FOUND")
    else:
        st.warning("❌ No setup right now")

st.divider()

st.subheader("🟢 RUNNING TRADES")
running = [t for t in trades if t["Status"] == "RUNNING"]
if running:
    st.dataframe(pd.DataFrame(running), use_container_width=True)
else:
    st.info("No running trades")

st.divider()

st.subheader("📜 TRADE HISTORY")
if trades:
    st.dataframe(pd.DataFrame(trades), use_container_width=True)
else:
    st.info("No trades yet")

st.caption("⚠️ Futures risky hote hain | Multi-strategy engine | Pro level scanner")
