from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from typing import List, Dict, Any, Optional
import asyncio
import json
import logging
import signal
import sys
import tkinter as tk
from datetime import datetime
import yaml
from server_manager import OSRMServer
from routing import RouteManager
from geocoding import GeocodingManager
from gui import NavigationGUI
from config import load_config

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('server.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('NavigationServer')

# FastAPI 앱 초기화
app = FastAPI()

# 전역 변수
osrm_server: Optional[OSRMServer] = None
route_manager: Optional[RouteManager] = None
geocoding_manager: Optional[GeocodingManager] = None
navigation_gui: Optional[NavigationGUI] = None
config = load_config()

class NavigationState:
    """네비게이션 상태 관리 클래스"""
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

nav_state = NavigationState()

class ConnectionManager:
    """웹소켓 연결 관리 클래스"""
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """웹소켓 연결 수락"""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"새로운 클라이언트 연결됨: {len(self.active_connections)}개의 연결")

    def disconnect(self, websocket: WebSocket):
        """웹소켓 연결 해제"""
        self.active_connections.remove(websocket)
        logger.info(f"클라이언트 연결 해제됨: {len(self.active_connections)}개의 연결")

    async def broadcast(self, message: Dict[str, Any]):
        """모든 클라이언트에게 메시지 브로드캐스트"""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"브로드캐스트 중 오류 발생: {str(e)}")
                disconnected.append(connection)
        
        # 끊어진 연결 제거
        for connection in disconnected:
            self.disconnect(connection)

manager = ConnectionManager()

def init_gui():
    """GUI 초기화"""
    global navigation_gui
    root = tk.Tk()
    navigation_gui = NavigationGUI(root)
    return root

async def run_gui():
    """GUI 실행"""
    root = init_gui()
    while True:
        try:
            root.update()
            await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"GUI 업데이트 중 오류 발생: {str(e)}")
            await asyncio.sleep(1)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """웹소켓 엔드포인트"""
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message["type"] == "destination":
                # 목적지 설정
                destination = message["data"]
                coords = geocoding_manager.validate_address(destination)
                if coords:
                    nav_state.set_destination(coords)
                    if navigation_gui:
                        navigation_gui.set_destination(
                            (coords['latitude'], coords['longitude']),
                            coords['address']
                        )
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
                # GPS 위치 업데이트
                nav_state.update_location(message["data"])
                if navigation_gui and nav_state.destination:
                    current_location = (
                        message["data"]["latitude"],
                        message["data"]["longitude"]
                    )
                    
                    # 경로 업데이트 필요 여부 확인
                    if should_update_route(current_location, nav_state.route):
                        new_route = route_manager.get_directions(
                            current_location,
                            nav_state.destination
                        )
                        if new_route:
                            nav_state.route = new_route
                            navigation_gui.update_route(new_route)
                            
                            # 음성 안내 메시지 전송
                            await websocket.send_json({
                                "type": "voice_guidance",
                                "message": new_route['steps'][0]
                            })
                    
                    # 목적지 도착 확인
                    if is_near_destination(current_location, nav_state.destination):
                        await websocket.send_json({
                            "type": "navigation_end",
                            "message": "목적지에 도착했습니다."
                        })
                        nav_state.clear()

            elif message["type"] == "command":
                if message["data"] == "stop_navigation":
                    nav_state.clear()
                    if navigation_gui:
                        navigation_gui.stop_navigation()
                elif message["data"] == "reroute":
                    if nav_state.current_location and nav_state.destination:
                        new_route = route_manager.get_directions(
                            nav_state.current_location,
                            nav_state.destination
                        )
                        if new_route:
                            nav_state.route = new_route
                            if navigation_gui:
                                navigation_gui.update_route(new_route)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"웹소켓 처리 중 오류 발생: {str(e)}")
        manager.disconnect(websocket)

def should_update_route(current_location: tuple, current_route: Dict) -> bool:
    """경로 업데이트 필요 여부 확인"""
    if not current_route:
        return True
    # 실제 구현에서는 더 복잡한 로직 필요
    return True

def is_near_destination(current: tuple, destination: tuple, threshold: float = 20.0) -> bool:
    """목적지 근처인지 확인"""
    from math import radians, sin, cos, sqrt, atan2
    
    R = 6371e3  # 지구 반지름 (미터)
    φ1 = radians(current[0])
    φ2 = radians(destination[0])
    Δφ = radians(destination[0] - current[0])
    Δλ = radians(destination[1] - current[1])

    a = sin(Δφ/2) * sin(Δφ/2) + \
        cos(φ1) * cos(φ2) * \
        sin(Δλ/2) * sin(Δλ/2)
    c = 2 * atan2(sqrt(a), sqrt(1-a))

    distance = R * c
    return distance <= threshold

@app.get("/status")
async def get_status():
    """서버 상태 확인 엔드포인트"""
    return {
        "active": nav_state.is_active,
        "destination": nav_state.destination,
        "current_location": nav_state.current_location,
        "last_update": nav_state.last_update.isoformat(),
        "osrm_status": "running" if osrm_server and osrm_server.is_server_running() else "stopped"
    }

@app.post("/reroute")
async def reroute():
    """경로 재탐색 엔드포인트"""
    if nav_state.current_location and nav_state.destination:
        new_route = route_manager.get_directions(
            nav_state.current_location,
            nav_state.destination
        )
        if new_route:
            nav_state.route = new_route
            if navigation_gui:
                navigation_gui.update_route(new_route)
            return {"success": True, "message": "경로가 재설정되었습니다."}
    return {"success": False, "message": "경로를 재설정할 수 없습니다."}

@app.on_event("startup")
async def startup_event():
    """서버 시작 시 실행되는 이벤트"""
    global osrm_server, route_manager, geocoding_manager
    try:
        # OSRM 서버 시작
        osrm_server = OSRMServer(config)
        if not osrm_server.start():
            logger.error("OSRM 서버 시작 실패")
            sys.exit(1)

        # 매니저 초기화
        route_manager = RouteManager()
        geocoding_manager = GeocodingManager()
        
        # GUI 시작
        asyncio.create_task(run_gui())
        
        logger.info("서버가 성공적으로 시작되었습니다.")
        
    except Exception as e:
        logger.error(f"서버 시작 중 오류 발생: {str(e)}")
        sys.exit(1)

@app.on_event("shutdown")
async def shutdown_event():
    """서버 종료 시 실행되는 이벤트"""
    if osrm_server:
        osrm_server.stop()
    logger.info("서버가 종료되었습니다.")

def signal_handler(signum, frame):
    """시그널 처리"""
    logger.info("\n서버를 종료합니다...")
    if osrm_server:
        osrm_server.stop()
    sys.exit(0)

if __name__ == "__main__":
    # 시그널 핸들러 등록
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # FastAPI 서버 시작
    import uvicorn
    uvicorn.run(
        app,
        host=config['server']['host'],
        port=config['server']['port']
    )