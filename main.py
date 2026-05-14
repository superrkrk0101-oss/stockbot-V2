import os
import yfinance as yf
import google.generativeai as genai
from groq import Groq
import requests
import pandas as pd
from datetime import datetime

# API 설정
DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK_URL')
GEMINI_KEY = os.environ.get('GEMINI_API_KEY')
GROQ_KEY = os.environ.get('GROQ_API_KEY')

# [수정] 분석 종목 및 경쟁사 설정
TICKERS = ['NVDA', 'TSLA', 'CEG', 'WCC', 'SERV', 'LUNR']
PEERS = {
    'NVDA': 'AMD', 
    'TSLA': None,    # 경쟁사 비교 제거 (독자적 분석)
    'CEG': 'VST', 
    'WCC': 'GWW', 
    'SERV': 'AMZN', 
    'LUNR': 'RKLB'   # 경쟁사 SPCE -> RKLB 수정
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
        
        # 기술적 지표
        ma5 = df['Close'].rolling(window=5).mean().iloc[-1]
        ma20 = df['Close'].rolling(window=20).mean().iloc[-1]
        ma60 = df['Close'].rolling(window=60).mean().iloc[-1]
        ma120 = df['Close'].rolling(window=120).mean().iloc[-1]
        rsi = round(calculate_rsi(df['Close']).iloc[-1], 2)
        
        avg_vol_20 = df['Volume'].tail(20).mean()
        vol_ratio = round((curr['Volume'] / avg_vol_20) * 100, 1)

        # 재무 지표
        eps = info.get('trailingEps', 0)
        pe_ratio = info.get('trailingPE', 0)
        fair_value = round(eps * pe_ratio, 2) if eps and pe_ratio else 0

        # [수정] 경쟁사 동향 로직
        p_ticker = PEERS.get(ticker)
        peer_info = "독보적 시장 지위(비교 대상 없음)"
        if p_ticker:
            p_hist = yf.Ticker(p_ticker).history(period="2d")
            if not p_hist.empty:
                p_change = round(((p_hist['Close'].iloc[-1] - p_hist['Close'].iloc[-2]) / p_hist['Close'].iloc[-2]) * 100, 2)
                p_sign = "+" if p_change > 0 else ""
                peer_info = f"{p_ticker}({p_sign}{p_change}%)"

        news = " / ".join([n.get('title', '') for n in stock.news[:3]])

        return {
            'ticker': ticker, 'price': price, 'change': change,
            'ma': {'5': ma5, '20': ma20, '60': ma60, '120': ma120},
            'rsi': rsi, 'vol_ratio': vol_ratio, 'peer': peer_info,
            'eps': eps, 'pe': pe_ratio, 'fair_value': fair_value, 'news': news
        }
    except Exception as e:
        print(f"{ticker} 데이터 수집 중 에러: {e}")
        return None

def get_professional_analysis(data_list):
    prompt = f"""
    당신은 월스트리트 시니어 애널리스트입니다. 아래 데이터를 바탕으로 전문 리포트를 '한국어'로 작성하세요.
    외국어나 한자 혼용을 절대 금지하며 100% 순수 한국어 금융 용어만 사용하세요.

    데이터:
    {data_list}

    [필수 항목]
    1. 투자 핵심 요약: 투자의견 및 주요 뉴스.
    2. 기술적 지표 분석: 이평선 정배열/역배열, 거래량 신뢰도, RSI 위치.
    3. 기본적 분석 및 밸류에이션: $Fair Value = EPS \\times Target P/E$ 관점의 분석.
    4. 시장 맥락: 경쟁사 수익률과의 비교(경쟁사가 없는 경우 시장 지배력 분석).
    5. 향후 전망 및 리스크 관리 전략.
    """
    
    # Gemini -> Groq 순차 호출
    if GEMINI_KEY:
        try:
            genai.configure(api_key=GEMINI_KEY)
            model = genai.GenerativeModel('gemini-1.5-flash')
            res = model.generate_content(prompt)
            if res.text: return res.text, "Gemini"
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
    
    return None, "모든 엔진 실패"

def main():
    today = datetime.now().strftime('%Y-%m-%d')
    header = f"📊 **{today} 월스트리트 모닝 리포트 (V7.1)**\n━━━━━━━━━━━━━━━━━━━━\n"
    
    stock_results = []
    for ticker in TICKERS:
        data = get_stock_data(ticker)
        if data: stock_results.append(data)

    analysis_txt, engine = get_professional_analysis(stock_results)
    final_report = header + f"💡 **분석 엔진:** `{engine}`\n\n"
    
    for stock in stock_results:
        sign = "+" if stock['change'] > 0 else ""
        emoji = "📈" if stock['change'] >= 0 else "📉"
        
        content = "분석 생성 실패"
        # 티커별 블록 파싱 (대소문자 구분 없이)
        for block in analysis_txt.split('\n\n'):
            if stock['ticker'].upper() in block.upper():
                content = block.split(':', 1)[-1].strip() if ':' in block else block
                break

        final_report += f"### {emoji} {stock['ticker']} | `${stock['price']}` ({sign}{stock['change']}%)\n"
        final_report += f"{content}\n\n"

    send_to_discord(final_report + "━━━━━━━━━━━━━━━━━━━━")

def send_to_discord(message):
    if DISCORD_WEBHOOK_URL:
        for i in range(0, len(message), 1900):
            requests.post(DISCORD_WEBHOOK_URL, json={"content": message[i:i+1900]})

if __name__ == "__main__":
    main()
