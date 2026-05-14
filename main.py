import os
import yfinance as yf
import google.generativeai as genai
import requests
from datetime import datetime

# 1. 환경 설정 및 보안 키 로드
DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK_URL')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

# 제미나이 설정
genai.configure(api_key=GEMINI_API_KEY)

# 2. 분석 대상 종목 리스트
TICKERS = ['NVDA', 'CEG','SERV','WCC', 'PLTR', 'LUNR']

def get_best_model():
    """현재 사용 가능한 가장 최신 모델(Gemini 3 Flash 등)을 동적으로 선택합니다."""
    try:
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        target = 'models/gemini-3-flash'
        return target if target in available_models else available_models[0]
    except Exception:
        return 'gemini-1.5-flash'  # 폴백 모델

def send_discord(message):
    """분석 결과를 디스코드로 전송합니다."""
    if DISCORD_WEBHOOK_URL:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": message})

def fetch_stock_data(ticker):
    """야후 파이낸스에서 주가 및 뉴스 데이터를 안전하게 가져옵니다."""
    stock = yf.Ticker(ticker)
    
    # 주가 데이터 (최근 1일)
    hist = stock.history(period="1d")
    if hist.empty:
        return None, "데이터 없음"

    info = {
        'close': round(hist['Close'].iloc[-1], 2),
        'open': round(hist['Open'].iloc[-1], 2),
        'volume': hist['Volume'].iloc[-1],
        'news': "관련 뉴스 없음"
    }

    # 뉴스 데이터 수집 (구조 변경 대응 로직)
    try:
        news_items = stock.news
        if news_items:
            titles = []
            for item in news_items[:3]:
                # 'title'이 없으면 'content' 내부를 확인하는 유연한 파싱
                title = item.get('title') or item.get('content', {}).get('title')
                if title:
                    titles.append(title)
            if titles:
                info['news'] = " / ".join(titles)
    except Exception:
        pass # 뉴스 로드 실패 시에도 주가 분석은 진행

    return info, None

def create_analysis_report():
    """전체 종목을 분석하여 최종 리포트를 생성합니다."""
    model_name = get_best_model()
    model = genai.GenerativeModel(model_name)
    
    today = datetime.now().strftime('%Y-%m-%d')
    report = f"📅 **{today} 미국 주식 시장 브리핑**\n"
    report += f"🤖 사용 모델: `{model_name}`\n\n"

    for ticker in TICKERS:
        data, error = fetch_stock_data(ticker)
        if error:
            report += f"📊 **{ticker}**: 데이터를 가져올 수 없습니다.\n\n"
            continue

        # AI에게 전달할 프롬프트 (팩트 중심 분석 요청)
        prompt = f"""
        당신은 전문 금융 분석가입니다. 아래 데이터를 바탕으로 분석 리포트를 작성하세요.
        
        [데이터 팩트]
        - 종목: {ticker}
        - 종가: ${data['close']} (시가: ${data['open']})
        - 거래량: {data['volume']}
        - 주요 뉴스 제목: {data['news']}

        [작성 가이드라인]
        1. '분석 결과'와 '데이터 팩트'를 명확히 구분할 것.
        2. 차트 흐름과 거래량이 주는 의미를 기술적으로 해석할 것.
        3. 뉴스가 향후 주가에 미칠 잠재적 영향을 포함할 것.
        4. 친절하지만 전문적인 톤으로 3~4문장 내외로 작성할 것.
        """

        try:
            response = model.generate_content(prompt)
            report += f"📊 **{ticker} (현재 ${data['close']})**\n{response.text}\n\n"
        except Exception as e:
            report += f"📊 **{ticker}**: AI 분석 중 오류 발생 ({e})\n\n"

    return report

if __name__ == "__main__":
    final_report = create_analysis_report()
    send_discord(final_report)
