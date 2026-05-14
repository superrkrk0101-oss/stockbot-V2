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

# 분석 종목 및 매칭되는 경쟁사(Peer) 설정
TICKERS = ['NVDA', 'TSLA', 'CEG', 'WCC', 'SERV', 'LUNR']
PEERS = {
    'NVDA': 'AMD', 'TSLA': 'RIVN', 'CEG': 'VST', 
    'WCC': 'GWW', 'SERV': 'AMZN', 'LUNR': 'SPCE'
}

def send_to_discord(message):
    if not DISCORD_WEBHOOK_URL: return
    try:
        for i in range(0, len(message), 1900):
            requests.post(DISCORD_WEBHOOK_URL, json={"content": message[i:i+1900]}, timeout=10)
    except: pass

def get_ai_analysis(input_data):
    # 언어 혼착 방지를 위해 "순수 한국어" 및 "전문 용어 사용" 지침 강화
    prompt = f"""
    당신은 월스트리트 출신의 퀀트 분석가입니다. 제공된 데이터를 바탕으로 심층 분석 리포트를 작성하세요.
    
    [데이터]
    {input_data}
    
    [작성 규칙 - 필독]
    1. **반드시 순수 한국어로만 작성하세요.** (empresa, entreprise 같은 외국어나 불필요한 한자 혼용 금지)
    2. 단순히 뉴스 요약이 아니라, '거래량 변화'와 '경쟁사 대비 성과'를 연계하여 주가 변동의 원인을 분석하세요.
    3. 종목당 3문장 내외로 전문성 있게 작성하세요.
    4. 형식: '종목명: 분석내용'
    """
    
    # Gemini 시도
    if GEMINI_KEY:
        try:
            genai.configure(api_key=GEMINI_KEY)
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(prompt)
            if response.text: return response.text, "Gemini"
        except: pass

    # Groq 시도 (Llama 3.3 모델 사용)
    if GROQ_KEY:
        try:
            client = Groq(api_key=GROQ_KEY)
            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}]
            )
            return completion.choices[0].message.content, "Groq"
        except: pass

    return None, "AI 호출 실패"

def get_stock_details(ticker):
    """거래량 및 경쟁사 데이터를 포함한 상세 정보를 가져옵니다."""
    stock = yf.Ticker(ticker)
    # 10일치 데이터를 가져와 평균 거래량 계산
    hist = stock.history(period="10d")
    if hist.empty or len(hist) < 2: return None

    curr = hist.iloc[-1]
    prev = hist.iloc[-2]
    
    price = round(curr['Close'], 2)
    change_pct = round(((curr['Close'] - prev['Close']) / prev['Close']) * 100, 2)
    
    # 거래량 분석 (오늘 거래량 vs 10일 평균 거래량)
    avg_vol = hist['Volume'].mean()
    vol_ratio = round((curr['Volume'] / avg_vol) * 100, 1)
    vol_status = "급증" if vol_ratio > 150 else ("저조" if vol_ratio < 70 else "평이")

    # 경쟁사 동향 가져오기
    peer_ticker = PEERS.get(ticker)
    peer_info = "정보 없음"
    if peer_ticker:
        p_stock = yf.Ticker(peer_ticker)
        p_hist = p_stock.history(period="2d")
        if not p_hist.empty:
            p_change = round(((p_hist['Close'].iloc[-1] - p_hist['Close'].iloc[-2]) / p_hist['Close'].iloc[-2]) * 100, 2)
            p_sign = "+" if p_change > 0 else ""
            peer_info = f"{peer_ticker}({p_sign}{p_change}%)"

    news = "없음"
    if stock.news:
        news = " / ".join([n.get('title', '') for n in stock.news[:2]])

    return {
        'price': price, 'change': change_pct, 'vol_ratio': vol_ratio,
        'vol_status': vol_status, 'peer': peer_info, 'news': news
    }

def main():
    today = datetime.now().strftime('%Y-%m-%d')
    header = f"━━━━━━━━━━━━━━━━━━━━\n🚀 **{today} 미증시 심층 전략 보고서 (V6)**\n━━━━━━━━━━━━━━━━━━━━\n\n"
    
    stock_list = []
    ai_input = ""

    for ticker in TICKERS:
        data = get_stock_details(ticker)
        if data:
            stock_list.append({'ticker': ticker, **data})
            ai_input += (f"[{ticker}] 가격:${data['price']}({data['change']}%), "
                        f"거래량:평균대비 {data['vol_ratio']}%({data['vol_status']}), "
                        f"경쟁사:{data['peer']}, 뉴스:{data['news']}\n")

    raw_res, engine = get_ai_analysis(ai_input)
    
    report_body = ""
    if raw_res and "실패" not in engine:
        header += f"💡 **활성 엔진:** `{engine}`\n\n"
        for s in stock_list:
            sign = "+" if s['change'] > 0 else ""
            emoji = "📈" if s['change'] >= 0 else "📉"
            
            # AI 답변 파싱
            analysis = "분석을 생성하지 못했습니다."
            for line in raw_res.split('\n'):
                if s['ticker'].lower() in line.lower():
                    analysis = line.split(':')[-1].strip() if ':' in line else line.strip()
                    break

            report_body += f"**{emoji} {s['ticker']}** | `${s['price']}` (**{sign}{s['change']}%**)\n"
            report_body += f"> {analysis}\n\n"
    else:
        header += f"⚠️ **분석 엔진 오류 ({engine})**\n\n"
        for s in stock_list:
            sign = "+" if s['change'] > 0 else ""
            report_body += f"**{s['ticker']}** | `${s['price']}` ({sign}{s['change']}%)\n> {s['news']}\n\n"

    send_to_discord(header + report_body + "━━━━━━━━━━━━━━━━━━━━")

if __name__ == "__main__":
    main()
