import os
import yfinance as yf
import google.generativeai as genai
from groq import Groq
import requests
import pandas as pd
from datetime import datetime
import time

# API 설정
DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK_URL')
GEMINI_KEY = os.environ.get('GEMINI_API_KEY')
GROQ_KEY = os.environ.get('GROQ_API_KEY')

TICKERS = ['NVDA', 'TSLA', 'CEG', 'WCC', 'SERV', 'LUNR']
PEERS = {'NVDA': 'AMD', 'TSLA': None, 'CEG': 'VST', 'WCC': 'GWW', 'SERV': 'AMZN', 'LUNR': 'RKLB'}

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def get_stock_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="100d")
        if df.empty or len(df) < 60: return None
        curr, prev = df.iloc[-1], df.iloc[-2]
        change = round(((curr['Close'] - prev['Close']) / prev['Close']) * 100, 2)
        ma = { '5': round(df['Close'].rolling(5).mean().iloc[-1], 2), '20': round(df['Close'].rolling(20).mean().iloc[-1], 2) }
        rsi = round(calculate_rsi(df['Close']).iloc[-1], 2)
        vol_ratio = round((curr['Volume'] / df['Volume'].tail(20).mean()) * 100, 1)
        p_ticker = PEERS.get(ticker)
        peer_info = f"{p_ticker}" if p_ticker else "Market Leader"
        return {'ticker': ticker, 'price': round(curr['Close'], 2), 'change': change, 'ma': ma, 'rsi': rsi, 'vol': vol_ratio, 'peer': peer_info}
    except: return None

def get_ai_analysis(data):
    sign = "+" if data['change'] > 0 else ""
    # 밸류에이션 제거 및 콤팩트한 프롬프트
    prompt = f"""
    Senior Analyst Mode: Analyze {data['ticker']} (${data['price']}, {sign}{data['change']}%).
    Data: MA5(${data['ma']['5']}), MA20(${data['ma']['20']}), RSI({data['rsi']}), Vol({data['vol']}%), Peer({data['peer']}).
    
    Rules: 100% English. Bullet points. No intro/outro.
    Format:
    ▶ **Technical**: (Trend & RSI focus)
    ▶ **Market**: (Relative strength vs {data['peer']})
    ▶ **Outlook**: (Next move & key level)
    """
    if GEMINI_KEY:
        try:
            genai.configure(api_key=GEMINI_KEY)
            res = genai.GenerativeModel('gemini-1.5-flash').generate_content(prompt)
            return res.text, "Gemini"
        except: pass
    return "Analysis failed.", "None"

def send_to_discord(message):
    if DISCORD_WEBHOOK_URL: requests.post(DISCORD_WEBHOOK_URL, json={"content": message})

def main():
    now = datetime.now()
    header = f"🚀 **{now.strftime('%Y-%m-%d %H:%M')} Morning Report (V7.7)**\n━━━━━━━━━━━━━━━━━━━━\n"
    send_to_discord(header)
    for ticker in TICKERS:
        data = get_stock_data(ticker)
        if data:
            analysis, engine = get_ai_analysis(data)
            sign = "+" if data['change'] > 0 else ""
            report = f"### {'📈' if data['change']>=0 else '📉'} {data['ticker']} | `${data['price']}` ({sign}{data['change']}%)\n{analysis.strip()}\n"
            send_to_discord(report)
            time.sleep(1)

if __name__ == "__main__": main()
