import os
import yfinance as yf
import google.generativeai as genai
import requests
from datetime import datetime

# [1] 환경 설정
DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK_URL')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
genai.configure(api_key=GEMINI_API_KEY)

# [2] 분석 대상 티커
TICKERS = ['NVDA', 'TSLA', 'CEG', 'WCC', 'SERV', 'LUNR']

def send_to_discord(message):
    if DISCORD_WEBHOOK_URL:
        try:
            if len(message) > 1900:
                for i in range(0, len(message), 1900):
                    requests.post(DISCORD_WEBHOOK_URL, json={"content": message[i:i+1900]}, timeout=10)
            else:
                requests.post(DISCORD_WEBHOOK_URL, json={"content": message}, timeout=10)
        except Exception as e:
            print(f"전송 실패: {e}")

def get_ai_model():
    try:
        available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        # 2026년 기준 가장 안정적인 모델 선택
        target = 'models/gemini-1.5-flash' 
        return genai.GenerativeModel(target if target in available else available[0])
    except:
        return genai.GenerativeModel('gemini-1.5-flash')

def get_combined_report():
    model = get_ai_model()
    today = datetime.now().strftime('%Y년 %m월 %d일')
    
    header = f"━━━━━━━━━━━━━━━━━━━━\n🚀 **{today} 미증시 통합 브리핑**\n━━━━━━━━━━━━━━━━━━━━\n\n"
    
    all_stock_data = ""
    stock_info_list = []

    # 1. 모든 종목의 기초 데이터를 먼저 수집 (AI 호출 전)
    for ticker in TICKERS:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="2d")
            if hist.empty: continue

            price = round(hist['Close'].iloc[-1], 2)
            prev_price = hist['Close'].iloc[-2]
            change_pct = round(((price - prev_price) / prev_price) * 100, 2)
            
            news_text = "이슈 없음"
            try:
                if stock.news:
                    titles = [n.get('title') or n.get('content', {}).get('title') for n in stock.news[:2]]
                    news_text = " / ".join(filter(None, titles))
            except: pass

            # AI에게 전달할 종목별 데이터 뭉치 만들기
            stock_info_list.append({
                'ticker': ticker,
                'price': price,
                'change': change_pct,
                'news': news_text,
                'emoji': "📈" if change_pct >= 0 else "📉",
                'sign': "+" if change_pct >= 0 else ""
            })
            all_stock_data += f"- {ticker}: 가격 ${price}({change_pct}%), 뉴스: {news_text}\n"

        except Exception as e:
            print(f"{ticker} 데이터 수집 에러: {e}")

    # 2. 딱 한 번의 AI 호출로 모든 종목 분석 요청 (쿼터 절약 핵심!)
    prompt = f"""
    당신은 주식 분석 전문가입니다. 아래 제공된 6개 종목의 데이터를 바탕으로 각 종목별 분석 리포트를 작성하세요.
    
    [데이터 정보]
    {all_stock_data}
    
    [작성 규칙]
    1. 각 종목마다 1~2문장으로 아주 핵심적인 분석만 작성할 것.
    2. 종목 이름은 쓰지 말고 분석 내용만 적을 것 (나중에 코드가 합쳐줌).
    3. 답변은 반드시 종목 순서대로 '분석1|분석2|분석3...' 처럼 구분자 '|'를 써서 한 줄로 길게 출력해줘.
    """

    try:
        response = model.generate_content(prompt)
        analyses = response.text.split('|')
        
        report_body = ""
        for i, info in enumerate(stock_info_list):
            analysis = analyses[i].strip() if i < len(analyses) else "분석 데이터를 가져오지 못했습니다."
            report_body += f"**{info['emoji']} {info['ticker']}** | `${info['price']}` ({info['sign']}{info['change']}%)\n"
            report_body += f"> {analysis}\n\n"
            
        return header + report_body + "━━━━━━━━━━━━━━━━━━━━"

    except Exception as e:
        # AI 호출 자체가 실패(쿼터 초과 등)했을 경우 팩트 데이터만이라도 전송
        fallback_report = header + "⚠️ AI 분석량 초과로 기초 데이터만 전송합니다.\n\n"
        for info in stock_info_list:
            fallback_report += f"**{info['emoji']} {info['ticker']}** | `${info['price']}` ({info['sign']}{info['change']}%)\n> {info['news']}\n\n"
        return fallback_report + "━━━━━━━━━━━━━━━━━━━━"

if __name__ == "__main__":
    try:
        final_report = get_combined_report()
        send_to_discord(final_report)
    except Exception as total_error:
        send_to_discord(f"🚨 **시스템 오류 발생:** {str(total_error)}")
