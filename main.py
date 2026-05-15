import os
import yfinance as yf
import google.generativeai as genai
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
import time

# 환경 변수 로드 (그록 제거)
DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK_URL')
GEMINI_KEY = os.environ.get('GEMINI_API_KEY')

# 분석 대상을 CRCL 단일 종목으로 변경
TICKERS = ['CRCL']

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
            'vol': round((curr['Volume'] / df['Volume'].tail(20).mean()) * 100, 1)
        }
    except: return None

def get_ai_analysis(data):
    # 제미나이의 깊이 있는 분석을 유도하는 프롬프트
    prompt = (
        f"당신은 월스트리트의 수석 애널리스트입니다. {data['ticker']} 종목을 정밀 분석하세요.\n"
        f"현재가: ${data['price']} ({data['change']}%)\n"
        f"RSI: {data['rsi']}, 거래량 비율: {data['vol']}%\n\n"
        "다음 세 가지 관점에서 한국어 존댓말로 핵심을 짚어주세요:\n"
        "1. 기술적 지표 해석 (현재 주가 위치와 에너지)\n"
        "2. 현재 시장 상황과 연계된 분석\n"
        "3. 단기 및 중장기 향후 전망과 대응 전략\n"
        "한자는 사용하지 마세요."
    )
    
    if GEMINI_KEY:
        try:
            genai.configure(api_key=GEMINI_KEY)
            # 장기 기억한 대로 2.0-flash 모델 사용
            model = genai.GenerativeModel('gemini-2.0-flash')
            res = model.generate_content(prompt)
            if res.text: 
                return res.text.strip(), "Gemini 2.0 Flash"
        except Exception as e:
            return f"Gemini 분석 중 오류 발생: {e}", "Gemini_Error"
            
    return "API 키를 확인해주세요.", "None"

def main():
    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst)
    requests.post(DISCORD_WEBHOOK_URL, json={"content": f"🎯 **Gemini 단독 정밀 분석 리포트 | {now.strftime('%Y-%m-%d %H:%M')}**\n━━━━━━━━━━━━━━━━━━━━━━━━"})
    
    for ticker in TICKERS:
        data = get_stock_data(ticker)
        if data:
            analysis, engine = get_ai_analysis(data)
            emoji = '📈' if data['change'] >= 0 else '📉'
            report = f"### {emoji} {data['ticker']} 정밀 리포트\n> **분석 엔진**: `{engine}`\n\n{analysis}\n────────────────────"
            requests.post(DISCORD_WEBHOOK_URL, json={"content": report})

if __name__ == "__main__":
    main()
