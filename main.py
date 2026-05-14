import os
import yfinance as yf
import google.generativeai as genai
from groq import Groq
import requests
import pandas as pd
from datetime import datetime
import time

# API 설정 (환경 변수 확인 필요)
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
        peer_info = f"{p_ticker}" if p_ticker else "시장 주도주(비교 대상 없음)"
        return {'ticker': ticker, 'price': round(curr['Close'], 2), 'change': change, 'ma': ma, 'rsi': rsi, 'vol': vol_ratio, 'peer': peer_info}
    except: return None

def get_ai_analysis(data):
    sign = "+" if data['change'] > 0 else ""
    # [프롬프트 개선] 한국어 전용, 한자 절대 금지 지침 강화
    prompt = f"""
    당신은 월스트리트의 수석 애널리스트입니다. 아래 데이터를 바탕으로 {data['ticker']} 종목을 분석하세요.
    
    [데이터]
    현재가: ${data['price']} ({sign}{data['change']}%)
    이동평균선: 5일(${data['ma']['5']}), 20일(${data['ma']['20']})
    RSI: {data['rsi']} / 거래량 비율: {data['vol']}%
    경쟁사 동향: {data['peer']}

    [작성 규칙 - 엄격 준수]
    1. 반드시 '한국어'로만 답변하세요.
    2. 한자(예: 變化, 壓力)를 절대 사용하지 말고 순수 한글 금융 용어만 사용하세요.
    3. 아래의 [출력 형식]을 지키고 각 항목은 1~2문장으로 간결하게 작성하세요.
    4. 분석 내용만 출력하고 서론(인사말 등)은 생략하세요.

    [출력 형식]
    ▶ **기술적 지표**: (이평선 추세 및 RSI 과매수/과매도 분석)
    ▶ **시장 상황**: (경쟁사 대비 성과 및 시장 위치 분석)
    ▶ **향후 전망**: (단기적 주가 방향성 및 주목해야 할 지점)
    """
    
    # 1. 한국어 성능이 우수한 Gemini 우선 시도
    if GEMINI_KEY:
        try:
            genai.configure(api_key=GEMINI_KEY)
            model = genai.GenerativeModel('gemini-1.5-flash')
            res = model.generate_content(prompt)
            if res.text: return res.text, "Gemini"
        except: pass

    # 2. 백업용으로 Groq 시도
    if GROQ_KEY:
        try:
            client = Groq(api_key=GROQ_KEY)
            comp = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}]
            )
            return comp.choices[0].message.content, "Groq"
        except: pass

    return "분석 생성에 실패했습니다.", "None"

def send_to_discord(message):
    if DISCORD_WEBHOOK_URL:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": message})

def main():
    now = datetime.now()
    # 헤더에 현재 날짜와 시각 포함
    date_time = now.strftime('%Y-%m-%d %H:%M:%S')
    header = f"🚀 **{date_time} 월스트리트 모닝 리포트 (V7.9)**\n━━━━━━━━━━━━━━━━━━━━\n"
    send_to_discord(header)
    
    for ticker in TICKERS:
        data = get_stock_data(ticker)
        if data:
            analysis, engine = get_ai_analysis(data)
            sign = "+" if data['change'] > 0 else ""
            emoji = '📈' if data['change'] >= 0 else '📉'
            
            report = f"### {emoji} {data['ticker']} | `${data['price']}` ({sign}{data['change']}%)\n"
            report += f"> **분석 엔진**: `{engine}`\n"
            report += f"{analysis.strip()}\n"
            report += "────────────────────"
            
            send_to_discord(report)
            time.sleep(1)

if __name__ == "__main__":
    main()
