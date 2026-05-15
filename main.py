import os
import yfinance as yf
import google.generativeai as genai
from groq import Groq
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
import time

# 1. API 및 환경 설정
DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK_URL')
GEMINI_KEY = os.environ.get('GEMINI_API_KEY')
GROQ_KEY = os.environ.get('GROQ_API_KEY')

# 분석 대상 및 경쟁사 매핑
TICKERS = ['NVDA', 'TSLA', 'CRCL','CEG', 'WCC', 'SERV', 'LUNR']
PEERS = {
    'NVDA': 'AMD', 'TSLA': None,'CRCL': None, 'CEG': 'VST', 
    'WCC': 'GWW', 'SERV': 'AMZN', 'LUNR': 'RKLB'
}

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def get_stock_data(ticker):
    """주식 데이터 수집 및 기술적 지표 계산"""
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="100d")
        if df.empty or len(df) < 60: return None

        curr, prev = df.iloc[-1], df.iloc[-2]
        change = round(((curr['Close'] - prev['Close']) / prev['Close']) * 100, 2)
        
        # 이동평균선 및 RSI
        ma = {
            '5': round(df['Close'].rolling(5).mean().iloc[-1], 2),
            '20': round(df['Close'].rolling(20).mean().iloc[-1], 2)
        }
        rsi = round(calculate_rsi(df['Close']).iloc[-1], 2)
        vol_ratio = round((curr['Volume'] / df['Volume'].tail(20).mean()) * 100, 1)

        p_ticker = PEERS.get(ticker)
        peer_info = f"{p_ticker}" if p_ticker else "시장 주도주(비교 대상 없음)"

        return {
            'ticker': ticker, 'price': round(curr['Close'], 2), 'change': change,
            'ma': ma, 'rsi': rsi, 'vol': vol_ratio, 'peer': peer_info
        }
    except Exception as e:
        print(f"데이터 수집 오류 ({ticker}): {e}")
        return None

def get_ai_analysis(data):
    """AI 엔진을 사용한 한국어 전문 분석 (한자 제외)"""
    sign = "+" if data['change'] > 0 else ""
    
    prompt = f"""
    당신은 월스트리트의 수석 애널리스트입니다. 아래 데이터를 바탕으로 {data['ticker']} 종목을 분석하세요.
    
    [실시간 데이터]
    현재가: ${data['price']} ({sign}{data['change']}%)
    이동평균선: 5일(${data['ma']['5']}), 20일(${data['ma']['20']})
    RSI: {data['rsi']} / 거래량 비율: {data['vol']}%
    경쟁사 동향: {data['peer']}

    [작성 가이드라인]
    1. 반드시 '한국어'로만 답변하세요. 존댓말을 사용합니다.
    2. 한자(예: 變化, 壓力)를 절대 사용하지 마세요. 모든 단어는 한글로만 표기합니다.
    3. 가독성을 위해 불렛포인트(▶)를 사용하고 항목당 1~2문장으로 핵심만 짚으세요.
    4. 분석 내용만 출력하고 서론과 결론 인사는 생략하세요.

    [출력 포맷]
    ▶ **기술적 지표**: (추세 및 RSI 기반 해석)
    ▶ **시장 상황**: (경쟁사 대비 강점 또는 시장 위치)
    ▶ **향후 전망**: (단기 지지/저항선 및 대응 전략)
    """

    # 제미나이(Gemini) 우선 호출
    if GEMINI_KEY:
        try:
            genai.configure(api_key=GEMINI_KEY)
            model = genai.GenerativeModel('gemini-1.5-flash')
            res = model.generate_content(prompt)
            if res.text: return res.text, "Gemini"
        except Exception as e:
            print(f"Gemini 호출 실패: {e}")

    # 실패 시 Groq 백업 호출
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

    return "분석 생성에 실패했습니다. API 설정을 확인해주세요.", "None"

def send_to_discord(message):
    """디스코드 웹후크 전송 (글자 수 제한 대응)"""
    if DISCORD_WEBHOOK_URL:
        for i in range(0, len(message), 1900):
            requests.post(DISCORD_WEBHOOK_URL, json={"content": message[i:i+1900]})

def main():
    # 한국 표준시(KST) 설정
    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst)
    time_str = now.strftime('%Y-%m-%d %H:%M:%S')
    
    # 1. 헤더 생성 및 전송
    header = f"🚀 **월스트리트 모닝 리포트 (V8.0) | 분석 시각: {time_str}**\n"
    header += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    send_to_discord(header)
    
    # 2. 종목별 분석 수행
    for ticker in TICKERS:
        data = get_stock_data(ticker)
        if data:
            analysis, engine = get_ai_analysis(data)
            sign = "+" if data['change'] > 0 else ""
            emoji = '📈' if data['change'] >= 0 else '📉'
            
            # 리포트 블록 구성
            report = f"### {emoji} {data['ticker']} | `${data['price']}` ({sign}{data['change']}%)\n"
            report += f"> **분석 엔진**: `{engine}`\n"
            report += f"{analysis.strip()}\n"
            report += "────────────────────────────────────"
            
            send_to_discord(report)
            time.sleep(1) # API 레이트 리밋 방지

if __name__ == "__main__":
    main()
