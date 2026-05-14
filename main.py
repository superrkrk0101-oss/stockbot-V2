import os
import yfinance as yf
import google.generativeai as genai
from groq import Groq
import requests
from datetime import datetime

# [1] 설정 로드
DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK_URL')
GEMINI_KEY = os.environ.get('GEMINI_API_KEY')
GROQ_KEY = os.environ.get('GROQ_API_KEY')

TICKERS = ['NVDA', 'TSLA', 'CEG', 'WCC', 'SERV', 'LUNR']

def send_to_discord(message):
    if not DISCORD_WEBHOOK_URL: return
    try:
        for i in range(0, len(message), 1900):
            requests.post(DISCORD_WEBHOOK_URL, json={"content": message[i:i+1900]}, timeout=10)
    except: pass

def get_ai_analysis(input_data):
    prompt = f"""
    당신은 한국의 주식 전문가입니다. 아래 뉴스 데이터를 읽고 각 종목별로 '한국어' 요약을 1~2문장으로 작성하세요.
    반드시 '종목명: 요약내용' 형식을 지켜주세요.
    
    데이터:
    {input_data}
    """
    
    # 1트랙: Gemini (모델 이름 형식을 더 유연하게 수정)
    if GEMINI_KEY:
        try:
            genai.configure(api_key=GEMINI_KEY)
            # 404 에러 방지를 위해 가장 안정적인 이름 사용
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(prompt)
            if response.text: return response.text, "Gemini"
        except Exception as e:
            print(f"Gemini 시도 실패: {e}")

    # 2트랙: Groq (모델 이름을 llama-3.3-70b-versatile 등으로 최신화)
    if GROQ_KEY:
        try:
            client = Groq(api_key=GROQ_KEY)
            # 400 에러 방지를 위해 2026년 기준 표준 모델명 사용
            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile", 
                messages=[{"role": "user", "content": prompt}]
            )
            return completion.choices[0].message.content, "Groq"
        except Exception as e:
            print(f"Groq 시도 실패: {e}")

    return None, "모든 AI 엔진 호출 실패 (모델 명칭 확인 필요)"

def main():
    today = datetime.now().strftime('%Y-%m-%d')
    header = f"━━━━━━━━━━━━━━━━━━━━\n🚀 **{today} 미증시 전략 보고서 (V5)**\n━━━━━━━━━━━━━━━━━━━━\n\n"
    
    stock_info = []
    ai_raw_input = ""

    for ticker in TICKERS:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="2d")
            if hist.empty: continue
            
            curr = round(hist['Close'].iloc[-1], 2)
            prev = hist['Close'].iloc[-2]
            change = round(((curr - prev) / prev) * 100, 2)
            
            news_title = "특별한 이슈 없음"
            if stock.news:
                titles = [n.get('title') or n.get('content', {}).get('title', '') for n in stock.news[:2]]
                news_title = " / ".join(filter(None, titles))
            
            stock_info.append({'ticker': ticker, 'price': curr, 'change': change, 'news': news_title})
            ai_raw_input += f"[{ticker}] 뉴스: {news_title}\n"
        except: pass

    raw_response, status = get_ai_analysis(ai_raw_input)
    
    report_body = ""
    if raw_response and "실패" not in status:
        header += f"💡 **활성 엔진:** `{status}`\n\n"
        for info in stock_info:
            emoji = "📈" if info['change'] >= 0 else "📉"
            analysis_line = "분석 내용을 생성하지 못했습니다."
            for line in raw_response.split('\n'):
                if info['ticker'].lower() in line.lower():
                    analysis_line = line.split(':')[-1].strip() if ':' in line else line.strip()
                    break
            
            report_body += f"**{emoji} {info['ticker']}** | `${info['price']}` ({info['change']}%)\n"
            report_body += f"> {analysis_line}\n\n"
    else:
        header += f"⚠️ **AI 엔진 작동 불가**\n`상태: {status}`\n\n"
        for info in stock_info:
            emoji = "📈" if info['change'] >= 0 else "📉"
            report_body += f"**{emoji} {info['ticker']}** | `${info['price']}` ({info['change']}%)\n"
            report_body += f"> 📰 {info['news']}\n\n"

    send_to_discord(header + report_body + "━━━━━━━━━━━━━━━━━━━━")

if __name__ == "__main__":
    main()
