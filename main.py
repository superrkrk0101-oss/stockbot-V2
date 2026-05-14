import os
import yfinance as yf
import google.generativeai as genai
import requests
import pandas as pd
from datetime import datetime

# 1. 초기 설정
DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK_URL')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
genai.configure(api_key=GEMINI_API_KEY)

# 분석 대상 티커 리스트
TICKERS = ['NVDA','CEG', 'WCC', 'SERV', 'LUNR']

def send_discord(message):
    """메시지를 디스코드로 전송합니다. 실패 시 콘솔에 출력합니다."""
    if not DISCORD_WEBHOOK_URL:
        print("에러: DISCORD_WEBHOOK_URL이 설정되지 않았습니다.")
        return
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json={"content": message})
        response.raise_for_status()
    except Exception as e:
        print(f"디스코드 전송 중 에러 발생: {e}")

def get_model():
    """Gemini 3 Flash 모델을 우선 찾고, 없으면 사용 가능한 모델을 선택합니다."""
    try:
        model_list = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        target = 'models/gemini-3-flash'
        return genai.GenerativeModel(target if target in model_list else model_list[0])
    except:
        return genai.GenerativeModel('gemini-1.5-flash')

def analyze_stock(ticker, model):
    """개별 종목 분석 데이터를 수집하고 AI 분석을 수행합니다."""
    try:
        stock = yf.Ticker(ticker)
        # 이동평균선을 위해 충분한 데이터(60일치) 확보
        df = stock.history(period="60d")
        
        if df.empty or len(df) < 50:
            return f"📊 **{ticker}**: 데이터 부족으로 분석 불가"

        # 지표 계산
        curr_price = round(df['Close'].iloc[-1], 2)
        ma20 = round(df['Close'].rolling(window=20).mean().iloc[-1], 2)
        ma50 = round(df['Close'].rolling(window=50).mean().iloc[-1], 2)
        
        # 뉴스 데이터 (안전한 파싱)
        news_titles = []
        try:
            raw_news = stock.news
            if raw_news:
                for item in raw_news[:3]:
                    title = item.get('title') or item.get('content', {}).get('title')
                    if title: news_titles.append(title)
        except:
            pass
        news_summary = " / ".join(news_titles) if news_titles else "최근 주요 이슈 없음"

        # AI 프롬프트 구성
        prompt = f"""
        당신은 데이터 기반 주식 분석가입니다. 아래 지표를 보고 3문장으로 분석하세요.
        - 종목: {ticker} (현재가 ${curr_price})
        - 기술지표: 20일 이평선(${ma20}), 50일 이평선(${ma50})
        - 뉴스: {news_summary}
        
        [요청] 이평선 대비 현재가 위치를 기반으로 단기 추세를 진단하고, 뉴스의 영향을 포함해 전문적으로 요약해줘.
        """
        
        response = model.generate_content(prompt)
        return f"📊 **{ticker} (${curr_price})**\n{response.text}\n"

    except Exception as e:
        return f"❌ **{ticker} 분석 중 에러**: {str(e)}"

def main():
    print("작업 시작...")
    model = get_model()
    today = datetime.now().strftime('%Y-%m-%d')
    final_report = f"📅 **{today} 미국 주식 전략 리포트**\n\n"
    
    results = []
    for ticker in TICKERS:
        print(f"{ticker} 분석 중...")
        analysis = analyze_stock(ticker, model)
        results.append(analysis)
    
    final_report += "\n".join(results)
    
    # 최종 전송
    send_discord(final_report)
    print("분석 완료 및 디스코드 전송 성공!")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # 시스템 전체가 멈췄을 경우 디스코드로 에러 보고
        send_discord(f"🚨 **시스템 중단 에러 발생!**\n사유: {str(e)}")
