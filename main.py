import os
import yfinance as yf
import google.generativeai as genai
from groq import Groq
import requests
from datetime import datetime

# [1] API 설정
DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK_URL')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')

genai.configure(api_key=GEMINI_API_KEY)
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

TICKERS = ['NVDA', 'TSLA', 'CEG', 'WCC', 'SERV', 'LUNR']

def send_to_discord(message):
    if DISCORD_WEBHOOK_URL:
        try:
            # 메시지 길이 초과 방지
            if len(message) > 1900:
                for i in range(0, len(message), 1900):
                    requests.post(DISCORD_WEBHOOK_URL, json={"content": message[i:i+1900]}, timeout=10)
            else:
                requests.post(DISCORD_WEBHOOK_URL, json={"content": message}, timeout=10)
        except: pass

def get_ai_analysis(data_text):
    """Gemini 시도 -> 실패 시 Groq 시도"""
    # AI가 형식을 잘 지키도록 더 구체적으로 지시합니다.
    prompt = f"""
    당신은 한국의 금융 분석 전문가입니다. 아래 주식 데이터를 보고 각 종목별로 '한국어' 요약을 작성하세요.
    
    데이터:
    {data_text}
    
    [작성 규칙 - 매우 중요]
    1. 각 종목의 요약만 '구분자(|)'를 사용하여 순서대로 나열하세요.
    2. 예시: 첫 번째 종목 요약입니다 | 두 번째 종목 요약입니다 | 세 번째...
    3. 다른 설명이나 인사말은 절대 하지 마세요.
    """

    # 1트랙: Gemini
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        if response.text:
            return response.text, "Gemini 3 Flash"
    except Exception as e:
        print(f"Gemini 실패: {e}")

    # 2트랙: Groq
    if groq_client:
        try:
            completion = groq_client.chat.completions.create(
                model="llama3-8b-8192",
                messages=[{"role": "user", "content": prompt}]
            )
            return completion.choices[0].message.content, "Groq (Llama 3)"
        except Exception as e:
            print(f"Groq 실패: {e}")
            
    return None, None

def get_combined_report():
    today = datetime.now().strftime('%Y년 %m월 %d일')
    header = f"━━━━━━━━━━━━━━━━━━━━\n🚀 **{today} 미증시 하이브리드 브리핑**\n━━━━━━━━━━━━━━━━━━━━\n\n"
    
    stock_data_list = []
    input_text = ""

    # 데이터 수집
    for ticker in TICKERS:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="2d")
            if hist.empty: continue
            
            price = round(hist['Close'].iloc[-1], 2)
            change = round(((price - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100, 2)
            
            news = "특별한 이슈 없음"
            if stock.news:
                titles = [n.get('title') or n.get('content', {}).get('title') for n in stock.news[:2]]
                news = " / ".join(filter(None, titles))

            stock_data_list.append({'ticker': ticker, 'price': price, 'change': change, 'news': news})
            input_text += f"[{ticker}] 현재가 ${price}, 변동률 {change}%, 뉴스: {news}\n"
        except: pass

    # AI 분석 요청
    raw_analysis, model_name = get_ai_analysis(input_text)
    
    report_body = ""
    if raw_analysis:
        header += f"💡 **활성 엔진:** `{model_name}`\n\n"
        # AI가 준 답변을 리스트로 변환 (공백 제거 등 정제 작업 포함)
        analyses = [a.strip() for a in raw_analysis.split('|')]
        
        for i, info in enumerate(stock_data_list):
            # AI 답변 개수가 부족할 경우를 대비한 안전장치
            txt = analyses[i] if i < len(analyses) else "분석 요약을 생성하지 못했습니다."
            emoji = "📈" if info['change'] >= 0 else "📉"
            report_body += f"**{emoji} {info['ticker']}** | `${info['price']}` ({info['change']}%)\n"
            report_body += f"> {txt}\n\n"
    else:
        # 모든 AI 실패 시
        header += "⚠️ **AI 분석 실패 (팩트 데이터만 전송)**\n\n"
        for info in stock_data_list:
            emoji = "📈" if info['change'] >= 0 else "📉"
            report_body += f"**{emoji} {info['ticker']}** | `${info['price']}` ({info['change']}%)\n"
            report_body += f"> 📰 {info['news']}\n\n"

    return header + report_body + "━━━━━━━━━━━━━━━━━━━━"

if __name__ == "__main__":
    final_report = get_combined_report()
    send_to_discord(final_report)
