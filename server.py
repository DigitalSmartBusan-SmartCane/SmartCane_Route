# server.py
import logging
from typing import List, Dict, Any, Optional, Tuple, Callable
from datetime import datetime
from fastapi import WebSocket

from routing import RouteManager
from geocoding import GeocodingManager

logger = logging.getLogger("RouteManager")

class ConnectionManager:
    """웹소켓 연결 관리 클래스"""
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """웹소켓 연결 수락"""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.debug(f"New client connected: {len(self.active_connections)} connections")

    def disconnect(self, websocket: WebSocket):
        """웹소켓 연결 해제"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.debug(f"Client disconnected: {len(self.active_connections)} connections")

class NavigationState:
    """현재 내비게이션 상태 관리"""
    def __init__(self):
        self.current_location: Optional[Tuple[float, float]] = None
        self.destination: Optional[Dict[str, float]] = None
        self.route: Optional[List[Tuple[float, float]]] = None

    def update_location(self, location: Dict[str, float]) -> bool:
        """현재 위치 업데이트"""
        try:
            latitude = location['latitude']
            longitude = location['longitude']
            self.current_location = (latitude, longitude)
            logger.debug(f"위치 데이터 설정: 위도={latitude}, 경도={longitude}")
            return True
        except KeyError as e:
            logger.error(f"위치 데이터 누락: {e}")
            return False

    def set_destination(self, destination: Dict[str, float]):
        """목적지 설정"""
        try:
            self.destination = destination
            logger.debug(f"목적지 설정: {destination}")
        except Exception as e:
            logger.error(f"목적지 설정 중 오류 발생: {e}")

    def clear(self):
        """내비게이션 상태 초기화"""
        self.current_location = None
        self.destination = None
        self.route = None

class NavigationSystem:
    """내비게이션 시스템 클래스"""
    def __init__(self, on_update: Callable[[Tuple[float, float], Optional[List[Tuple[float, float]]], str], None]):
        self.nav_state = NavigationState()
        self.route_manager = RouteManager()
        self.geocoding_manager = GeocodingManager()
        self.on_update = on_update  # GUI 업데이트 콜백 함수

    def handle_destination(self, destination: Any) -> bool:
        """목적지 처리"""
        try:
            # 메시지 데이터 타입에 따라 처리
            if isinstance(destination, str):
                address = destination
                logger.debug(f"문자열 주소 수신: {address}")
            elif isinstance(destination, dict):
                # 좌표가 직접 전달된 경우
                if 'latitude' in destination and 'longitude' in destination:
                    self.nav_state.set_destination(destination)
                    logger.info(f"목적지 좌표 직접 설정: {destination}")
                    if self.nav_state.current_location:
                        self.update_route()
                    return True
                # 주소가 전달된 경우
                address = destination.get('address', '')
                logger.debug(f"딕셔너리 주소 수신: {address}")
            else:
                logger.warning(f"알 수 없는 목적지 형식: {type(destination)}")
                return False

            if not address:
                logger.warning("빈 주소 수신")
                return False

            # 지오코딩으로 주소를 좌표로 변환
            coords = self.geocoding_manager.validate_address(address)
            if coords:
                destination_dict = {
                    'latitude': coords[0],
                    'longitude': coords[1]
                }
                self.nav_state.set_destination(destination_dict)
                logger.info(f"목적지 설정 완료: {coords}")
                if self.nav_state.current_location:
                    self.update_route()
                return True
            else:
                logger.warning("지오코딩 실패: 유효하지 않은 주소")
                return False
        except Exception as e:
            logger.error(f"목적지 처리 중 오류 발생: {str(e)}")
            return False

    def update_location(self, location: Dict[str, float]) -> bool:
        """현재 위치 업데이트 및 경로 재계산"""
        success = self.nav_state.update_location(location)
        if success:
            logger.info(f"현재 위치 업데이트: {self.nav_state.current_location}")
            if self.nav_state.destination:
                logger.debug("목적지가 설정되어 있어 경로를 업데이트합니다.")
                self.update_route()
            else:
                logger.debug("목적지가 설정되지 않아 경로 업데이트를 생략합니다.")
        else:
            logger.error("위치 업데이트 실패: 위치 데이터가 올바르지 않습니다.")
        return success

    def update_route(self):
        """경로 계산 및 GUI 업데이트"""
        try:
            if not self.nav_state.current_location:
                logger.warning("현재 위치가 설정되지 않았습니다.")
                return

            if not self.nav_state.destination:
                logger.warning("목적지가 설정되지 않았습니다.")
                return

            route = self.route_manager.get_directions(
                self.nav_state.current_location,
                self.nav_state.destination
            )
            
            if route:
                # 현재 위치와 목적지 사이의 거리 계산
                current_coords = self.nav_state.current_location
                dest_coords = (self.nav_state.destination['latitude'], self.nav_state.destination['longitude'])
                distance = self.route_manager.calculate_distance(current_coords, dest_coords)
                
                # 목적지 도착 여부 확인 (20미터 이내)
                if distance <= 20:
                    logger.info("🏁 목적지에 도착했습니다!")
                    print("\n🏁 목적지에 도착했습니다!")
                
                formatted_route = self.route_manager.format_route(route)
                if 'route' in formatted_route and formatted_route['route']:
                    self.nav_state.route = formatted_route['route']
                    instruction = self.route_manager.get_next_instruction(
                        self.nav_state.current_location,
                        route
                    )
                    logger.info(f"경로 안내: {instruction}")
                    self.on_update(
                        self.nav_state.current_location,
                        self.nav_state.route,
                        self.nav_state.destination
                    )
                    print(f"\n경로 안내: {instruction}")
                else:
                    logger.warning("경로 포맷 오류")
            else:
                logger.warning("경로를 찾을 수 없습니다.")
        except Exception as e:
            logger.exception("경로 계산 중 예외 발생")

    def get_current_instruction(self) -> str:
        """현재 위치에 따른 경로 안내 메시지를 반환합니다"""
        try:
            if not self.nav_state.current_location or not self.nav_state.destination:
                return "경로 안내를 시작할 수 없습니다."

            route = self.route_manager.get_directions(
                self.nav_state.current_location,
                self.nav_state.destination
            )
            
            if route:
                instruction = self.route_manager.get_next_instruction(
                    self.nav_state.current_location,
                    route
                )
                return instruction
            else:
                return "경로를 찾을 수 없습니다."
        except Exception as e:
            logger.error(f"경로 안내 메시지 생성 중 오류 발생: {str(e)}")
            return "경로 안내 중 오류가 발생했습니다."