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
    'NVDA': 'AMD', 
    'TSLA': None, 
    'CEG': 'VST', 
    'WCC': 'GWW', 
    'SERV': 'AMZN', 
    'LUNR': 'RKLB'
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
        
        # 이동평균선 계산
        ma5 = round(df['Close'].rolling(window=5).mean().iloc[-1], 2)
        ma20 = round(df['Close'].rolling(window=20).mean().iloc[-1], 2)
        ma60 = round(df['Close'].rolling(window=60).mean().iloc[-1], 2)
        ma120 = round(df['Close'].rolling(window=120).mean().iloc[-1], 2)
        rsi = round(calculate_rsi(df['Close']).iloc[-1], 2)
        
        avg_vol_20 = df['Volume'].tail(20).mean()
        vol_ratio = round((curr['Volume'] / avg_vol_20) * 100, 1)

        eps = info.get('trailingEps', 0)
        pe_ratio = info.get('trailingPE', 0)
        
        # 경쟁사 데이터
        p_ticker = PEERS.get(ticker)
        peer_info = "비교 대상 없음(독보적 지위)"
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
    """개별 종목에 대해 AI 분석 수행"""
    sign = "+" if data['change'] > 0 else ""
    
    prompt = f"""
    당신은 월스트리트의 시니어 수석 애널리스트입니다. 
    다음 데이터를 바탕으로 {data['ticker']} 종목에 대한 심층 분석 리포트를 작성하세요.
    
    [데이터]
    - 종목: {data['ticker']} / 현재가: ${data['price']} ({sign}{data['change']}%)
    - 이동평균선: 5일(${data['ma']['5']}), 20일(${data['ma']['20']}), 60일(${data['ma']['60']}), 120일(${data['ma']['120']})
    - RSI: {data['rsi']} / 거래량 비율: {data['vol_ratio']}%
    - 경쟁사 동향: {data['peer']}
    - 재무: EPS {data['eps']}, P/E {data['pe']}
    - 주요 뉴스: {data['news']}

    [작성 가이드라인]
    1. 말투: 전문적이고 냉철한 분석가의 톤 (경어체 사용).
    2. 필수 내용:
       - 거래량과 이동평균선을 결합한 기술적 추세 해석.
       - 경쟁사 수익률 대비 해당 종목의 강세/약세 원인 분석.
       - 현재 가격이 펀더멘탈(EPS, P/E) 대비 적정한지에 대한 의견.
       - 투자자가 유의해야 할 단기 리스크와 향후 전망.
    3. 금지: 영어/한자 남발을 지양하고 깔끔한 한국어 금융 용어 사용.
    4. 분석 내용만 출력하고 서론(분석 대상은~ 등)은 절대 쓰지 마세요.
    """
    
    # AI 엔진 호출 로직 (Gemini 우선, 실패 시 Groq)
    if GEMINI_KEY:
        try:
            genai.configure(api_key=GEMINI_KEY)
            model = genai.GenerativeModel('gemini-1.5-flash')
            res = model.generate_content(prompt)
            return res.text, "Gemini"
        except Exception as e:
            print(f"Gemini 호출 실패: {e}")

    if GROQ_KEY:
        try:
            client = Groq(api_key=GROQ_KEY)
            comp = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}]
            )
            return comp.choices[0].message.content, "Groq"
        except Exception as e:
            print(f"Groq 호출 실패: {e}")
    
    return "분석 생성에 실패했습니다.", "None"

def send_to_discord(message):
    if DISCORD_WEBHOOK_URL:
        # 디스코드 글자 수 제한(2000자) 대응
        for i in range(0, len(message), 1900):
            requests.post(DISCORD_WEBHOOK_URL, json={"content": message[i:i+1900]})

def main():
    today = datetime.now().strftime('%Y-%m-%d')
    report_header = f"📊 **{today} 월스트리트 모닝 리포트 (V7.2)**\n"
    report_header += "━━━━━━━━━━━━━━━━━━━━\n"
    
    send_to_discord(report_header) # 헤더 먼저 전송

    for ticker in TICKERS:
        data = get_stock_data(ticker)
        if data:
            analysis_text, engine = get_ai_analysis(data)
            
            sign = "+" if data['change'] > 0 else ""
            emoji = "📈" if data['change'] >= 0 else "📉"
            
            # 종목별 블록 생성
            stock_report = f"### {emoji} {data['ticker']} | `${data['price']}` ({sign}{data['change']}%)\n"
            stock_report += f"**[엔진: {engine}]**\n"
            stock_report += f"{analysis_text}\n"
            stock_report += "────────────────────\n"
            
            send_to_discord(stock_report)
            time.sleep(1) # API 레이트 리밋 방지

if __name__ == "__main__":
    main()
