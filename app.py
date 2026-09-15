import cv2
import json
import os
import asyncio
import edge_tts
import pygame
import threading

# 1. 오디오 시스템 및 캐릭터 DB 로드
pygame.mixer.init()

with open("characters.json", "r", encoding="utf-8") as f:
    character_db = json.load(f)

# 2. ORB 특징점 검출기 설정
orb = cv2.ORB_create(nfeatures=1500)
bf = cv2.BFMatcher(cv2.NORM_HAMMING)

# 3. Reference 이미지 특징점 사전 계산
ref_features = {}
ref_images_dir = os.path.join("assets", "ref_images")

print("=== 기준 카드 이미지 특징점 로딩 중... ===")
for char_key, char_info in character_db.items():
    for img_name in char_info["images"]:
        img_path = os.path.join(ref_images_dir, img_name)
        if os.path.exists(img_path):
            img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
            if img is not None:
                kp, des = orb.detectAndCompute(img, None)
                if des is not None:
                    ref_features[img_name] = {
                        "char_key": char_key,
                        "des": des
                    }
        else:
            print(f"경고: {img_path} 파일을 찾을 수 없습니다.")

print(f"총 {len(ref_features)}개의 이미지 특징점 로딩 완료!\n")

is_speaking = False

# 백그라운드 음성 출력 함수 (화면 멈춤 방지)
def run_tts_in_thread(text):
    global is_speaking
    is_speaking = True
    
    async def _speak():
        file_path = "temp_speak.mp3"
        communicate = edge_tts.Communicate(text, "ko-KR-InJoonNeural")
        await communicate.save(file_path)
        
        pygame.mixer.music.load(file_path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)
        pygame.mixer.music.unload()
        if os.path.exists(file_path):
            os.remove(file_path)
            
    asyncio.run(_speak())
    is_speaking = False

def speak_text_async(text):
    t = threading.Thread(target=run_tts_in_thread, args=(text,), daemon=True)
    t.start()

# 4. 웹캠 실행 및 스페이스바 수동 측정 루프
# 기존 (노트북 내장 웹캠)
# cap = cv2.VideoCapture(0)

# 수정 (ESP32-S3 무선 스트리밍 주소)
stream_url = "http://172.28.26.178:81/stream"
cap = cv2.VideoCapture(stream_url)

MATCH_THRESHOLD = 30  # 매칭 기준점 개수
last_detected_info = "Press SPACE to Scan Target"

print("=== 스카우터 비전 인식 서비스 구동 ===")
print("카메라 창을 클릭한 뒤 [SPACE]를 누르면 측정을 시작합니다. ('q' 또는 Ctrl+C로 종료)")

try:
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        key = cv2.waitKey(1) & 0xFF

        # 스페이스바(Space) 입력 시 측정 실행
        if key == ord(' '):
            if is_speaking:
                print("[알림] 음성 안내가 출력 중입니다. 잠시 후 다시 시도하세요.")
            else:
                print("\n[스카우터 타겟 스캔 시작...]")
                gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                kp_frame, des_frame = orb.detectAndCompute(gray_frame, None)

                best_match_char = None
                max_matches = 0

                if des_frame is not None and len(des_frame) > 10:
                    for img_name, ref_data in ref_features.items():
                        matches = bf.knnMatch(ref_data["des"], des_frame, k=2)
                        good_matches = []
                        for m_pair in matches:
                            if len(m_pair) == 2:
                                m, n = m_pair
                                if m.distance < 0.7 * n.distance:
                                    good_matches.append(m)

                        if len(good_matches) > max_matches and len(good_matches) >= MATCH_THRESHOLD:
                            max_matches = len(good_matches)
                            best_match_char = ref_data["char_key"]

                if best_match_char:
                    char_data = character_db[best_match_char]
                    last_detected_info = f"{char_data['name']} | POWER: {char_data['power']}"
                    print(f"[측정 성공] {char_data['name']} (전투력: {char_data['power']})")
                    speak_text_async(char_data["tts_text"])
                else:
                    last_detected_info = "TARGET NOT FOUND"
                    print("[측정 실패] 인식된 캐릭터 카드가 없습니다.")

        # HUD UI 화면 표시
        cv2.putText(frame, "Press 'SPACE': Scan | Press 'q': Quit", (20, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        
        # 측정 결과에 따라 텍스트 색상 변경 (인식 성공: 녹색, 실패: 빨간색)
        status_color = (0, 255, 0) if "POWER" in last_detected_info else (0, 0, 255)
        cv2.putText(frame, f"STATUS: {last_detected_info}", (20, 70), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)

        cv2.imshow("Dragon Ball Scouter - Service 1", frame)

        if key == ord('q'):
            break

except KeyboardInterrupt:
    print("\n[알림] 사용자에 의해 스카우터 프로그램이 종료되었습니다.")
finally:
    cap.release()
    cv2.destroyAllWindows()