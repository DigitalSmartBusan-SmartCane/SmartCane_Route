import asyncio
import json
import websockets
import logging
from datetime import datetime
from typing import Optional, Dict
import signal
import sys
from config import load_config
from stt import STTManager
from tts import TTSManager

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()  # FileHandler 제거
    ]
)
logger = logging.getLogger('NavigationClient')

class NavigationClient:
    def __init__(self):
        """내비게이션 클라이언트 초기화"""
        self.config = load_config()
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.navigation_active = False
        
        # 부경대학교 위치로 고정
        self.current_location = {
            "latitude": 35.1336,
            "longitude": 129.1030
        }
        
        # 각 매니저 초기화
        self.stt_manager = STTManager(
            device_index=self.config['client']['audio']['input_device']
        )
        self.tts_manager = TTSManager()
        
        # 상태 변수
        self.should_reconnect = True
        self.is_connected = False

    async def connect(self) -> None:
        """서버 연결"""
        while self.should_reconnect:
            try:
                if not self.is_connected:
                    self.websocket = await websockets.connect(
                        self.config['client']['server_url']
                    )
                    self.is_connected = True
                    logger.info("서버에 연결되었습니다")
                    
                    # 모든 태스크 시작
                    await asyncio.gather(
                        self.handle_voice_command(),
                        self.handle_server_messages()
                    )
            except Exception as e:
                logger.error(f"서버 연결 실패: {str(e)}")
                self.is_connected = False
                await asyncio.sleep(5)  # 재연결 전 대기

    async def handle_voice_command(self) -> None:
        """음성 명령어 처리"""
        while self.is_connected:
            try:
                command = self.stt_manager.listen_for_command()
                if command == "start_navigation":
                    if not self.navigation_active:
                        self.navigation_active = True
                        self.tts_manager.text_to_speech("목적지를 말씀해 주세요")
                        
                        destination = self.stt_manager.listen_for_destination()
                        if destination:
                            # 웹소켓 연결 상태 확인
                            if self.websocket and self.websocket.open:
                                # 목적지 정보 전송
                                await self.websocket.send(json.dumps({
                                    "type": "destination",
                                    "data": destination
                                }))
                                
                                # 현재 위치(부경대학교) 전송
                                await self.websocket.send(json.dumps({
                                    "type": "location",
                                    "data": self.current_location
                                }))
                                
                                self.tts_manager.text_to_speech("경로를 탐색합니다")
                            else:
                                logger.error("웹소켓 연결이 없거나 닫혀있습니다")
                                self.navigation_active = False
                        else:
                            self.tts_manager.text_to_speech("목적지를 인식하지 못했습니다")
                            self.navigation_active = False
                
                await asyncio.sleep(0.1)
                    
            except websockets.exceptions.ConnectionClosed:
                logger.warning("서버와의 연결이 끊어졌습니다")
                self.is_connected = False
                break
            except Exception as e:
                logger.error(f"음성 명령어 처리 중 오류: {str(e)}")
                await asyncio.sleep(1)

    async def handle_server_messages(self) -> None:
        """서버 메시지 처리"""
        while self.is_connected:
            try:
                message = await self.websocket.recv()
                data = json.loads(message)
                
                if data["type"] == "voice_guidance":
                    self.tts_manager.text_to_speech(data["message"])
                elif data["type"] == "navigation_end":
                    self.tts_manager.text_to_speech(data["message"])
                    self.navigation_active = False
                    
            except websockets.exceptions.ConnectionClosed:
                logger.warning("서버와의 연결이 끊어졌습니다")
                self.is_connected = False
                break
            except Exception as e:
                logger.error(f"서버 메시지 처리 중 오류: {str(e)}")
                await asyncio.sleep(1)

    def cleanup(self) -> None:
        """리소스 정리"""
        self.should_reconnect = False
        self.is_connected = False
        if self.websocket:
            asyncio.create_task(self.websocket.close())

def signal_handler(signum, frame):
    """시그널 핸들러"""
    print("\n프로그램을 종료합니다...")
    if client:
        client.cleanup()
    sys.exit(0)

client = None

def main():
    global client
    try:
        # 시그널 핸들러 등록
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # 클라이언트 시작
        client = NavigationClient()
        asyncio.get_event_loop().run_until_complete(client.connect())
        
    except KeyboardInterrupt:
        print("\n프로그램을 종료합니다...")
        if client:
            client.cleanup()
    except Exception as e:
        logger.error(f"예기치 않은 오류 발생: {str(e)}")
        if client:
            client.cleanup()

if __name__ == "__main__":
    main()