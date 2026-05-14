import os
import yfinance as yf
import google.generativeai as genai
from groq import Groq
import requests
from datetime import datetime

# [1] API 설정 및 클라이언트 초기화
DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK_URL')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')

genai.configure(api_key=GEMINI_API_KEY)
groq_client = Groq(api_key=GROQ_API_KEY)

TICKERS = ['NVDA', 'TSLA', 'CEG', 'WCC', 'SERV', 'LUNR']

def send_to_discord(message):
    if DISCORD_WEBHOOK_URL:
        try:
            if len(message) > 1900:
                for i in range(0, len(message), 1900):
                    requests.post(DISCORD_WEBHOOK_URL, json={"content": message[i:i+1900]}, timeout=10)
            else:
                requests.post(DISCORD_WEBHOOK_URL, json={"content": message}, timeout=10)
        except: pass

def get_ai_analysis(all_stock_data):
    """Gemini 우선 시도, 실패 시 Groq으로 전환"""
    prompt = f"""
    당신은 한국의 전문 주식 분석가입니다. 아래 제공된 영어 뉴스 데이터를 읽고, 한국 투자자들을 위해 반드시 한국어로 요약하세요.
    데이터: {all_stock_data}
    각 종목의 핵심 이슈를 1~2문장으로 한국어 요약하고, 결과는 '요약1|요약2|요약3...' 처럼 구분자 '|'를 써서 한 줄로 출력하세요.
    """

    # 1트랙: Gemini
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        return response.text, "Gemini 3 Flash"
    except Exception as e:
        print(f"Gemini 쿼터 초과 또는 에러: {e}")

    # 2트랙: Groq (Llama 3 8B 모델 사용)
    try:
        completion = groq_client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": prompt}]
        )
        return completion.choices[0].message.content, "Groq (Llama 3)"
    except Exception as e:
        print(f"Groq API 에러: {e}")
        return None, None

def get_combined_report():
    today = datetime.now().strftime('%Y년 %m월 %d일')
    header = f"━━━━━━━━━━━━━━━━━━━━\n🚀 **{today} 미증시 하이브리드 브리핑**\n━━━━━━━━━━━━━━━━━━━━\n\n"
    
    all_stock_data = ""
    stock_info_list = []

    for ticker in TICKERS:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="2d")
            if hist.empty: continue
            price = round(hist['Close'].iloc[-1], 2)
            change_pct = round(((price - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100, 2)
            
            news = "특별한 뉴스 없음"
            if stock.news:
                titles = [n.get('title') or n.get('content', {}).get('title') for n in stock.news[:2]]
                news = " / ".join(filter(None, titles))

            stock_info_list.append({'ticker': ticker, 'price': price, 'change': change_pct, 'news': news})
            all_stock_data += f"- {ticker}: ${price}({change_pct}%), 뉴스: {news}\n"
        except: pass

    # AI 분석 수행 (Gemini -> Groq 로테이션)
    analysis_result, model_name = get_ai_analysis(all_stock_data)
    
    report_body = ""
    if analysis_result:
        header += f"💡 **활성 엔진:** `{model_name}`\n\n"
        analyses = analysis_result.split('|')
        for i, info in enumerate(stock_info_list):
            txt = analyses[i].strip() if i < len(analyses) else "분석 데이터를 가져오지 못했습니다."
            emoji = "📈" if info['change'] >= 0 else "📉"
            report_body += f"**{emoji} {info['ticker']}** | `${info['price']}` ({info['change']}%)\n"
            report_body += f"> {txt}\n\n"
    else:
        # 모든 AI 실패 시 폴백
        header += "⚠️ **AI 분석량 초과로 영어 뉴스 원문 전송**\n\n"
        for info in stock_info_list:
            emoji = "📈" if info['change'] >= 0 else "📉"
            report_body += f"**{emoji} {info['ticker']}** | `${info['price']}` ({info['change']}%)\n"
            report_body += f"> 📰 {info['news']}\n\n"

    return header + report_body + "━━━━━━━━━━━━━━━━━━━━"

if __name__ == "__main__":
    send_to_discord(get_combined_report())
