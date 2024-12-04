import requests
import json
from typing import Dict, List, Optional, Tuple, Any
import time
from config import load_config
import logging
from datetime import datetime
from collections import OrderedDict
from math import sin, cos, sqrt, atan2, radians

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('RouteManager')

# 한국어 안내문 사전
instruction_translation = {
    # 기본 방향
    "turn": "회전",
    "turn right": "우회전",
    "turn left": "좌회전",
    "continue": "직진",
    "straight": "직진",
    
    # 상세 방향
    "slight right": "우측",
    "slight left": "좌측",
    "sharp right": "급우회전",
    "sharp left": "급좌회전",
    "uturn": "유턴",
    
    # 기타 안내
    "roundabout": "로터리",
    "merge": "합류",
    "ramp": "램프",
    "exit": "출구",
    "keep right": "우측 유지",
    "keep left": "좌측 유지",
    "fork": "우측",
    "fork right": "우측",
    "fork left": "좌측",
    "fork straight": "직진",
    
    # 추가 안내
    "enter roundabout": "로터리 진입",
    "exit roundabout": "로터리 출구",
    "finish": "도착",
    "via": "경유",
    "head": "진행",
    "end of road": "도로 끝",
    "motorway": "고속도로",
    "motorway link": "고속도로 진입",
    "on ramp": "진입",
    "off ramp": "출구"
}

class RouteCache:
    """경로 캐시 관리 클래스"""
    def __init__(self, max_size: int = 100, expiry: int = 300):
        self.cache = OrderedDict()
        self.max_size = max_size
        self.expiry = expiry  # 캐시 유효 시간 (초)

    def get_key(self, start: Tuple[float, float], end: Tuple[float, float]) -> str:
        """캐시 키 생성"""
        return f"{start[0]},{start[1]}-{end[0]},{end[1]}"

    def get(self, start: Tuple[float, float], end: Tuple[float, float]) -> Optional[Dict]:
        """캐시된 경로 조회"""
        key = self.get_key(start, end)
        if key in self.cache:
            route_data, timestamp = self.cache[key]
            if time.time() - timestamp < self.expiry:
                logger.debug(f"캐시 히트: {key}")
                return route_data
            else:
                del self.cache[key]
        return None

    def set(self, start: Tuple[float, float], end: Tuple[float, float], route_data: Dict):
        """경로 캐시에 저장"""
        key = self.get_key(start, end)
        if len(self.cache) >= self.max_size:
            self.cache.popitem(last=False)
        self.cache[key] = (route_data, time.time())

class RouteNotFoundError(Exception):
    pass

