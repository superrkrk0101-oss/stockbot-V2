import os
import yfinance as yf
import google.generativeai as genai
import requests
import time

# 1. 금고에서 열쇠 꺼내기
DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK_URL')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

# 제미나이 설정
genai.configure(api_key=GEMINI_API_KEY)

def send_discord(message):
    if DISCORD_WEBHOOK_URL:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": message})

def run_analysis():
    # 분석 종목
    tickers = ['NVDA', 'PLTR', 'LUNR', 'CEG', 'SERV', 'META', 'JEPI']
    
    # [핵심] 2026년 현재 가장 정확한 모델명은 'gemini-3-flash'입니다.
    try:
        model = genai.GenerativeModel('gemini-3-flash')
    except Exception as e:
        # 혹시라도 모델명이 또 바뀌었다면 에러를 디스코드에 출력
        send_discord(f"🚨 모델 연결 오류: {e}")
        return

    report = "☀️ **2026 미국 주식 모닝 브리핑** ☀️\n\n"
    
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="2d")
            if hist.empty: continue
            
            price = hist['Close'].iloc[-1]
            change = ((price - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100
            
            # 뉴스 수집
            news = stock.news
            titles = [n.get('title') or n.get('content', {}).get('title', '') for n in news[:2]]
            news_str = " / ".join(filter(None, titles)) or "뉴스 없음"

            # AI 분석 (제미나이 3 엔진 가동)
            prompt = f"{ticker}(${price:.2f}, {change:+.2f}%)와 뉴스({news_str})를 보고 투자 포인트를 2문장으로 요약해."
            
            response = model.generate_content(prompt)
            report += f"📊 **{ticker}**: {response.text.strip()}\n\n"
            
            time.sleep(1) # 안정적인 호출을 위해 1초 휴식
            
        except Exception as e:
            report += f"📊 **{ticker}**: 분석 스킵 ({str(e)[:20]})\n\n"

    send_discord(report)

if __name__ == "__main__":
    run_analysis()
