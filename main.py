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
        
        ma5 = round(df['Close'].rolling(window=5).mean().iloc[-1], 2)
        ma20 = round(df['Close'].rolling(window=20).mean().iloc[-1], 2)
        ma60 = round(df['Close'].rolling(window=60).mean().iloc[-1], 2)
        ma120 = round(df['Close'].rolling(window=120).mean().iloc[-1], 2)
        rsi = round(calculate_rsi(df['Close']).iloc[-1], 2)
        
        avg_vol_20 = df['Volume'].tail(20).mean()
        vol_ratio = round((curr['Volume'] / avg_vol_20) * 100, 1)

        eps = info.get('trailingEps', 0)
        pe_ratio = info.get('trailingPE', 0)
        
        p_ticker = PEERS.get(ticker)
        peer_info = "비교 대상 없음"
        if p_ticker:
            p_hist = yf.Ticker(p_ticker).history(period="2d")
            if not p_hist.empty:
                p_change = round(((p_hist['Close'].iloc[-1] - p_hist['Close'].iloc[-2]) / p_hist['Close'].iloc[-2]) * 100, 2)
                p_sign = "+" if p_change > 0 else ""
                peer_info = f"{p_ticker} ({p_sign}{p_change}%)"

        news = " / ".join([n.get('title', '') for n in stock.news[:3]])

        return {
            'ticker': ticker, 'price': price, 'change': change,
            'ma': {'5': ma5, '20': ma20, '60': ma60, '120': ma120},
            'rsi': rsi, 'vol_ratio': vol_ratio, 'peer': peer_info,
            'eps': eps, 'pe': pe_ratio, 'news': news
        }
    except Exception as e:
        print(f"{ticker} 데이터 수집 중 에러: {e}")
        return None

def get_ai_analysis(data):
    sign = "+" if data['change'] > 0 else ""
    
    # [프롬프트 대폭 수정] 한자 금지 및 시각화 구조 강제
    prompt = f"""
    당신은 월스트리트의 시니어 수석 애널리스트입니다. 
    다음 데이터를 바탕으로 {data['ticker']} 종목에 대한 분석 리포트를 작성하세요.

    [데이터 정보]
    - 티커: {data['ticker']} / 현재가: ${data['price']} ({sign}{data['change']}%)
    - 이동평균선: 5일(${data['ma']['5']}), 20일(${data['ma']['20']}), 60일(${data['ma']['60']}), 120일(${data['ma']['120']})
    - RSI: {data['rsi']} / 거래량 비율: {data['vol_ratio']}%
    - 경쟁사({data['peer']}) 대비 성과
    - 재무상태: EPS {data['eps']}, P/E {data['pe']}
    - 핵심 뉴스: {data['news']}

    [작성 규칙 - 필독]
    1. **한자 절대 금지**: 모든 한자(예: 變化, 競爭, 壓力)를 한글로만 적으세요.
    2. **가시성 최우선**: 줄글로 길게 쓰지 말고, 아래의 [출력 형식]을 반드시 따르세요.
    3. **전문성**: 수치에 기반하여 냉철하게 분석하되, 부드러운 존댓말을 사용하세요.
    4. 분석 내용만 출력하고, 인사말이나 "분석 결과입니다" 같은 서론은 생략하세요.

    [출력 형식]
    ▶ **기술적 관점**: (이평선 정배열 여부, 거래량 신뢰도, RSI를 이용한 과매수/과매도 분석)
    ▶ **시장 및 경쟁**: (경쟁사 대비 성과 및 시장 내 위치 분석)
    ▶ **밸류에이션**: (현재 주가가 실적 대비 저평가인지 고평가인지 판단)
    ▶ **리스크 및 전망**: (단기 주의 사항 및 향후 주가 방향성)
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
    
    return "분석 생성에 실패했습니다.", "None"

def send_to_discord(message):
    if DISCORD_WEBHOOK_URL:
        for i in range(0, len(message), 1900):
            requests.post(DISCORD_WEBHOOK_URL, json={"content": message[i:i+1900]})

def main():
    today = datetime.now().strftime('%Y-%m-%d')
    header = f"🚀 **{today} 월스트리트 모닝 리포트 (V7.3)**\n"
    header += "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    send_to_discord(header)

    for ticker in TICKERS:
        data = get_stock_data(ticker)
        if data:
            analysis_text, engine = get_ai_analysis(data)
            sign = "+" if data['change'] > 0 else ""
            emoji = "📈" if data['change'] >= 0 else "📉"
            
            # 리포트 가시성 강화
            stock_report = f"### {emoji} {data['ticker']} | `${data['price']}` ({sign}{data['change']}%)\n"
            stock_report += f"> **분석 엔진**: `{engine}`\n"
            stock_report += f"{analysis_text.strip()}\n"
            stock_report += "\n"
            
            send_to_discord(stock_report)
            time.sleep(1)

if __name__ == "__main__":
    main()
