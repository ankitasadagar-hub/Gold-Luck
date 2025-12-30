import streamlit as st
import requests
import pandas as pd
import yfinance as yf
import os
import json
from openai import OpenAI
from datetime import datetime

# --- 🔧 USER CONFIGURATION 🔧 ---
# ⚠️ PASTE YOUR KEYS HERE
GOLD_API_KEY = "" 
OPENROUTER_API_KEY = ""

AI_MODEL = "meta-llama/llama-3.1-8b-instruct"

# --- 📉 CALCULATION ENGINE ---
def calculate_landed_cost(spot_price_gram, tax_rate_percent=9.18, dealer_premium=0):
    base_price = spot_price_gram 
    taxed_price = base_price * (1 + (tax_rate_percent / 100))
    final_price = taxed_price * (1 + (dealer_premium / 100))
    return final_price

# --- 📡 DATA FETCHING ---
def get_market_data(premium_percent):
    headers = {"x-access-token": GOLD_API_KEY, "Content-Type": "application/json"}
    try:
        resp_gold = requests.get("https://www.goldapi.io/api/XAU/INR", headers=headers)
        resp_silver = requests.get("https://www.goldapi.io/api/XAG/INR", headers=headers)
        
        if resp_gold.status_code == 200 and resp_silver.status_code == 200:
            g_data = resp_gold.json()
            s_data = resp_silver.json()
            
            spot_gold_10g = g_data.get("price_gram_24k") * 10
            gold_price = calculate_landed_cost(spot_gold_10g, 9.2, premium_percent)
            
            spot_silver_1kg = s_data.get("price_gram_24k") * 1000
            silver_price = calculate_landed_cost(spot_silver_1kg, 9.2, premium_percent)
            
            return {"gold_price": gold_price, "silver_price": silver_price}
        else:
            st.error(f"API Error: GoldAPI returned status {resp_gold.status_code}")
            return None
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return None

def get_short_term_trends():
    try:
        tickers = yf.download("GC=F SI=F", period="1mo", interval="1d", progress=False)
        
        def analyze(series):
            if len(series) < 5: return 50, "NEUTRAL"
            sma_5 = series.rolling(window=5).mean().iloc[-1]
            current = series.iloc[-1]
            trend = "UP" if current > sma_5 else "DOWN"
            
            delta = series.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs)).iloc[-1]
            return rsi, trend

        # Handle yfinance multi-index columns safely
        try:
            g_close = tickers['Close']['GC=F']
            s_close = tickers['Close']['SI=F']
        except KeyError:
             # Fallback for different yfinance versions
            g_close = tickers.xs('GC=F', level=1, axis=1)['Close']
            s_close = tickers.xs('SI=F', level=1, axis=1)['Close']

        g_rsi, g_trend = analyze(g_close)
        s_rsi, s_trend = analyze(s_close)
        
        return {
            "gold_rsi": g_rsi, "gold_trend": g_trend,
            "silver_rsi": s_rsi, "silver_trend": s_trend
        }
    except Exception as e:
        st.warning(f"Trend Data Error: {e}")
        return {"gold_rsi": 50, "gold_trend": "NEUTRAL", "silver_rsi": 50, "silver_trend": "NEUTRAL"}

