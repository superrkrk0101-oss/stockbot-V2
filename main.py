import os
import yfinance as yf
import google.generativeai as genai
from groq import Groq
import requests
from datetime import datetime

# [1] 설정 및 보안키 로드
DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK_URL')
GEMINI_KEY = os.environ.get('GEMINI_API_KEY')
GROQ_KEY = os.environ.get('GROQ_API_KEY')

TICKERS = ['NVDA', 'TSLA', 'CEG', 'WCC', 'SERV', 'LUNR']

def send_to_discord(message):
    if not DISCORD_WEBHOOK_URL: return
    try:
        # 긴 메시지는 안전하게 분할 전송
        for i in range(0, len(message), 1900):
            requests.post(DISCORD_WEBHOOK_URL, json={"content": message[i:i+1900]}, timeout=10)
    except: pass

def get_ai_analysis(input_data):
    """Gemini 시도 -> 실패 시 Groq 시도 -> 에러 로그 수집"""
    prompt = f"""
    당신은 한국의 주식 전문가입니다. 아래 뉴스 데이터를 읽고 각 종목별로 '한국어' 요약을 1~2문장으로 작성하세요.
    반드시 '종목명: 요약내용' 형식을 지켜주세요. 다른 인사는 하지 마세요.
    
    데이터:
    {input_data}
    """
    
    errors = []

    # 1트랙: Gemini (최신 3 Flash 시도)
    if GEMINI_KEY:
        try:
            genai.configure(api_key=GEMINI_KEY)
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(prompt)
            if response.text: return response.text, "Gemini"
        except Exception as e:
            errors.append(f"Gemini API 에러: {str(e)[:50]}")

    # 2트랙: Groq (Llama 3 시도)
    if GROQ_KEY:
        try:
            client = Groq(api_key=GROQ_KEY)
            completion = client.chat.completions.create(
                model="llama3-8b-8192",
                messages=[{"role": "user", "content": prompt}]
            )
            return completion.choices[0].message.content, "Groq (Llama 3)"
        except Exception as e:
            errors.append(f"Groq API 에러: {str(e)[:50]}")
    else:
        errors.append("Groq API 키가 설정되지 않았습니다.")

    return None, " / ".join(errors)

def main():
    today = datetime.now().strftime('%Y-%m-%d')
    header = f"━━━━━━━━━━━━━━━━━━━━\n🚀 **{today} 미증시 전략 보고서 (V4)**\n━━━━━━━━━━━━━━━━━━━━\n\n"
    
    stock_info = []
    ai_raw_input = ""

    # [데이터 수집 단계]
    for ticker in TICKERS:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="2d")
            if hist.empty: continue
            
            curr = round(hist['Close'].iloc[-1], 2)
            prev = hist['Close'].iloc[-2]
            change = round(((curr - prev) / prev) * 100, 2)
            
            news_title = "관련 뉴스 없음"
            if stock.news:
                titles = [n.get('title') or n.get('content', {}).get('title', '') for n in stock.news[:2]]
                news_title = " / ".join(filter(None, titles))
            
            stock_info.append({'ticker': ticker, 'price': curr, 'change': change, 'news': news_title})
            ai_raw_input += f"[{ticker}] 가격 ${curr}({change}%), 뉴스: {news_title}\n"
        except: pass

    # [AI 분석 단계]
    raw_response, status = get_ai_analysis(ai_raw_input)
    
    report_body = ""
    if raw_response and " API 에러" not in status:
        header += f"💡 **활성 엔진:** `{status}`\n\n"
        # 유연한 파싱: 줄 단위로 읽어서 종목명이 포함된 줄을 찾습니다.
        for info in stock_info:
            emoji = "📈" if info['change'] >= 0 else "📉"
            # AI 답변에서 해당 티커가 포함된 줄 찾기
            analysis_line = "분석 내용을 생성하지 못했습니다."
            for line in raw_response.split('\n'):
                if info['ticker'] in line:
                    analysis_line = line.split(':')[-1].strip() if ':' in line else line.strip()
                    break
            
            report_body += f"**{emoji} {info['ticker']}** | `${info['price']}` ({info['change']}%)\n"
            report_body += f"> {analysis_line}\n\n"
    else:
        # [최종 방어] AI가 모두 실패했을 경우
        header += f"⚠️ **AI 엔진 작동 불가** (원인: {status})\n\n"
        for info in stock_info:
            emoji = "📈" if info['change'] >= 0 else "📉"
            report_body += f"**{emoji} {info['ticker']}** | `${info['price']}` ({info['change']}%)\n"
            report_body += f"> 📰 {info['news']}\n\n"

    send_to_discord(header + report_body + "━━━━━━━━━━━━━━━━━━━━")

if __name__ == "__main__":
    main()
