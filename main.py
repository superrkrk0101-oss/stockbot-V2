import os
import yfinance as yf
import google.generativeai as genai
import requests
import time

# 1. 비밀 금고에서 열쇠 꺼내기
DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK_URL')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

# 제미나이 요정 설정 (2026 최신 안정화 주소 사용)
genai.configure(api_key=GEMINI_API_KEY)

def send_discord(message):
    if DISCORD_WEBHOOK_URL:
        payload = {"content": message}
        requests.post(DISCORD_WEBHOOK_URL, json=payload)

def get_stock_analysis():
    # 분석하고 싶은 종목들 (관심 있으신 종목 위주로 꽉 채웠어요!)
    tickers = ['NVDA', 'PLTR', 'LUNR', 'CEG', 'SERV', 'META', 'JEPI']
    final_message = "☀️ **2026년형 미국 주식 아침 브리핑** ☀️\n\n"
    
    # 요정 부르기 (가장 안정적인 모델 이름으로 시도)
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
    except:
        model = genai.GenerativeModel('models/gemini-1.5-flash')

    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            
            # 주가 데이터 가져오기
            hist = stock.history(period="2d") # 어제와 그저께 데이터 비교
            if hist.empty:
                continue
                
            today_close = hist['Close'].iloc[-1]
            prev_close = hist['Close'].iloc[-2]
            change_percent = ((today_close - prev_close) / prev_close) * 100
            volume = hist['Volume'].iloc[-1]
            
            # 뉴스 제목 찾아내기 (더 꼼꼼한 버전)
            news_text = "특별한 뉴스가 없습니다."
            try:
                raw_news = stock.news
                titles = []
                for n in raw_news[:3]:
                    t = n.get('title') or (n.get('content') and n.get('content').get('title'))
                    if t: titles.append(t)
                if titles:
                    news_text = " / ".join(titles)
            except:
                pass

            # 요정에게 분석 요청 (프롬프트 강화)
            prompt = f"""
            너는 주식 분석 전문가야. 아래 데이터를 보고 초보자도 이해하기 쉽게 3문장으로 요약해줘.
            - 종목: {ticker}
            - 현재가: ${today_close:.2f} (전일대비 {change_percent:.2f}%)
            - 거래량: {volume:,}
            - 주요 뉴스: {news_text}
            
            어제 차트의 움직임이 긍정적인지 부정적인지, 뉴스가 어떤 영향을 줬는지 아주 쉽게 설명해줘.
            """
            
            response = model.generate_content(prompt)
            analysis = response.text
            
            final_message += f"📊 **{ticker}** (${today_close:.2f})\n{analysis}\n\n"
            
            # 너무 빨리 요청하면 요정이 힘들어하니 1초씩 쉬어주기
            time.sleep(1)
            
        except Exception as e:
            final_message += f"📊 **{ticker}** 분석 중 작은 문제가 생겼어요: {e}\n\n"
            
    return final_message

if __name__ == "__main__":
    report = get_stock_analysis()
    send_discord(report)
