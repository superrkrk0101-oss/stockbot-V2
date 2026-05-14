import os
import yfinance as yf
import google.generativeai as genai
import requests
import time

# 1. 환경 설정
DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK_URL')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

genai.configure(api_key=GEMINI_API_KEY)

def get_best_model():
    """현재 사용 가능한 최적의 모델을 자동으로 찾습니다."""
    try:
        for m in genai.list_models():
            if 'flash' in m.name.lower() and 'generateContent' in m.supported_generation_methods:
                return m.name
    except: pass
    return 'models/gemini-1.5-flash'

def send_discord(message):
    if DISCORD_WEBHOOK_URL:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": message})

def run_analysis():
    tickers = ['NVDA', 'PLTR', 'LUNR', 'CEG', 'SERV', 'META', 'JEPI']
    target_model = get_best_model()
    model = genai.GenerativeModel(target_model)

    report = f"☀️ **2026 미국 주식 모닝 리포트** ☀️\n"
    report += f"*(분석 엔진: {target_model.split('/')[-1]})*\n\n"
    
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="2d")
            if hist.empty: continue
            
            curr_p = hist['Close'].iloc[-1]
            prev_p = hist['Close'].iloc[-2]
            change = ((curr_p - prev_p) / prev_p) * 100
            volume = hist['Volume'].iloc[-1] # 거래량 데이터 추출
            
            news = stock.news
            titles = [n.get('title') or n.get('content', {}).get('title', '') for n in news[:2]]
            news_str = " / ".join(filter(None, titles)) or "최근 뉴스 없음"

            # 가시성을 극대화한 프롬프트 설계
            prompt = f"""
            주식 전문가로서 {ticker}를 분석하세요.
            [데이터] 현재가: ${curr_p:.2f} ({change:+.2f}%), 거래량: {volume:,}주, 주요뉴스: {news_str}
            
            아래 형식을 엄격히 지켜 답변하세요:
            • **시장 팩트**: 가격 변동과 거래량 수치가 갖는 의미를 한 줄 요약.
            • **핵심 이슈**: 뉴스나 섹터 호재가 미친 영향 분석.
            • **투자 관점**: 오늘 투자자가 주의 깊게 봐야 할 포인트.
            """
            
            response = model.generate_content(prompt)
            
            # 종목별 가독성 높은 포맷 구성
            report += f"━━━━━━━━━━━━━━━━━━\n"
            report += f"### 📊 **{ticker}** | ${curr_p:.2f} ({change:+.2f}%)\n"
            report += f"{response.text.strip()}\n\n"
            
            # 429 에러 방지를 위해 휴식 시간을 5초로 연장
            time.sleep(5)
            
        except Exception as e:
            report += f"📊 **{ticker}**: 분석 스킵 (사유: {str(e)[:30]})\n\n"

    send_discord(report)

if __name__ == "__main__":
    run_analysis()
