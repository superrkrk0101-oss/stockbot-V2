import os
import yfinance as yf
import google.generativeai as genai
import requests
import time

# 1. 환경 설정 (비밀 금고 데이터)
DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK_URL')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

# 제미나이 설정
genai.configure(api_key=GEMINI_API_KEY)

def get_best_model():
    """구글 서버에서 현재 사용 가능한 최적의 모델 이름을 자동으로 찾아옵니다."""
    try:
        for m in genai.list_models():
            # 'flash' 모델 중 콘텐츠 생성이 가능한 가장 최신 모델을 고릅니다.
            if 'flash' in m.name.lower() and 'generateContent' in m.supported_generation_methods:
                return m.name
    except:
        pass
    # 만약 목록 조회가 안 되면 가장 표준적인 이름을 반환합니다.
    return 'models/gemini-1.5-flash'

def send_discord(message):
    if DISCORD_WEBHOOK_URL:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": message})

def run_analysis():
    # 준희님이 투자 중인 종목들 (NVDA, PLTR, JEPI 등)
    tickers = ['NVDA', 'PLTR', 'LUNR', 'CEG', 'SERV', 'META', 'JEPI']
    
    # 서버에서 모델 이름을 자동으로 가져옵니다.
    target_model = get_best_model()
    
    try:
        model = genai.GenerativeModel(target_model)
    except Exception as e:
        send_discord(f"🚨 모델 연결 불가: {e}")
        return

    # 리포트 시작 (사용 중인 엔진 이름을 표시해줍니다)
    report = f"☀️ **2026 미국 주식 모닝 브리핑 (엔진: {target_model.split('/')[-1]})** ☀️\n\n"
    
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
            news_str = " / ".join(filter(None, titles)) or "최근 뉴스 없음"

            # AI 분석 요청
            prompt = f"{ticker}(${price:.2f}, {change:+.2f}%)와 뉴스({news_str})를 보고 오늘 투자자가 알아야 할 핵심을 2문장으로 요약해줘."
            
            response = model.generate_content(prompt)
            report += f"📊 **{ticker}**: {response.text.strip()}\n\n"
            
            # 구글 서버에 무리가 가지 않게 2초씩 쉬어줍니다.
            time.sleep(2)
            
        except Exception as e:
            report += f"📊 **{ticker}**: 분석 스킵 (사유: {str(e)[:30]})\n\n"

    send_discord(report)

if __name__ == "__main__":
    run_analysis()
