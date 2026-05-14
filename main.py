import os
import yfinance as yf
import google.generativeai as genai
import requests
from datetime import datetime
import pandas as pd

# 환경 설정
DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK_URL')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
genai.configure(api_key=GEMINI_API_KEY)

# 분석 대상 티커 (요청하신 신규 티커 + LUNR)
TICKERS = ['CEG', 'WCC', 'SERV', 'LUNR']

def get_best_model():
    """사용 가능한 최신 모델을 동적으로 선택합니다."""
    try:
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        target = 'models/gemini-3-flash'
        return target if target in available_models else available_models[0]
    except Exception:
        return 'gemini-1.5-flash'

def send_discord(message):
    """결과를 디스코드로 전송합니다."""
    if DISCORD_WEBHOOK_URL:
        try:
            requests.post(DISCORD_WEBHOOK_URL, json={"content": message})
        except Exception as e:
            print(f"디스코드 전송 실패: {e}")

def fetch_stock_data(ticker):
    """주가, 이동평균선, 뉴스 데이터를 수집합니다."""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="60d")
        
        if hist.empty or len(hist) < 20:
            return None, "데이터 부족 또는 티커 오류"

        close_price = round(hist['Close'].iloc[-1], 2)
        ma20 = round(hist['Close'].rolling(window=20).mean().iloc[-1], 2)
        ma50 = round(hist['Close'].rolling(window=50).mean().iloc[-1], 2)
        trend = "상승 추세" if close_price > ma20 else "조정/하락 추세"
        
        # 뉴스 데이터 수집 (구조 변경 완벽 대응)
        news_text = "최근 관련 뉴스 없음"
        try:
            if stock.news:
                titles = []
                for item in stock.news[:3]:
                    t = item.get('title') or item.get('content', {}).get('title')
                    if t: titles.append(t)
                if titles: news_text = " / ".join(titles)
        except:
            pass

        return {
            'close': close_price,
            'ma20': ma20,
            'ma50': ma50,
            'trend': trend,
            'news': news_text
        }, None
    except Exception as e:
        return None, str(e)

def run_analysis():
    model_name = get_best_model()
    model = genai.GenerativeModel(model_name)
    
    today = datetime.now().strftime('%Y-%m-%d')
    final_report = f"📅 **{today} 실시간 주식 분석 리포트**\n🤖 모델: `{model_name}`\n\n"
    
    success_count = 0
    for ticker in TICKERS:
        data, error = fetch_stock_data(ticker)
        if error:
            final_report += f"📊 **{ticker}**: 분석 스킵 (사유: {error})\n\n"
            continue
        
        prompt = f"""
        전문 분석가로서 아래 데이터를 분석하세요.
        티커: {ticker} / 현재가: ${data['close']} / MA20: ${data['ma20']} / MA50: ${data['ma50']}
        추세: {data['trend']} / 뉴스: {data['news']}
        
        위 데이터를 바탕으로 기술적 분석과 뉴스 영향력을 3문장으로 요약해줘. 
        데이터 팩트와 너의 의견을 명확히 구분해서 말해줘.
        """
        
        try:
            response = model.generate_content(prompt)
            final_report += f"📊 **{ticker} (${data['close']})**\n{response.text}\n\n"
            success_count += 1
        except Exception as e:
            final_report += f"📊 **{ticker}**: AI 생성 오류 ({e})\n\n"

    if success_count == 0:
        final_report += "🚨 모든 종목 분석에 실패했습니다. 로그를 확인하세요."
    
    send_discord(final_report)

if __name__ == "__main__":
    run_analysis()
