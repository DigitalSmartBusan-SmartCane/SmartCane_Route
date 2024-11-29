# main.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import json
from typing import List, Dict, Any, Optional
import asyncio
import uvicorn
import yaml
from server_manager import OSRMServer
import signal
import sys
from config import load_config
import threading
from datetime import datetime
import logging
from gui import NavigationGUI
import tkinter as tk
from routing import RouteManager
from geocoding import GeocodingManager


# 로깅 설정
logging.basicConfig(
   level=logging.INFO,
   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
   handlers=[
       logging.FileHandler('navigation.log'),
       logging.StreamHandler()
   ]
)
logger = logging.getLogger('NavigationMain')

class NavigationState:
   def __init__(self):
       self.destination = None
       self.current_location = None
       self.route = None
       self.is_active = False
       self.last_update = datetime.now()

   def update_location(self, location: Dict[str, float]):
       """위치 정보 업데이트"""
       self.current_location = (location['latitude'], location['longitude'])
       self.last_update = datetime.now()

   def set_destination(self, destination: Dict[str, Any]):
       """목적지 설정"""
       self.destination = (destination['latitude'], destination['longitude'])
       self.is_active = True

   def clear(self):
       """상태 초기화"""
       self.destination = None
       self.current_location = None
       self.route = None
       self.is_active = False

class NavigationSystem:
   def __init__(self):
       self.config = load_config()
       self.root = tk.Tk()
       self.setup_managers()
       self.gui = None
       self.websocket_manager = None
       self.nav_state = NavigationState()

   def setup_managers(self):
       """매니저 초기화"""
       self.route_manager = RouteManager()
       self.geocoding_manager = GeocodingManager()

   def handle_destination(self, destination: str, websocket: WebSocket):
       """목적지 처리"""
       coords = self.geocoding_manager.validate_address(destination)
       if coords:
           self.nav_state.set_destination(coords)
           if self.gui:
               self.gui.set_destination((coords['latitude'], coords['longitude']), coords['address'])
           return True
       return False

class ConnectionManager:
   def __init__(self):
       self.active_connections: List[WebSocket] = []

   async def connect(self, websocket: WebSocket):
       await websocket.accept()
       self.active_connections.append(websocket)

   def disconnect(self, websocket: WebSocket):
       self.active_connections.remove(websocket)

   async def broadcast(self, message: str):
       for connection in self.active_connections:
           await connection.send_text(message)

manager = ConnectionManager()
app = FastAPI()
navigation_system = None
osrm_server = None

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
   await manager.connect(websocket)
   try:
       while True:
           data = await websocket.receive_text()
           message = json.loads(data)
           
           if message["type"] == "destination":
               if navigation_system.handle_destination(message["data"], websocket):
                   await websocket.send_json({
                       "type": "voice_guidance",
                       "message": "목적지가 설정되었습니다."
                   })
               else:
                   await websocket.send_json({
                       "type": "voice_guidance",
                       "message": "목적지를 찾을 수 없습니다."
                   })

           elif message["type"] == "location":
               current_location = (
                   message["data"]["latitude"],
                   message["data"]["longitude"]
               )
               navigation_system.gui.update_current_location(current_location)

   except WebSocketDisconnect:
       manager.disconnect(websocket)
   except Exception as e:
       logger.error(f"위치 업데이트 처리 중 오류 발생: {str(e)}")

def run_fastapi_server():
    config = load_config()
    uvicorn.run(
        app,
        host=config['server']['host'],
        port=config['server']['port'],
        log_level="info"
    )

def signal_handler(signum, frame):
    """종료 시그널 처리"""
    logger.info("\n프로그램을 종료합니다...")
    if osrm_server:
        osrm_server.stop()
    sys.exit(0)

def main():
    global navigation_system, osrm_server

    try:
        # OSRM 서버 시작
        osrm_server = OSRMServer()
        if not osrm_server.start():
            logger.error("OSRM 서버 시작 실패")
            return

        # 내비게이션 시스템 초기화
        navigation_system = NavigationSystem()
        navigation_system.gui = NavigationGUI(navigation_system.root)

        # FastAPI 서버 실행
        server_thread = threading.Thread(target=run_fastapi_server, daemon=True)
        server_thread.start()

        # GUI 메인 루프 시작
        navigation_system.root.mainloop()

    except Exception as e:
        logger.error(f"프로그램 실행 중 오류 발생: {str(e)}")
    finally:
        # 서버 종료
        if osrm_server:
            osrm_server.stop()

if __name__ == "__main__":
    # 시그널 핸들러 등록
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    main()