import os
import yfinance as yf
import google.generativeai as genai
import requests
import time

# 1. 환경 설정 (깃허브 비밀 금고에서 데이터 호출)
DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK_URL')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

# 제미나이 초기화 (현재 가장 안정적인 설정)
genai.configure(api_key=GEMINI_API_KEY)

def send_discord(message):
    """디스코드 특정 채널로 메시지를 전송합니다."""
    if DISCORD_WEBHOOK_URL:
        try:
            requests.post(DISCORD_WEBHOOK_URL, json={"content": message})
        except Exception as e:
            print(f"디스코드 전송 실패: {e}")

def run_analysis():
    # 분석 종목 리스트
    tickers = ['NVDA', 'PLTR', 'LUNR', 'CEG', 'SERV', 'META', 'JEPI']
    
    # 모델 호출 (2026년 표준 모델인 gemini-1.5-flash 사용)
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
    except Exception as model_err:
        send_discord(f"🚨 [시스템 에러] 모델 연결 실패: {model_err}")
        return

    final_report = "☀️ **2026 미국 주식 모닝 브리핑** ☀️\n\n"
    
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            # 최근 2거래일 데이터를 가져와 변동률 계산
            hist = stock.history(period="2d")
            if hist.empty:
                final_report += f"📊 **{ticker}**: 주가 데이터를 찾을 수 없습니다.\n\n"
                continue
            
            curr_price = hist['Close'].iloc[-1]
            prev_price = hist['Close'].iloc[-2]
            change_percent = ((curr_price - prev_price) / prev_price) * 100
            
            # 뉴스 데이터 수집 및 제목 추출
            news_items = stock.news
            news_titles = []
            if news_items:
                for n in news_items[:2]:
                    # 최신 야후 파이낸스 뉴스 구조 대응
                    t = n.get('title') or (n.get('content') and n.get('content').get('title'))
                    if t: news_titles.append(t)
            news_summary = " / ".join(news_titles) if news_titles else "최근 주요 뉴스 없음"

            # 인공지능에게 분석 요청
            prompt = f"""
            당신은 객관적인 지표를 중시하는 주식 분석가입니다. 
            종목: {ticker} (현재가 ${curr_price:.2f}, 전일비 {change_percent:+.2f}%)
            뉴스: {news_summary}
            
            위 데이터를 바탕으로 투자자가 오늘 주목해야 할 기술적 흐름이나 이슈를 2문장으로 명확하게 요약하세요.
            """
            
            response = model.generate_content(prompt)
            final_report += f"📊 **{ticker}** (${curr_price:.2f}): {response.text.strip()}\n\n"
            
            # API 호출 간격 유지 (과부하 방지)
            time.sleep(2)
            
        except Exception as e:
            final_report += f"📊 **{ticker}**: 분석 중 오류 발생 (사유: {str(e)[:40]})\n\n"

    # 최종 결과 전송
    send_discord(final_report)

if __name__ == "__main__":
    run_analysis()
