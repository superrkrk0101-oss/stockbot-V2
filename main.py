import os
import yfinance as yf
import google.generativeai as genai
import requests
from datetime import datetime

# [1] 환경 설정
DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK_URL')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
genai.configure(api_key=GEMINI_API_KEY)

# [2] 분석 대상 티커 (NVDA, TSLA 추가)
TICKERS = ['NVDA', 'TSLA', 'CEG', 'WCC', 'SERV', 'LUNR']

def send_to_discord(message):
    """디스코드로 즉시 메시지 전송"""
    if DISCORD_WEBHOOK_URL:
        try:
            # 메시지가 너무 길 경우 분할 전송 (디스코드 2000자 제한)
            if len(message) > 1900:
                for i in range(0, len(message), 1900):
                    requests.post(DISCORD_WEBHOOK_URL, json={"content": message[i:i+1900]}, timeout=10)
            else:
                requests.post(DISCORD_WEBHOOK_URL, json={"content": message}, timeout=10)
        except Exception as e:
            print(f"전송 실패: {e}")

def get_ai_model():
    """Gemini 3 Flash 모델 선택"""
    try:
        available = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        target = 'models/gemini-3-flash'
        return genai.GenerativeModel(target if target in available else available[0])
    except:
        return genai.GenerativeModel('gemini-1.5-flash')

def get_stock_report():
    model = get_ai_model()
    today = datetime.now().strftime('%Y년 %m월 %d일')
    
    # 상단 헤더
    header = f"━━━━━━━━━━━━━━━━━━━━\n"
    header += f"🚀 **{today} 미증시 전략 브리핑**\n"
    header += f"━━━━━━━━━━━━━━━━━━━━\n\n"
    
    report_body = ""
    
    for ticker in TICKERS:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="2d") # 등락률 계산을 위해 2일치
            
            if hist.empty:
                report_body += f"▫️ **{ticker}**: 데이터 로드 실패\n\n"
                continue

            price = round(hist['Close'].iloc[-1], 2)
            prev_price = hist['Close'].iloc[-2]
            change_pct = round(((price - prev_price) / prev_price) * 100, 2)
            
            # 등락에 따른 이모지 선택
            emoji = "📈" if change_pct >= 0 else "📉"
            sign = "+" if change_pct >= 0 else ""

            # 뉴스 수집
            news_text = "최근 주요 이슈 없음"
            try:
                if stock.news:
                    titles = [n.get('title') or n.get('content', {}).get('title') for n in stock.news[:2]]
                    news_text = " / ".join(filter(None, titles))
            except: pass

            # AI 분석 (가독성 좋게 요청)
            prompt = f"종목:{ticker}, 가격:${price}({sign}{change_pct}%), 뉴스:{news_text}. 현재 흐름과 뉴스 영향을 전문가처럼 한 줄로 요약해줘."
            res = model.generate_content(prompt)
            
            # 한 종목씩 블록 형태로 구성
            report_body += f"**{emoji} {ticker}** | `${price}` ({sign}{change_pct}%)\n"
            report_body += f"> {res.text}\n\n"
            
        except Exception as e:
            report_body += f"❌ **{ticker} 분석 중 에러**: {str(e)}\n\n"
            
    footer = f"━━━━━━━━━━━━━━━━━━━━"
    return header + report_body + footer

if __name__ == "__main__":
    try:
        # 리포트 생성 및 전송
        final_report = get_stock_report()
        send_to_discord(final_report)
        
    except Exception as total_error:
        # [에러 즉보 기능] 시스템 전체 중단 시 상세 사유 보고
        error_msg = (
            f"🚨 **시스템 치명적 오류 발생!**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"**사유:** `{str(total_error)}`\n"
            f"**발생 시간:** {datetime.now().strftime('%H:%M:%S')}\n"
            f"**조치:** GitHub Actions 로그를 확인해 주세요."
        )
        send_to_discord(error_msg)
