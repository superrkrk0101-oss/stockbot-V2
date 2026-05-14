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

    for ticker in TICKERS:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="2d")
            if hist.empty: continue

            price = round(hist['Close'].iloc[-1], 2)
            prev_price = hist['Close'].iloc[-2]
            change_pct = round(((price - prev_price) / prev_price) * 100, 2)
            
            news_text = "특별한 뉴스 없음"
            try:
                if stock.news:
                    titles = [n.get('title') or n.get('content', {}).get('title') for n in stock.news[:2]]
                    news_text = " / ".join(filter(None, titles))
            except: pass

            stock_info_list.append({
                'ticker': ticker, 'price': price, 'change': change_pct, 
                'news': news_text, 'emoji': "📈" if change_pct >= 0 else "📉",
                'sign': "+" if change_pct >= 0 else ""
            })
            all_stock_data += f"- {ticker}: 가격 ${price}({change_pct}%), 뉴스: {news_text}\n"

        except Exception as e:
            print(f"{ticker} 데이터 수집 에러: {e}")

    # [핵심] 한국어 답변을 강제하는 프롬프트
    prompt = f"""
    당신은 한국의 전문 주식 분석가입니다. 아래 제공된 영어 뉴스 데이터를 읽고, 한국 투자자들을 위해 **반드시 한국어로** 요약하세요.
    
    [데이터 정보]
    {all_stock_data}
    
    [작성 규칙]
    1. 모든 답변은 반드시 **한국어**로 작성할 것.
    2. 종목마다 영어 뉴스의 핵심 내용을 파악하여 한국어로 1~2문장 요약할 것.
    3. 답변은 반드시 '요약1|요약2|요약3|요약4|요약5|요약6' 형태로 '|'를 사용해 한 줄로 출력할 것.
    """

    try:
        response = model.generate_content(prompt)
        # AI가 답변을 한국어로 줄 것입니다.
        analyses = response.text.split('|')
        
        report_body = ""
        for i, info in enumerate(stock_info_list):
            analysis = analyses[i].strip() if i < len(analyses) else "분석 생성 중 오류가 발생했습니다."
            report_body += f"**{info['emoji']} {info['ticker']}** | `${info['price']}` ({info['sign']}{info['change']}%)\n"
            report_body += f"> {analysis}\n\n"
            
        return header + report_body + "━━━━━━━━━━━━━━━━━━━━"

    except Exception as e:
        # AI 호출 실패 시 안내 문구도 한국어화
        fallback_report = header + "⚠️ **알림: AI 할당량 초과로 영어 뉴스 원문만 전송합니다.**\n"
        fallback_report += "*(오후에 다시 실행하면 한국어 요약이 제공됩니다)*\n\n"
        for info in stock_info_list:
            fallback_report += f"**{info['emoji']} {info['ticker']}** | `${info['price']}` ({info['sign']}{info['change']}%)\n> 📰 {info['news']}\n\n"
        return fallback_report + "━━━━━━━━━━━━━━━━━━━━"

if __name__ == "__main__":
    try:
        final_report = get_combined_report()
        send_to_discord(final_report)
    except Exception as total_error:
        send_to_discord(f"🚨 **시스템 오류 발생:** {str(total_error)}")
