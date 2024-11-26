from stt import speech_to_text
from routing import get_directions
from tts import text_to_speech
from geocoding import validate_address
from gps import GPSManager
import time
"""
def main():
    destination = speech_to_text()  # STT로 목적지 받아오기
    if not destination:
        text_to_speech("목적지를 인식하지 못했습니다.")
        return

    current_location = input("현재 위치를 입력해주세요: ")

    # 주소 검증하여 좌표로 변환
    current_location_coords = validate_address(current_location)
    destination_coords = validate_address(destination)

    if current_location_coords and destination_coords:
        # get_directions 함수에 좌표 전달
        directions = get_directions(current_location_coords, destination_coords)

        if directions:
            for step in directions:
                text_to_speech(step)
        else:
            text_to_speech("경로를 찾을 수 없습니다.")
    else:
        text_to_speech("주소를 인식하지 못했습니다.")
"""
def main():
    # Windows용 GPS 관리자 초기화
    gps_manager = GPSManager()
    
    # 목적지 음성 인식
    destination = speech_to_text()
    if not destination:
        text_to_speech("목적지를 인식하지 못했습니다.")
        return
    
    # 목적지 주소를 좌표로 변환
    destination_coords = validate_address(destination)
    if not destination_coords:
        text_to_speech("목적지 주소를 인식하지 못했습니다.")
        return
    
    # 현재 위치 확인
    current_coords = gps_manager.get_current_location()
    if not current_coords:
        text_to_speech("현재 위치를 확인할 수 없습니다. Windows의 위치 서비스 설정을 확인해주세요.")
        return
    
    # 실시간 내비게이션 시작
    text_to_speech("경로 안내를 시작합니다.")
    
    try:
        while True:
            # 업데이트 시간 체크
            if not gps_manager.can_update():
                time.sleep(1)
                continue
            
            # 현재 GPS 위치 가져오기
            current_coords = gps_manager.get_current_location()
            if not current_coords:
                text_to_speech("위치 신호를 확인할 수 없습니다.")
                time.sleep(gps_manager.update_interval)
                continue
            
            # 목적지 도착 확인
            if gps_manager.is_near_destination(current_coords, destination_coords):
                text_to_speech("목적지에 도착했습니다.")
                break
            
            # 경로 업데이트가 필요한지 확인
            if gps_manager.should_update_route(current_coords):
                # 새로운 경로 가져오기
                directions = get_directions(current_coords, destination_coords)
                if directions:
                    # 첫 번째 안내만 음성으로 출력
                    text_to_speech(directions[0])
                else:
                    text_to_speech("경로를 찾을 수 없습니다.")
                    time.sleep(gps_manager.update_interval)
                    continue
                
                gps_manager.update_last_coords(current_coords)
            
    except KeyboardInterrupt:
        text_to_speech("경로 안내를 종료합니다.")
    except Exception as e:
        text_to_speech(f"오류가 발생했습니다: {str(e)}")


if __name__ == "__main__":
    main()
