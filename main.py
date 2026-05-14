import os
import yfinance as yf
import google.generativeai as genai
from groq import Groq
import requests
from datetime import datetime
import json
import re

# [1] API 설정 및 초기화
DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK_URL')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')

genai.configure(api_key=GEMINI_API_KEY)
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

TICKERS = ['NVDA', 'TSLA', 'CEG', 'WCC', 'SERV', 'LUNR']

def send_to_discord(message):
    if not DISCORD_WEBHOOK_URL: return
    try:
        # 메시지 길이 제한(2000자) 대응
        for i in range(0, len(message), 1900):
            requests.post(DISCORD_WEBHOOK_URL, json={"content": message[i:i+1900]}, timeout=10)
    except: pass

def get_ai_response(prompt):
    """Gemini 시도 후 실패 시 Groq 시도"""
    # 1. Gemini 시도
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        if response.text: return response.text, "Gemini"
    except Exception as e:
        print(f"Gemini Error: {e}")

    # 2. Groq 시도
    if groq_client:
        try:
            completion = groq_client.chat.completions.create(
                model="llama3-8b-8192",
                messages=[{"role": "user", "content": prompt}]
            )
            return completion.choices[0].message.content, "Groq"
        except Exception as e:
            print(f"Groq Error: {e}")
            
    return None, None

def parse_analysis(raw_text, ticker_count):
    """AI의 답변에서 JSON만 쏙 뽑아내거나 수동으로 파싱합니다."""
    try:
        # AI 답변에서 JSON 블록 { ... } 만 추출
        match = re.search(r'\{.*\}', raw_text, re.DOTALL)
        if match:
            data = json.loads(match.group())
            return [data.get(str(i), "분석 결과 없음") for i in range(ticker_count)]
    except:
        pass
    # JSON 파싱 실패 시 차선책 (줄바꿈 등으로 대충 잘라보기)
    lines = [line.strip() for line in raw_text.split('\n') if line.strip() and (':' in line or '-' in line)]
    return lines if len(lines) >= ticker_count else None

def main():
    today = datetime.now().strftime('%Y년 %m월 %d일')
    header = f"━━━━━━━━━━━━━━━━━━━━\n🚀 **{today} 미증시 하이브리드 브리핑**\n━━━━━━━━━━━━━━━━━━━━\n\n"
    
    collected_data = []
    ai_input = ""

    for i, ticker in enumerate(TICKERS):
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="2d")
            if hist.empty: continue
            
            price = round(hist['Close'].iloc[-1], 2)
            change = round(((price - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2]) * 100, 2)
            news = "이슈 없음"
            if stock.news:
                titles = [n.get('title') or n.get('content', {}).get('title') for n in stock.news[:2]]
                news = " / ".join(filter(None, titles))

            collected_data.append({'ticker': ticker, 'price': price, 'change': change, 'news': news})
            ai_input += f"{i}: [{ticker}] 뉴스: {news}\n"
        except: pass

    # AI에게 JSON 형식으로 답변하도록 아주 엄격하게 명령
    prompt = f"""
    당신은 한국 투자 전문가입니다. 다음 뉴스 데이터를 읽고 각 번호에 맞는 한국어 요약을 'JSON' 형식으로만 답변하세요.
    인사말이나 설명은 절대 하지 마세요. 오직 JSON만 출력하세요.
    
    데이터:
    {ai_input}
    
    형식 예시:
    {{
      "0": "엔비디아는 AI 수요 증가로 상승세입니다.",
      "1": "테슬라는 전기차 인도량 감소 우려가 있습니다."
    }}
    """

    raw_response, engine = get_ai_response(prompt)
    
    report_body = ""
    if raw_response:
        analyses = parse_analysis(raw_response, len(collected_data))
        
        if analyses:
            header += f"💡 **활성 엔진:** `{engine}`\n\n"
            for i, info in enumerate(collected_data):
                txt = analyses[i] if i < len(analyses) else "분석 생성 오류"
                emoji = "📈" if info['change'] >= 0 else "📉"
                report_body += f"**{emoji} {info['ticker']}** | `${info['price']}` ({info['change']}%)\n> {txt}\n\n"
        else:
            # AI가 대답은 했는데 형식이 엉망일 경우 (디버깅 모드)
            header += f"⚠️ **AI 답변 형식이 올바르지 않습니다.** (엔진: {engine})\n\n"
            report_body += f"**[AI 원문 데이터]**\n{raw_response[:500]}...\n\n"
    else:
        header += "❌ **모든 AI 엔진 호출 실패**\n\n"
        for info in collected_data:
            emoji = "📈" if info['change'] >= 0 else "📉"
            report_body += f"**{emoji} {info['ticker']}** | `${info['price']}` ({info['change']}%)\n> 📰 {info['news']}\n\n"

    send_to_discord(header + report_body + "━━━━━━━━━━━━━━━━━━━━")

if __name__ == "__main__":
    main()
