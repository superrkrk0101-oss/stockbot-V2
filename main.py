import os
import yfinance as yf
import google.generativeai as genai
from groq import Groq
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
import time

# 1. 환경 변수 설정 (GitHub Secrets에서 가져옴)
DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK_URL')
GEMINI_KEY = os.environ.get('GEMINI_API_KEY')
GROQ_KEY = os.environ.get('GROQ_API_KEY')

# 분석 대상 및 경쟁사 매핑
TICKERS = ['NVDA', 'TSLA', 'CRCL', 'CEG', 'WCC', 'SERV', 'LUNR']
PEERS = {
    'NVDA': 'AMD', 'TSLA': 'BYD', 'CRCL': 'COIN', 'CEG': 'VST', 
    'WCC': 'GWW', 'SERV': 'AMZN', 'LUNR': 'RKLB'
}

def calculate_rsi(series, period=14):
    """Wilder의 방식에 가까운 안정적인 RSI 계산"""
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    # 0으로 나누기 방지
    loss = loss.replace(0, 0.001)
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def get_stock_data(ticker):
    """주식 데이터 수집 및 지표 계산"""
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="100d")
        if df.empty or len(df) < 30: 
            return None

        curr = df.iloc[-1]
        prev = df.iloc[-2]
        change = round(((curr['Close'] - prev['Close']) / prev['Close']) * 100, 2)
        
        # 이동평균선 및 지표
        ma5 = round(df['Close'].rolling(5).mean().iloc[-1], 2)
        ma20 = round(df['Close'].rolling(20).mean().iloc[-1], 2)
        rsi = round(calculate_rsi(df['Close']).iloc[-1], 2)
        avg_vol = df['Volume'].tail(20).mean()
        vol_ratio = round((curr['Volume'] / avg_vol) * 100, 1) if avg_vol > 0 else 0

        p_ticker = PEERS.get(ticker)
        peer_info = f"{p_ticker}" if p_ticker else "시장 주도주"

        return {
            'ticker': ticker, 'price': round(curr['Close'], 2), 'change': change,
            'ma5': ma5, 'ma20': ma20, 'rsi': rsi, 'vol': vol_ratio, 'peer': peer_info
        }
    except Exception as e:
        print(f"데이터 수집 오류 ({ticker}): {e}")
        return None

def get_ai_analysis(data):
    """AI를 사용한 한국어 전문 분석"""
    sign = "+" if data['change'] > 0 else ""
    prompt = f"""
    당신은 월스트리트의 수석 애널리스트입니다. 아래 데이터를 바탕으로 {data['ticker']} 종목을 분석하세요.
    
    [실시간 데이터]
    현재가: ${data['price']} ({sign}{data['change']}%)
    이동평균선: 5일(${data['ma5']}), 20일(${data['ma20']})
    RSI: {data['rsi']} / 거래량 비율: {data['vol']}%
    경쟁사 동향: {data['peer']}

    [작성 가이드라인]
    1. 반드시 '한국어'로만 답변하세요. 존댓말을 사용합니다.
    2. 한자(예: 變化, 壓力)를 절대 사용하지 마세요. 모든 단어는 한글로만 표기합니다.
    3. 가독성을 위해 불렛포인트(▶)를 사용하고 핵심만 짚으세요.
    4. 분석 내용만 출력하세요.

    [출력 포맷]
    ▶ **기술적 지표**: (추세 및 RSI 해석)
    ▶ **시장 상황**: (경쟁사 대비 강점 또는 위치)
    ▶ **향후 전망**: (단기 지지/저항 및 대응 전략)
    """

    # 1순위: Gemini
    if GEMINI_KEY:
        try:
            genai.configure(api_key=GEMINI_KEY)
            model = genai.GenerativeModel('gemini-1.5-flash')
            res = model.generate_content(prompt)
            if res and res.text: 
                return res.text.strip(), "Gemini"
        except Exception:
            pass

    # 2순위: Groq (백업)
    if GROQ_KEY:
        try:
            client = Groq(api_key=GROQ_KEY)
            comp = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}]
            )
            return comp.choices[0].message.content.strip(), "Groq"
        except Exception:
            pass

    return "분석 생성에 실패했습니다.", "Error"

def send_to_discord(message):
    """디스코드 전송"""
    if DISCORD_WEBHOOK_URL:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": message})

def main():
    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst)
    
    header = f"🚀 **월스트리트 모닝 리포트 | {now.strftime('%Y-%m-%d %H:%M')}**\n"
    header += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    send_to_discord(header)
    
    for ticker in TICKERS:
        data = get_stock_data(ticker)
        if data:
            analysis, engine = get_ai_analysis(data)
            emoji = '📈' if data['change'] >= 0 else '📉'
            sign = "+" if data['change'] > 0 else ""
            
            report = f"### {emoji} {data['ticker']} | `${data['price']}` ({sign}{data['change']}%)\n"
            report += f"> **분석 엔진**: `{engine}`\n"
            report += f"{analysis}\n"
            report += "────────────────────────────────────"
            
            send_to_discord(report)
            time.sleep(1)

if __name__ == "__main__":
    main()
