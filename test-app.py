import cv2
import asyncio
import edge_tts
import pygame
import os

# 오디오 시스템 초기화
pygame.mixer.init()

async def speak(text):
    file_path = "temp_test.mp3"
    communicate = edge_tts.Communicate(text, "ko-KR-InJoonNeural")
    await communicate.save(file_path)
    
    pygame.mixer.music.load(file_path)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        pygame.time.Clock().tick(10)
    pygame.mixer.music.unload()
    if os.path.exists(file_path):
        os.remove(file_path)

# 0번 기본 카메라 연결
cap = cv2.VideoCapture(0)

print("=== 스카우터 1기본 테스트 ===")
print("화면 창이 뜨면 키보드 's'를 눌러 음성을 테스트하세요. ('q' 누르면 종료)")

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        print("카메라 화면을 읽을 수 없습니다. 웹캠 연결을 확인해 주세요.")
        break

    cv2.putText(frame, "Press 's': Sound Test | Press 'q': Quit", (10, 30), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    cv2.imshow("Service 1 - Test Window", frame)

    key = cv2.waitKey(1) & 0xFF
    if key == ord('s'):
        print("음성 출력 시작...")
        asyncio.run(speak("스카우터 음성 테스트입니다. 시스템이 정상 작동합니다."))
    elif key == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()