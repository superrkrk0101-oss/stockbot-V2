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
PEERS = {
    'NVDA': 'AMD', 'TSLA': None, 'CEG': 'VST', 
    'WCC': 'GWW', 'SERV': 'AMZN', 'LUNR': 'RKLB'
}

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def get_stock_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="150d")
        if df.empty or len(df) < 120: return None

        info = stock.info
        curr = df.iloc[-1]
        prev = df.iloc[-2]
        
        price = round(curr['Close'], 2)
        change = round(((curr['Close'] - prev['Close']) / prev['Close']) * 100, 2)
        
        ma_data = {
            '5': round(df['Close'].rolling(window=5).mean().iloc[-1], 2),
            '20': round(df['Close'].rolling(window=20).mean().iloc[-1], 2),
            '60': round(df['Close'].rolling(window=60).mean().iloc[-1], 2),
            '120': round(df['Close'].rolling(window=120).mean().iloc[-1], 2)
        }
        rsi = round(calculate_rsi(df['Close']).iloc[-1], 2)
        vol_ratio = round((curr['Volume'] / df['Volume'].tail(20).mean()) * 100, 1)

        p_ticker = PEERS.get(ticker)
        peer_info = "N/A (Dominant Market Position)"
        if p_ticker:
            p_hist = yf.Ticker(p_ticker).history(period="2d")
            if not p_hist.empty:
                p_chg = round(((p_hist['Close'].iloc[-1] - p_hist['Close'].iloc[-2]) / p_hist['Close'].iloc[-2]) * 100, 2)
                peer_info = f"{p_ticker} ({'+' if p_chg > 0 else ''}{p_chg}%)"

        news = " / ".join([n.get('title', '') for n in stock.news[:3]])

        return {
            'ticker': ticker, 'price': price, 'change': change,
            'ma': ma_data, 'rsi': rsi, 'vol_ratio': vol_ratio, 
            'peer': peer_info, 'eps': info.get('trailingEps', 0), 
            'pe': info.get('trailingPE', 0), 'news': news
        }
    except Exception as e:
        print(f"{ticker} Error: {e}")
        return None

def get_ai_analysis(data):
    """분석 결과는 100% 영문으로 수행 (V7.5 로직 유지)"""
    sign = "+" if data['change'] > 0 else ""
    
    prompt = f"""
    You are a Senior Wall Street Analyst. 
    Analyze the following stock data and provide a professional report STRICTLY in English.

    [STOCK DATA]
    - Ticker: {data['ticker']} / Current Price: ${data['price']} ({sign}{data['change']}%)
    - Moving Averages: 5D(${data['ma']['5']}), 20D(${data['ma']['20']}), 60D(${data['ma']['60']}), 120D(${data['ma']['120']})
    - RSI: {data['rsi']} / Volume Ratio: {data['vol_ratio']}%
    - Peer Comparison: {data['peer']}
    - Fundamentals: EPS {data['eps']}, P/E {data['pe']}
    - Recent News: {data['news']}

    [OUTPUT RULES]
    1. Output MUST BE 100% in ENGLISH only.
    2. No other languages allowed.
    3. Use professional and concise terminology.

    [OUTPUT FORMAT]
    ▶ **Technical Perspective**: 
    ▶ **Market & Peer Context**: 
    ▶ **Valuation Analysis**: 
    ▶ **Risks & Outlook**: 
    """
    
    if GEMINI_KEY:
        try:
            genai.configure(api_key=GEMINI_KEY)
            model = genai.GenerativeModel('gemini-1.5-flash')
            res = model.generate_content(prompt)
            return res.text, "Gemini"
        except: pass

    if GROQ_KEY:
        try:
            client = Groq(api_key=GROQ_KEY)
            comp = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}]
            )
            return comp.choices[0].message.content, "Groq"
        except: pass
    
    return "Analysis generation failed.", "None"

def send_to_discord(message):
    if DISCORD_WEBHOOK_URL:
        for i in range(0, len(message), 1900):
            requests.post(DISCORD_WEBHOOK_URL, json={"content": message[i:i+1900]})

def main():
    # 현재 날짜와 시간 가져오기
    now = datetime.now()
    date_str = now.strftime('%Y-%m-%d')
    time_str = now.strftime('%H:%M:%S')
    
    # 헤더에 시간 추가 (V7.6)
    header = f"🚀 **{date_str} {time_str} Wall Street Morning Report (V7.6)**\n"
    header += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    send_to_discord(header)

    for ticker in TICKERS:
        data = get_stock_data(ticker)
        if data:
            analysis_text, engine = get_ai_analysis(data)
            sign = "+" if data['change'] > 0 else ""
            emoji = "📈" if data['change'] >= 0 else "📉"
            
            report = f"### {emoji} {data['ticker']} | `${data['price']}` ({sign}{data['change']}%)\n"
            report += f"> **Analysis Engine**: `{engine}`\n"
            report += f"{analysis_text.strip()}\n"
            report += "────────────────────────────────────\n"
            
            send_to_discord(report)
            time.sleep(1)

if __name__ == "__main__":
    main()