# --- 🧠 AI ENGINE ---
# --- 🧠 MICRO AI ENGINE (Token Optimized) ---
# --- 🧠 ROBUST AI ENGINE ---
# --- 🧠 ROBUST AI ENGINE (Fixed Prompt) ---
def ask_ai_mini(prices, trends):
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_API_KEY)
    
    # CHANGED: We removed the complex "Pipe | Format" instructions.
    # We now use a simple standard Q&A format.
    prompt = f"""
    Market Data:
    - Gold: {prices['gold_price']:.0f} (Trend: {trends['gold_trend']}, RSI: {trends['gold_rsi']:.0f})
    - Silver: {prices['silver_price']:.0f} (Trend: {trends['silver_trend']}, RSI: {trends['silver_rsi']:.0f})
    
    Task: Give a 1-word recommendation (BUY, SELL, or WAIT) and a 1-sentence reason.
    
    Reply exactly like this:
    Gold Rec: [BUY/WAIT/SELL]
    Gold Reason: [Reason here]
    Silver Rec: [BUY/WAIT/SELL]
    Silver Reason: [Reason here]
    """
    
    try:
        completion = client.chat.completions.create(
            model=AI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=80, 
        )
        
        raw_text = completion.choices[0].message.content
        
        # Simple Parser that looks for our keywords
        result = {}
        lines = raw_text.split('\n')
        for line in lines:
            if "Gold Rec:" in line: result['gold_verdict'] = line.split(':')[1].strip().upper()
            if "Gold Reason:" in line: result['gold_reason'] = line.split(':')[1].strip()
            if "Silver Rec:" in line: result['silver_verdict'] = line.split(':')[1].strip().upper()
            if "Silver Reason:" in line: result['silver_reason'] = line.split(':')[1].strip()
            
        # Fallback if AI fails to format perfectly
        if 'gold_verdict' not in result: result['gold_verdict'] = "WAIT"
        if 'gold_reason' not in result: result['gold_reason'] = "Market Uncertain"
        if 'silver_verdict' not in result: result['silver_verdict'] = "WAIT"
        if 'silver_reason' not in result: result['silver_reason'] = "Market Uncertain"
            
        return json.dumps(result)

    except Exception as e:
        return f"ERROR: {e}"

        
# --- 🖥️ UI ---
st.set_page_config(page_title="Gold Luck", page_icon="⚡")
st.title("⚡ Gold Luck ")

premium = st.slider("Jeweler Premium %", 0.0, 5.0, 0.0, 0.5)

# --- 🖥️ UI DISPLAY (Clean Version) ---
if st.button("🚀 Fetch Prediction"):
    with st.spinner("Analyzing Markets..."):
        prices = get_market_data(premium)
        trends = get_short_term_trends()
        
        if prices and trends:
            # PRICES DISPLAY
            c1, c2 = st.columns(2)
            c1.metric("Gold (10g)", f"₹{prices['gold_price']:,.0f}", f"{trends['gold_trend']} (RSI {trends['gold_rsi']:.0f})")
            c2.metric("Silver (1kg)", f"₹{prices['silver_price']:,.0f}", f"{trends['silver_trend']} (RSI {trends['silver_rsi']:.0f})")
            
            st.divider()
            
            # AI PREDICTION DISPLAY
            st.subheader("🤖 AI Prediction")
            ai_resp = ask_ai_mini(prices, trends)
            
            # Error Handling
            if not ai_resp or "ERROR" in ai_resp:
                st.error("AI Connection Failed. Please try again.")
                with st.expander("Debug Info"):
                    st.write(ai_resp)
            else:
                try:
                    advice = json.loads(ai_resp)
                    
                    col1, col2 = st.columns(2)
                    
                    # --- GOLD CARD ---
                    with col1:
                        with st.container(border=True):
                            st.markdown("### 🥇 GOLD")
                            verdict = advice.get('gold_verdict', 'WAIT')
                            reason = advice.get('gold_reason', 'No data')
                            
                            if "BUY" in verdict:
                                st.success(f"**VERDICT: {verdict}**")
                            elif "SELL" in verdict:
                                st.error(f"**VERDICT: {verdict}**")
                            else:
                                st.warning(f"**VERDICT: {verdict}**")
                            
                            st.info(f"📝 {reason}")

                    # --- SILVER CARD ---
                    with col2:
                        with st.container(border=True):
                            st.markdown("### 🥈 SILVER")
                            verdict = advice.get('silver_verdict', 'WAIT')
                            reason = advice.get('silver_reason', 'No data')
                            
                            if "BUY" in verdict:
                                st.success(f"**VERDICT: {verdict}**")
                            elif "SELL" in verdict:
                                st.error(f"**VERDICT: {verdict}**")
                            else:
                                st.warning(f"**VERDICT: {verdict}**")
                            
                            st.info(f"📝 {reason}")
                            
                except json.JSONDecodeError:
                    st.error("AI Response Error. Please click Fetch again.")
                    st.write("Raw Output:", ai_resp)