class RouteManager:
    def __init__(self, osrm_url: str = "http://localhost:5000"):
        self.osrm_url = osrm_url
        self.last_instruction = None
        self.current_segment_index = 0

    def get_directions(self, start: Tuple[float, float], end: Dict[str, float]) -> Optional[Dict]:
        """OSRM API를 사용하여 도보 경로를 가져옵니다"""
        try:
            url = f"{self.osrm_url}/route/v1/foot/{start[1]},{start[0]};{end['longitude']},{end['latitude']}"
            params = {
                "overview": "full",
                "geometries": "geojson",
                "steps": "true"
            }
            logger.debug(f"OSRM 요청 URL: {url}")
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if 'routes' in data and len(data['routes']) > 0:
                logger.info("경로 데이터 수신 성공")
                return data['routes'][0]
            else:
                logger.warning(f"유효한 경로를 찾을 수 없습니다.")
                return None
                
        except Exception as e:
            logger.error(f"경로 가져오기 중 예외 발생: {str(e)}")
            return None

    def get_next_instruction(self, current_location: Tuple[float, float], route: Dict) -> str:
        """현재 위치에 따른 다음 안내 메시지를 생성합니다"""
        try:
            if 'legs' not in route or not route['legs']:
                return "경로 안내를 시작할 수 없습니다."

            steps = route['legs'][0]['steps']
            if not steps:
                return "안내할 경로가 없습니다."

            # 현재 위치에서 가장 가까운 경로 세그먼트 찾기
            min_distance = float('inf')
            closest_step_index = 0

            for i, step in enumerate(steps):
                step_coords = step['geometry']['coordinates'][0]
                distance = self.calculate_distance(
                    current_location,
                    (step_coords[1], step_coords[0])
                )
                if distance < min_distance:
                    min_distance = distance
                    closest_step_index = i

            # 현재 세그먼트의 안내 메시지 생성
            current_step = steps[closest_step_index]
            
            # 현재 단계의 거리
            distance = int(current_step['distance'])
            
            # 현재 단계의 조작 타입 가져오기
            maneuver = current_step.get('maneuver', {})
            maneuver_type = maneuver.get('type', 'continue')
            maneuver_modifier = maneuver.get('modifier', '')
            
            # 조작 타입과 수정자를 결합
            instruction_key = f"{maneuver_type} {maneuver_modifier}".strip()
            if instruction_key in instruction_translation:
                base_instruction = instruction_translation[instruction_key]
            else:
                base_instruction = instruction_translation.get(maneuver_type, "직진")

            # 목적지까지 남은 거리 계산
            remaining_distance = sum(step['distance'] for step in steps[closest_step_index:])
            
            # 마지막 단계인 경우
            if closest_step_index == len(steps) - 1:
                return "목적지에 도착했습니다."
            
            # 다음 단계의 안내 준비
            next_step = steps[closest_step_index + 1]
            next_maneuver = next_step.get('maneuver', {})
            next_type = next_maneuver.get('type', 'continue')
            next_modifier = next_maneuver.get('modifier', '')
            next_instruction_key = f"{next_type} {next_modifier}".strip()
            
            next_instruction = instruction_translation.get(
                next_instruction_key,
                instruction_translation.get(next_type, "직진")
            )

            # 현재 위치에서 다음 조작까지의 거리
            distance_to_next = int(current_step['distance'])

            # 안내 메시지 생성
            if distance_to_next < 20:
                instruction = f"잠시 후 {next_instruction}하세요."
            else:
                instruction = f"{distance_to_next}m 앞에서 {next_instruction}하세요."

            # 전체 남은 거리 추가
            if remaining_distance > 1000:
                instruction += f" 목적지까지 {remaining_distance/1000:.1f}km 남았습니다."
            else:
                instruction += f" 목적지까지 {int(remaining_distance)}m 남았습니다."

            self.last_instruction = instruction
            return instruction

        except Exception as e:
            logger.error(f"안내 메시지 생성 중 오류 발생: {str(e)}")
            return "경로 안내 중 오류가 발생했습니다."

    def translate_instruction(self, maneuver: str, distance: int) -> str:
        """안내 메시지를 한글로 변환합니다"""
        base_instruction = instruction_translation.get(maneuver, "직진")
        
        if distance < 1000:
            return f"{distance}m 앞까지 {base_instruction}입니다."
        else:
            return f"{distance/1000:.1f}km 앞까지 {base_instruction}입니다."

    def calculate_distance(self, point1: Tuple[float, float], point2: Tuple[float, float]) -> float:
        """두 지점 간의 거리를 계산합니다 (미터 단위)"""
        R = 6371000  # 지구의 반경 (미터)
        lat1, lon1 = radians(point1[0]), radians(point1[1])
        lat2, lon2 = radians(point2[0]), radians(point2[1])
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        
        return R * c

    def format_route(self, route: Dict) -> Dict:
        """경로 데이터를 GUI에 맞게 포맷합니다"""
        try:
            coordinates = route['geometry']['coordinates']
            formatted_route = {
                'route': [ (coord[1], coord[0]) for coord in coordinates ]  # [위도, 경도] 형식으로 변환
            }
            logger.debug(f"경로 포맷 완료: {formatted_route}")
            return formatted_route
        except KeyError as e:
            logger.error(f"경로 포맷 중 키 오류 발생: {e}")
            return {}
        except Exception as e:
            logger.error(f"경로 포맷 중 예외 발생: {str(e)}")
            return {}
            
class GeocodingManager:
    def validate_address(self, address: str) -> Optional[Tuple[float, float]]:
        """주소를 좌표로 변환"""
        # 예시: 주소를 좌표로 변환하는 로직
        if address == "대연역":
            return (35.1349964, 129.091565)  # 대연역 좌표
        else:
            logger.warning(f"유효하지 않은 주소: {address}")
            return None
            