import os
import google.generativeai as genai
import requests

# 1. 환경 설정
DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK_URL')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

genai.configure(api_key=GEMINI_API_KEY)

def send_discord(message):
    if DISCORD_WEBHOOK_URL:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": message})

def check_and_run():
    # 현재 준희님의 API 키로 부를 수 있는 '진짜 이름' 리스트를 뽑습니다.
    available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    
    # 2026년 기준, 가장 권장되는 이름인 'models/gemini-3-flash'를 먼저 찾습니다.
    target = 'models/gemini-3-flash'
    if target not in available_models:
        # 혹시 목록에 다른 이름이 있다면 그중 가장 좋은 걸로 자동 선택
        target = available_models[0]

    try:
        model = genai.GenerativeModel(target)
        # 이제 분석 시작!
        response = model.generate_content("2026년 미국 주식 시장의 특징을 한 문장으로 알려줘.")
        
        msg = f"✅ **연결 성공!**\n사용 중인 모델: `{target}`\n\n**AI 한 줄 분석:**\n{response.text}"
        send_discord(msg)
        
    except Exception as e:
        send_discord(f"🚨 아직도 에러가 나요: {e}\n사용 가능한 모델들: {available_models}")

if __name__ == "__main__":
    check_and_run()
