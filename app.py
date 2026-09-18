import cv2
import json
import os
import asyncio
import edge_tts
import pygame
import threading
import time
import requests
import numpy as np
import textwrap
from scouter_overlay import draw_scouter_overlay
from PIL import ImageFont, ImageDraw, Image

# 1. 오디오 시스템 및 캐릭터 DB 로드
pygame.mixer.init()

with open("characters.json", "r", encoding="utf-8") as f:
    character_db = json.load(f)


class MJPEGStream:
    """백그라운드 스레드에서 계속 프레임을 받아 최신 프레임만 보관.
    메인 루프의 read()는 네트워크 상태와 무관하게 즉시 반환되므로
    화면(cv2.imshow)이나 키 입력(waitKey)이 멈추지 않는다."""

    def __init__(self, url, timeout=5, reconnect_delay=1.0):
        self.url = url
        self.timeout = timeout
        self.reconnect_delay = reconnect_delay
        self.frame = None
        self.lock = threading.Lock()
        self.running = True
        self.thread = threading.Thread(target=self._update, daemon=True)
        self.thread.start()

    def _update(self):
        while self.running:
            buf = b""
            try:
                resp = requests.get(self.url, stream=True, timeout=self.timeout)
                for chunk in resp.iter_content(chunk_size=4096):
                    if not self.running:
                        break
                    if not chunk:
                        continue
                    buf += chunk

                    start = buf.find(b'\xff\xd8')  # JPEG 시작
                    end = buf.find(b'\xff\xd9')    # JPEG 끝
                    if start != -1 and end != -1 and end > start:
                        jpg = buf[start:end + 2]
                        buf = buf[end + 2:]
                        frame = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
                        if frame is not None:
                            with self.lock:
                                self.frame = frame
                    elif start == -1:
                        # 시작 마커가 없는 쓰레기 데이터는 버림 (버퍼 무한 증가 방지)
                        buf = buf[-2:]
                resp.close()
            except (requests.exceptions.RequestException, ConnectionError, OSError) as e:
                print(f"[스트림] 연결 끊김, {self.reconnect_delay}초 후 재연결 시도... ({e})")
            except Exception as e:
                print(f"[스트림] 알 수 없는 오류: {e}")

            if self.running:
                time.sleep(self.reconnect_delay)

    def isOpened(self):
        return self.running

    def read(self):
        with self.lock:
            if self.frame is None:
                return False, None
            return True, self.frame.copy()

    def release(self):
        self.running = False


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


def speak_text_async(char_key):
    def _play():
        file_path = os.path.join("assets", "audio", f"{char_key}.mp3")
        if os.path.exists(file_path):
            pygame.mixer.music.load(file_path)
            pygame.mixer.music.play()
        else:
            print(f"[경고] {file_path} 음성 파일이 존재하지 않습니다.")

    threading.Thread(target=_play, daemon=True).start()

# --- 한글 UI 캐싱 렌더링 함수 ---
ui_overlay_cache = None
last_char_name = None

def draw_fast_korean_ui(frame, char_data):
    global ui_overlay_cache, last_char_name
    
    # 캐릭터가 바뀔 때만 딱 1번 투명 이미지 생성 (렉 발생 원천 차단)
    if last_char_name != char_data['name']:
        img_pil = Image.new("RGBA", (frame.shape[1], frame.shape[0]), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img_pil)
        
        # 1. 상단용(24pt) 및 하단 설명용(18pt) Bold 폰트 각각 생성
        try:
            font_large = ImageFont.truetype("malgunbd.ttf", 24)
            font_small = ImageFont.truetype("malgunbd.ttf", 18)
        except:
            try:
                font_large = ImageFont.truetype("malgun.ttf", 24)
                font_small = ImageFont.truetype("malgun.ttf", 18)
            except:
                font_large = ImageFont.load_default()
                font_small = ImageFont.load_default()
            
        color_bgra = (0, 215, 255, 255) # 노란색 (BGR 기준)
        
        def draw_centered(text, y_pos, font):
            try:
                w = draw.textlength(text, font=font)
            except AttributeError:
                w = font.getbbox(text)[2] - font.getbbox(text)[0]
            x = (frame.shape[1] - int(w)) // 2
            draw.text((x, y_pos), text, font=font, fill=color_bgra)
            
        # 2. 최상단 배치 (큰 폰트 24pt 적용)
        draw_centered(f"이름: {char_data['name']}", 15, font_large)
        draw_centered(f"전투력 : {char_data['power']}", 45, font_large)
        
        # 3. 하단 설명 텍스트 (줄당 글자 수를 32자로 늘려 가로 폭 넓게 활용 & 작은 폰트 18pt 적용)
        desc_text = char_data['tts_text']
        lines = textwrap.wrap(desc_text, width=32)
        
        line_height = 24  # 18pt 폰트에 맞춘 알맞은 줄간격
        start_y = frame.shape[0] - (len(lines) * line_height + 20)
        
        for i, line in enumerate(lines):
            draw_centered(line, start_y + i * line_height, font_small)
        
        ui_overlay_cache = np.array(img_pil)
        last_char_name = char_data['name']
        
    if ui_overlay_cache is not None:
        alpha = ui_overlay_cache[:, :, 3] / 255.0
        for c in range(3):
            frame[:, :, c] = (alpha * ui_overlay_cache[:, :, c] + (1 - alpha) * frame[:, :, c]).astype(np.uint8)
            
    return frame

# 4. 웹캠 실행 및 스페이스바 수동 측정 루프
# 기존 (노트북 내장 웹캠)
cap = cv2.VideoCapture(0)

# 수정 (ESP32-S3 무선 스트리밍 주소 사용 시)
# stream_url = "http://192.168.1.50:81/stream"
# cap = MJPEGStream(stream_url)

MATCH_THRESHOLD = 30  # 매칭 기준점 개수
current_char_data = None
filter_mode = 0  
filter_colors = [None, (255, 100, 0), (0, 255, 0), (200, 50, 255), (255, 0, 150)]

print("=== 스카우터 비전 인식 서비스 구동 ===")
print("카메라 창을 클릭한 뒤 [SPACE]를 누르면 측정을 시작합니다. ('t': 필터 변경, 'q': 종료)")

try:
    while cap.isOpened():
        ret, frame = cap.read()

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        if key == ord('t'):
            filter_mode = (filter_mode + 1) % 5

        if not ret:
            # 아직 첫 프레임을 못 받았거나 재연결 중 -> 루프는 계속 돌되 이번 프레임만 스킵
            continue

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
                    current_char_data = character_db[best_match_char]
                    print(f"[측정 성공] {current_char_data['name']} (전투력: {current_char_data['power']})")
                    speak_text_async(best_match_char)
                else:
                    current_char_data = None
                    print("[측정 실패] 인식된 캐릭터 카드가 없습니다.")

        # 1. 색상 필터 적용 ('t' 키 조작 시)
        if filter_mode > 0:
            overlay = np.full_like(frame, filter_colors[filter_mode])
            frame = cv2.addWeighted(frame, 0.7, overlay, 0.3, 0)

        # 2. 노란색 스카우터 삼각형 오버레이
        draw_scouter_overlay(frame)

        # 3. 인식된 상태일 때만 중앙에 노란 한글 UI 표시
        if current_char_data is not None:
            frame = draw_fast_korean_ui(frame, current_char_data)

        cv2.imshow("Dragon Ball Scouter - Service 1", frame)

except KeyboardInterrupt:
    print("\n[알림] 사용자에 의해 스카우터 프로그램이 종료되었습니다.")
finally:
    cap.release()
    cv2.destroyAllWindows()