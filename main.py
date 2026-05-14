import os
import yfinance as yf
import google.generativeai as genai
import requests
import time

# 1. 환경 설정 (비밀 금고)
DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK_URL')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

# 제미나이 초기화
genai.configure(api_key=GEMINI_API_KEY)

def get_working_model():
    """2026년 기준 가장 안정적인 모델 호칭을 자동으로 찾습니다."""
    # 시도할 호칭 리스트 (최신 순)
    titles = ['gemini-2.0-flash', 'gemini-1.5-flash', 'models/gemini-1.5-flash']
    
    for title in titles:
        try:
            model = genai.GenerativeModel(title)
            # 아주 짧은 테스트로 모델 존재 여부 확인
            model.generate_content("hi", generation_config={"max_output_tokens": 1})
            print(f"✅ 연결 성공: {title}")
            return model
        except Exception:
            continue
    return None

def send_discord(message):
    if DISCORD_WEBHOOK_URL:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": message})

def run_analysis():
    # 준희님이 관심 가지시는 종목 리스트 (Veritas 분석 엔진 가동)
    tickers = ['NVDA', 'PLTR', 'LUNR', 'CEG', 'SERV', 'META', 'JEPI']
    
    model = get_working_model()
    if not model:
        send_discord("🚨 [시스템 오류] 제미나이 모델 주소를 찾을 수 없습니다. 라이브러리 버전을 확인해주세요.")
        return

    final_report = "☀️ **2026 Veritas 미국 주식 모닝 브리핑** ☀️\n\n"
    
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            # 최근 5일치 데이터를 가져와서 흐름 파악
            hist = stock.history(period="5d")
            if hist.empty: continue
            
            curr_price = hist['Close'].iloc[-1]
            prev_price = hist['Close'].iloc[-2]
            change = ((curr_price - prev_price) / prev_price) * 100
            
            # 뉴스 수집 (2026년 바뀐 뉴스 구조 대응)
            news_items = stock.news
            titles = [n.get('title') or n.get('content', {}).get('title', '') for n in news_items[:2]]
            news_summary = " / ".join(filter(None, titles)) or "주요 뉴스 없음"

            # 전문가 페르소나 주입
            prompt = f"""
            당신은 월가 출신의 투자 전문가입니다. 
            종목: {ticker} (현재가 ${curr_price:.2f}, 변동률 {change:+.2f}%)
            최근 뉴스: {news_summary}
            
            위 데이터를 보고 오늘 장의 핵심 관전 포인트를 2문장으로 아주 명료하게 분석하세요.
            """
            
            response = model.generate_content(prompt)
            final_report += f"📊 **{ticker}**: {response.text.strip()}\n\n"
            
            # API 과부하 방지를 위한 짧은 휴식
            time.sleep(1.5)
            
        except Exception as e:
            final_report += f"📊 **{ticker}**: 분석 스킵 (원인: {str(e)[:30]}...)\n\n"

    send_discord(final_report)

if __name__ == "__main__":
    run_analysis()
