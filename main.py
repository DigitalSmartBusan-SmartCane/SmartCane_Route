# main.py
import logging
import signal
import sys
import threading
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
import json
import tkinter as tk
from typing import Tuple, List, Optional

from server import ConnectionManager, NavigationSystem
from server_manager import OSRMServer  # OSRMServer가 정의된 모듈을 import
from gui import MapGUI  # GUI 관련 클래스 import
from config import ConfigManager  # 구성 파일 로드 클래스 import

# 로깅 설정
logging.basicConfig(
    level=logging.DEBUG,  # 필요에 따라 INFO로 변경 가능
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('navigation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('NavigationMain')

# FastAPI 앱 초기화
app = FastAPI()

# 정적 파일 및 템플릿 설정
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# 전역 인스턴스 생성
manager = ConnectionManager()
navigation_gui = None  # GUI 인스턴스는 나중에 초기화
navigation_system = None  # NavigationSystem 인스턴스는 나중에 초기화
osrm_server = None
config_manager = ConfigManager()

def update_gui(current_location: Tuple[float, float], 
               route: Optional[List[Tuple[float, float]]] = None,
               instruction: str = None):
    """GUI 업데이트 함수"""
    try:
        logger.debug(f"GUI 업데이트 호출: 위치={current_location}, 경로={'있음' if route else '없음'}, 안내='{instruction}'")
        if navigation_gui:
            # destination 정보를 navigation_system에서 가져옴
            destination = navigation_system.nav_state.destination if navigation_system else None
            navigation_gui.update_map_async(current_location, route, destination)
            if instruction:
                print(f"\n경로 안내: {instruction}")
                logger.info(f"경로 안내: {instruction}")
    except Exception as e:
        logger.error(f"GUI 업데이트 중 오류 발생: {str(e)}")

def initialize_navigation_system():
    """NavigationSystem 초기화"""
    global navigation_system
    navigation_system = NavigationSystem(on_update=update_gui)

@app.get("/", response_class=HTMLResponse)
async def get_map(request: Request):
    """map.html을 렌더링"""
    try:
        return templates.TemplateResponse("map.html", {"request": request})
    except Exception as e:
        logger.error(f"Error rendering map.html: {str(e)}")
        return HTMLResponse(content="Error loading map", status_code=500)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    logger.info("connection open")
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            message_type = message.get("type")
            logger.debug(f"수신된 메시지 타입: {message_type}")

            if message_type == "location":
                location_data = message.get("data")
                if location_data:
                    success = navigation_system.update_location(location_data)
                    if success:
                        await websocket.send_json({
                            "type": "ack",
                            "message": "위치 업데이트 완료"
                        })
                    else:
                        await websocket.send_json({
                            "type": "error",
                            "message": "위치 업데이트 실패"
                        })
                else:
                    await websocket.send_json({
                        "type": "error",
                        "message": "위치 데이터 누락"
                    })

            elif message_type == "destination":
                destination_data = message.get("data")
                if destination_data:
                    success = navigation_system.handle_destination(destination_data)
                    if success:
                        await websocket.send_json({
                            "type": "ack",
                            "message": "목적지 설정 완료"
                        })
                    else:
                        await websocket.send_json({
                            "type": "error",
                            "message": "목적지 설정 실패"
                        })

            else:
                logger.warning(f"알 수 없는 메시지 타입: {message_type}")
                await websocket.send_json({
                    "type": "error",
                    "message": f"알 수 없는 메시지 타입: {message_type}"
                })

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("서버와의 연결이 종료되었습니다")
    except Exception as e:
        logger.error(f"WebSocket 처리 중 오류 발생: {str(e)}")
        await websocket.close()
    finally:
        logger.info("WebSocket connection closed")

def run_fastapi_server():
    """FastAPI 서버 실행"""
    uvicorn.run(
        app,
        host=config_manager.config['server']['host'],
        port=config_manager.config['server']['port'],
        log_level="info"
    )

def signal_handler(signum, frame):
    """종료 시그널 처리"""
    logger.info("\n프로그램을 종료합니다...")
    if osrm_server:
        osrm_server.stop()
    if navigation_system:
        navigation_system.nav_state.clear()
    if navigation_gui:
        navigation_gui.master.destroy()
    sys.exit(0)

def start_fastapi_server():
    """FastAPI 서버를 별도의 스레드에서 실행"""
    server_thread = threading.Thread(target=run_fastapi_server, daemon=True)
    server_thread.start()

def initialize_gui():
    """GUI 초기화 및 실행"""
    global navigation_gui
    root = tk.Tk()
    navigation_gui = MapGUI(root)
    root.mainloop()

def main():
    global osrm_server

    try:
        # OSRM 서버 시작
        osrm_server = OSRMServer(config_manager.config)
        if not osrm_server.start():
            logger.error("OSRM 서버 시작 실패")
            return

        # NavigationSystem 초기화
        initialize_navigation_system()

        # FastAPI 서버 시작 (별도 스레드)
        start_fastapi_server()

        # GUI 초기화 (메인 스레드에서 실행)
        initialize_gui()

    except KeyboardInterrupt:
        logger.info("\n프로그램을 종료합니다...")
        if osrm_server:
            osrm_server.stop()
        if navigation_gui:
            navigation_gui.master.destroy()
        sys.exit(0)
    except Exception as e:
        logger.error(f"프로그램 실행 중 오류 발생: {str(e)}")
        if osrm_server:
            osrm_server.stop()
        if navigation_gui:
            navigation_gui.master.destroy()
        sys.exit(1)

if __name__ == "__main__":
    # 시그널 핸들러 등록
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    main()