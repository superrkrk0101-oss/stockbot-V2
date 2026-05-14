import os
import yfinance as yf
import google.generativeai as genai
import requests

# 1. 금고에서 비밀번호와 열쇠 꺼내기
DISCORD_WEBHOOK_URL = os.environ['DISCORD_WEBHOOK_URL']
GEMINI_API_KEY = os.environ['GEMINI_API_KEY']

# 제미나이 요정 설정
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')

# 2. 분석할 종목 리스트 (따옴표를 각각 입혀서 6개 모두 인식하게 수정했습니다!)
tickers = ['NVDA', 'PLTR', 'LUNR', 'CEG', 'SERV', 'META']

def send_discord(message):
    payload = {"content": message}
    requests.post(DISCORD_WEBHOOK_URL, json=payload)

def get_stock_analysis():
    final_message = "☀️ **오늘의 미국 주식 아침 브리핑** ☀️\n\n"
    
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            
            # 주가 데이터 가져오기
            hist = stock.history(period="1d")
            if hist.empty:
                continue
            close_price = round(hist['Close'].iloc[0], 2)
            open_price = round(hist['Open'].iloc[0], 2)
            volume = hist['Volume'].iloc[0]
            
            # [핵심] 야후 파이낸스 뉴스 제목(Title) 살려내기
            news_text = "최근 특별한 뉴스가 없습니다."
            try:
                news_items = stock.news
                if news_items:
                    news_titles = []
                    for item in news_items[:3]:
                        # 1순위: 'title' 바로 찾기 / 2순위: 'content' 상자 안의 'title' 찾기
                        title = item.get('title') or item.get('content', {}).get('title')
                        if title:
                            news_titles.append(title)
                    
                    if news_titles:
                        news_text = " / ".join(news_titles)
            except:
                pass # 뉴스를 못 가져와도 분석은 계속 진행
            
            # 제미나이에게 차트+거래량+뉴스 제목을 주고 분석 요청
            prompt = f"""
            너는 주식 전문가야. 아래 팩트 데이터를 바탕으로 3~4문장으로 요약해줘.
            종목: {ticker}
            어제 종가: {close_price}달러 / 거래량: {volume}
            최근 뉴스 제목: {news_text}
            
            내용에는 반드시 어제 차트 흐름의 의미와 뉴스 이슈가 주가에 준 영향을 포함해줘. 초보자도 이해하기 쉽게 설명해줘.
            """
            
            response = model.generate_content(prompt)
            analysis = response.text
            
            final_message += f"📊 **{ticker} (현재 ${close_price})**\n💡 **전문가 분석:**\n{analysis}\n\n"
            
        except Exception as e:
            # 혹시라도 에러가 나면 어떤 이유인지 디스코드로 알려줍니다.
            final_message += f"📊 **{ticker}** 분석 중 에러 발생: {e}\n\n"
            
    return final_message

if __name__ == "__main__":
    report = get_stock_analysis()
    send_discord(report)
