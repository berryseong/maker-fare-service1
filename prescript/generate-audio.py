import os
import json
import asyncio
import edge_tts

# 현재 스크립트 위치(prescript) 기준 상위 폴더(프로젝트 루트) 경로 계산
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))

JSON_PATH = os.path.join(PROJECT_ROOT, "characters.json")
AUDIO_DIR = os.path.join(PROJECT_ROOT, "assets", "audio")

# 오디오 저장 폴더 생성 (없을 경우 자동 생성)
os.makedirs(AUDIO_DIR, exist_ok=True)

async def generate_all_tts():
    if not os.path.exists(JSON_PATH):
        print(f"[오류] {JSON_PATH} 파일을 찾을 수 없습니다.")
        return

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        character_db = json.load(f)

    print("=== 스카우터 오프라인 음성(MP3) 사전 생성 시작 ===")
    
    for char_key, char_info in character_db.items():
        tts_text = char_info.get("tts_text", "")
        if not tts_text:
            continue
            
        file_path = os.path.join(AUDIO_DIR, f"{char_key}.mp3")
        print(f"[생성 중] {char_info.get('name', char_key)}: '{tts_text}' -> {char_key}.mp3")
        
        # 한국어 남성 음성(InJoonNeural)으로 MP3 변환 및 저장
        communicate = edge_tts.Communicate(tts_text, "ko-KR-InJoonNeural")
        await communicate.save(file_path)

    print("\n[완료] 모든 캐릭터의 오디오 파일이 assets/audio/ 에 성공적으로 저장되었습니다!")

if __name__ == "__main__":
    asyncio.run(generate_all_tts())