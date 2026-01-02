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
def calc_tp(price, direction):
    if price < 0.01:
        p1, p2, d = 0.04, 0.08, 6
    elif price < 1:
        p1, p2, d = 0.025, 0.05, 5
    else:
        p1, p2, d = 0.015, 0.03, 4

    if direction == "LONG":
        return round(price*(1+p1), d), round(price*(1+p2), d)
    else:
        return round(price*(1-p1), d), round(price*(1-p2), d)

# ================= BLAST STRATEGY =================
def find_blast_trade(df, oi_prev):
    best, best_score = None, 0

    for _, r in df.iterrows():
        if r["OI"] < 500 or r["Volume"] < 500:
            continue

        prev_oi = oi_prev.get(r["Symbol"], 0)
        oi_change = r["OI"] - prev_oi
        if oi_change <= r["OI"] * 0.01:
            continue

        vol_oi = r["Volume"] / (r["OI"] + 1)

        if r["High"] > 0 and r["Low"] > 0:
            range_pct = (r["High"] - r["Low"]) / r["Price"]
        else:
            continue

        # ===== BLAST LONG =====
        if vol_oi < 0.9 and r["Funding"] < 0 and range_pct < 0.012:
            direction = "LONG"
            score = oi_change / (range_pct + 0.001)

        # ===== BLAST SHORT =====
        elif vol_oi < 0.9 and r["Funding"] > 0 and range_pct < 0.012:
            direction = "SHORT"
            score = oi_change / (range_pct + 0.001)

        else:
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
                "Status": "RUNNING",
                "Note": "⚡ PRE-BLAST (15–20 MIN)"
            }
            best_score = score

    return best

# ================= STATUS UPDATE =================
def update_status(trade, price):
    if trade["Status"] != "RUNNING":
        return

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

# ================= UI =================
st.markdown("## 💣 BLAST FUTURES SCANNER (15–20 Min)")

trades = load_json(DATA_FILE, [])
oi_prev = load_json(OI_FILE, {})

df = prepare_df(fetch_data())
price_map = dict(zip(df["Symbol"], df["Price"]))

for t in trades:
    if t["Status"] == "RUNNING" and t["Symbol"] in price_map:
        update_status(t, price_map[t["Symbol"]])

save_json(DATA_FILE, trades)
save_json(OI_FILE, dict(zip(df["Symbol"], df["OI"])))


st.caption(f"📊 Markets scanned: {len(df)}")

# ================= GET BLAST =================
if st.button("🔥 GET BLAST SIGNAL", use_container_width=True):
    trade = find_blast_trade(df, oi_prev)
    if trade:
        trades.insert(0, trade)
        save_json(DATA_FILE, trades)
        st.success("💣 PRE-BLAST TRADE FOUND")
    else:
        st.warning("❌ No blast setup right now")

st.divider()

# ================= RUNNING =================
st.subheader("🟢 RUNNING BLAST TRADES")
running = [t for t in trades if t["Status"] == "RUNNING"]

if not running:
    st.info("No running blast trades")
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
            save_json(DATA_FILE, trades)
            st.rerun()

st.divider()

# ================= HISTORY =================
st.subheader("📜 BLAST SCAN HISTORY")
if trades:
    st.dataframe(pd.DataFrame(trades), use_container_width=True)
else:
    st.info("No blast trades yet")

st.caption("⚠️ High-risk strategy | Futures only | Use risk management")
