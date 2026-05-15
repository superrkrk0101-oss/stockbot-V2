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
    prompt = f"애널리스트로서 {data['ticker']} 분석: 현재가 ${data['price']}({data['change']}%), RSI {data['rsi']}, 거래량 {data['vol']}%. 한글로만 ▶기술적 지표, ▶시장 상황, ▶향후 전망 핵심 요약."
    
    # 1순위: Gemini (속도 제한에 걸릴 수 있음)
    if GEMINI_KEY:
        try:
            genai.configure(api_key=GEMINI_KEY)
            res = genai.GenerativeModel('gemini-2.0-flash').generate_content(prompt)
            if res.text: return res.text.strip(), "Gemini"
        except Exception as e:
            print(f"Gemini 한도 초과 또는 오류: {e}")
            pass # 실패 시 Groq으로 넘어감

    # 2순위: Groq (Gemini가 429 에러를 뱉을 때 구원투수 역할)
    if GROQ_KEY:
        try:
            res = Groq(api_key=GROQ_KEY).chat.completions.create(
                model="llama-3.3-70b-versatile", 
                messages=[{"role": "user", "content": prompt}]
            )
            return res.choices[0].message.content.strip(), "Groq"
        except: pass
        
    return "현재 모든 AI 엔진이 바쁩니다.", "None"

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
            # 💡 속도 제한(429)을 피하기 위해 간격을 8초로 늘렸습니다.
            time.sleep(8) 

if __name__ == "__main__":
    main()
