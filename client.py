import asyncio
import json
import websockets
from stt import STTManager
from tts import TTSManager
from gps import GPSManager
import signal
import sys
from config import load_config

# 전역 변수 초기화
stt_manager = STTManager()
tts_manager = TTSManager()
gps_manager = None
websocket_connection = None
navigation_active = False
config = load_config()

async def connect_websocket():
    """웹소켓 연결 설정"""
    try:
        return await websockets.connect(config['client']['server_url'])
    except Exception as e:
        print(f"웹소켓 연결 실패: {str(e)}")
        return None

async def voice_command_handler():
    """음성 명령어 처리 루프"""
    global navigation_active, websocket_connection
    
    while True:
        try:
            # 음성 명령어 대기
            command = stt_manager.listen_for_command()
            
            if command == "start_navigation":
                if not navigation_active:
                    navigation_active = True
                    tts_manager.text_to_speech("목적지를 말씀해 주세요")
                    
                    # 목적지 음성 인식
                    destination = stt_manager.listen_for_destination()
                    if destination:
                        # 웹소켓 연결 확인 및 재연결
                        if not websocket_connection:
                            websocket_connection = await connect_websocket()
                        
                        if websocket_connection:
                            await websocket_connection.send(json.dumps({
                                "type": "destination",
                                "data": destination
                            }))
                    else:
                        tts_manager.text_to_speech("목적지를 인식하지 못했습니다.")
                        navigation_active = False
                        
            elif command == "stop_navigation":
                if navigation_active:
                    navigation_active = False
                    if websocket_connection:
                        await websocket_connection.send(json.dumps({
                            "type": "command",
                            "data": "stop_navigation"
                        }))
                    tts_manager.text_to_speech("경로 안내를 종료합니다.")
                    
            elif command == "reroute":
                if navigation_active and websocket_connection:
                    await websocket_connection.send(json.dumps({
                        "type": "command",
                        "data": "reroute"
                    }))
                    
            await asyncio.sleep(0.1)
            
        except Exception as e:
            print(f"명령어 처리 중 오류 발생: {str(e)}")
            await asyncio.sleep(1)

async def gps_data_sender():
    """GPS 데이터 전송 루프"""
    global navigation_active, websocket_connection
    
    while True:
        try:
            if navigation_active and websocket_connection:
                if gps_manager.can_update():
                    current_coords = gps_manager.get_current_location()
                    if current_coords:
                        await websocket_connection.send(json.dumps({
                            "type": "location",
                            "data": {
                                "latitude": current_coords[0],
                                "longitude": current_coords[1]
                            }
                        }))
            await asyncio.sleep(1)
            
        except Exception as e:
            print(f"GPS 데이터 전송 중 오류 발생: {str(e)}")
            await asyncio.sleep(1)

async def websocket_receiver():
    """웹소켓 메시지 수신 처리"""
    global navigation_active, websocket_connection
    
    while True:
        try:
            if websocket_connection:
                message = await websocket_connection.recv()
                data = json.loads(message)
                
                if data["type"] == "voice_guidance":
                    tts_manager.text_to_speech(data["message"])
                elif data["type"] == "navigation_end":
                    tts_manager.text_to_speech(data["message"])
                    navigation_active = False
                    
        except Exception as e:
            print(f"웹소켓 수신 중 오류 발생: {str(e)}")
            websocket_connection = None
            await asyncio.sleep(1)

async def main():
    """메인 실행 함수"""
    global gps_manager, websocket_connection
    
    try:
        # GPS 매니저 초기화
        gps_manager = GPSManager(
            port=config['client']['gps']['port'],
            baudrate=config['client']['gps']['baudrate']
        )
        
        # 무한 재연결 루프
        while True:
            try:
                websocket_connection = await connect_websocket()
                if websocket_connection:
                    print("서버에 연결되었습니다.")
                    
                    # 모든 태스크 동시 실행
                    await asyncio.gather(
                        voice_command_handler(),
                        gps_data_sender(),
                        websocket_receiver()
                    )
                else:
                    print("서버 연결 실패. 재시도 중...")
                    await asyncio.sleep(5)
                    
            except websockets.exceptions.ConnectionClosed:
                print("서버와의 연결이 끊어졌습니다. 재연결 시도 중...")
                websocket_connection = None
                await asyncio.sleep(5)
                
            except Exception as e:
                print(f"예기치 않은 오류 발생: {str(e)}")
                await asyncio.sleep(5)
                
    except KeyboardInterrupt:
        print("\n프로그램을 종료합니다...")
    except Exception as e:
        print(f"치명적인 오류 발생: {str(e)}")
    finally:
        if gps_manager and gps_manager.ser:
            gps_manager.ser.close()
        if websocket_connection:
            await websocket_connection.close()

def signal_handler(sig, frame):
    """시그널 핸들러"""
    print("\n프로그램을 종료합니다...")
    if gps_manager and gps_manager.ser:
        gps_manager.ser.close()
    sys.exit(0)

if __name__ == "__main__":
    # 시그널 핸들러 등록
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 비동기 이벤트 루프 시작
    asyncio.run(main())