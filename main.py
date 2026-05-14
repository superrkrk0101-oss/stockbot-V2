import os
import yfinance as yf
import google.generativeai as genai
import requests

# 1. 금고에서 열쇠 꺼내기
DISCORD_WEBHOOK_URL = os.environ['DISCORD_WEBHOOK_URL']
GEMINI_API_KEY = os.environ['GEMINI_API_KEY']

# 제미나이 요정 세팅
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# 2. 내가 매일 아침 분석받고 싶은 주식들
tickers = ['NVDA', 'PLTR', 'APP', 'JEPI']

def send_discord(message):
    payload = {"content": message}
    requests.post(DISCORD_WEBHOOK_URL, json=payload)

def get_stock_analysis():
    final_message = "☀️ **오늘의 미국 주식 아침 브리핑** ☀️\n\n"
    
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            
            # 차트/거래량 팩트 가져오기
            hist = stock.history(period="1d")
            if hist.empty:
                continue
            close_price = round(hist['Close'].iloc[0], 2)
            open_price = round(hist['Open'].iloc[0], 2)
            volume = hist['Volume'].iloc[0]
            
            # 어제 뉴스 팩트 가져오기
            news_items = stock.news
            news_titles = [item['title'] for item in news_items[:3]] if news_items else ["최근 특별한 뉴스가 없습니다."]
            news_text = " / ".join(news_titles)
            
            # 제미나이에게 엄격하게 명령하기 (팩트와 가정 분리)
            prompt = f"""
            너는 주식 초보자에게 아주 친절하게 설명해주는 주식 전문가야. 
            절대 없는 정보를 지어내지 말고, 실제 데이터(팩트)와 너의 분석(가정)을 명확하게 구분해서 작성해.
            
            종목명: {ticker}
            어제 종가: {close_price}달러, 시가: {open_price}달러, 거래량: {volume}
            어제 주요 뉴스 제목들: {news_text}
            
            위 실제 데이터를 바탕으로, 오늘 이 주식의 차트 흐름과 거래량의 의미, 그리고 어제 있었던 이슈가 주가에 미친 영향을 딱 3~4문장으로 아주 쉽고 명확하게 정리해줘.
            """
            
            response = model.generate_content(prompt)
            analysis = response.text
            
            final_message += f"📊 **{ticker} (현재 ${close_price})**\n💡 **빅이슈 & 차트 분석:**\n{analysis}\n\n"
            
        except Exception as e:
            final_message += f"📊 **{ticker}** 데이터를 분석하는 데 문제가 발생했어요.\n\n"
            
    return final_message

if __name__ == "__main__":
    report = get_stock_analysis()
    send_discord(report)
