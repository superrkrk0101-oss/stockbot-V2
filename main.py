import os
import yfinance as yf
import google.generativeai as genai
from groq import Groq
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
import time

# 환경 변수 로드
DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK_URL')
GEMINI_KEY = os.environ.get('GEMINI_API_KEY')
GROQ_KEY = os.environ.get('GROQ_API_KEY')

TICKERS = ['NVDA', 'TSLA', 'CRCL', 'CEG', 'WCC', 'SERV', 'LUNR']
PEERS = {'NVDA': 'AMD', 'TSLA': 'BYD', 'CRCL': 'COIN', 'CEG': 'VST', 'WCC': 'GWW', 'SERV': 'AMZN', 'LUNR': 'RKLB'}

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    loss = loss.replace(0, 0.001)
    return 100 - (100 / (1 + (gain / loss)))

def get_stock_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="100d")
        if df.empty or len(df) < 30: return None
        curr, prev = df.iloc[-1], df.iloc[-2]
        return {
            'ticker': ticker, 'price': round(curr['Close'], 2), 
            'change': round(((curr['Close'] - prev['Close']) / prev['Close']) * 100, 2),
            'ma5': round(df['Close'].rolling(5).mean().iloc[-1], 2),
            'ma20': round(df['Close'].rolling(20).mean().iloc[-1], 2),
            'rsi': round(calculate_rsi(df['Close']).iloc[-1], 2),
            'vol': round((curr['Volume'] / df['Volume'].tail(20).mean()) * 100, 1),
            'peer': PEERS.get(ticker, "시장 주도주")
        }
    except: return None

def get_ai_analysis(data):
    prompt = f"애널리스트로서 {data['ticker']} 분석: 현재가 ${data['price']}({data['change']}%), RSI {data['rsi']}, 거래량 {data['vol']}%. 한자 없이 한국어 존댓말로 ▶기술적 지표, ▶시장 상황, ▶향후 전망 위주로 핵심 요약하세요."
    
    # Gemini 우선
    if GEMINI_KEY:
        try:
            genai.configure(api_key=GEMINI_KEY)
            res = genai.GenerativeModel('gemini-1.5-flash').generate_content(prompt)
            if res.text: return res.text.strip(), "Gemini"
        except: pass
    # Groq 백업
    if GROQ_KEY:
        try:
            res = Groq(api_key=GROQ_KEY).chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}])
            return res.choices[0].message.content.strip(), "Groq"
        except: pass
    return "분석 실패", "None"

def main():
    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst)
    requests.post(DISCORD_WEBHOOK_URL, json={"content": f"🚀 **모닝 리포트 | {now.strftime('%Y-%m-%d %H:%M')}**\n━━━━━━━━━━━━━━━━━━━━━━━━"})
    
    for ticker in TICKERS:
        data = get_stock_data(ticker)
        if data:
            analysis, engine = get_ai_analysis(data)
            emoji = '📈' if data['change'] >= 0 else '📉'
            report = f"### {emoji} {data['ticker']} | `${data['price']}` ({data['change']}%)\n> **엔진**: `{engine}`\n{analysis}\n────────────────────"
            requests.post(DISCORD_WEBHOOK_URL, json={"content": report})
            time.sleep(1)

if __name__ == "__main__":
    main()
