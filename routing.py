import requests
import json
from typing import Dict, List, Optional, Tuple
import time
from config import load_config
import logging
from datetime import datetime
from collections import OrderedDict

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
    "depart": "출발",
    "arrive": "도착",
    "continue": "직진",
    "straight": "직진",
    
    # 상세 방향
    "slight right": "우측 방향",
    "slight left": "좌측 방향",
    "sharp right": "급우회전",
    "sharp left": "급좌회전",
    "uturn": "유턴",
    
    # 기타 안내
    "roundabout": "로터리",
    "merge": "차선 합류",
    "ramp": "램프",
    "exit": "출구",
    "keep right": "우측 유지",
    "keep left": "좌측 유지",
    
    # 추가 안내
    "enter roundabout": "로터리 진입",
    "exit roundabout": "로터리 퇴출",
    "finish": "목적지",
    "via": "경유",
    "head": "방향",
    "end of road": "도로 끝",
    "fork": "갈림길",
    "motorway": "고속도로",
    "motorway link": "고속도로 연결로",
    "on ramp": "진입로",
    "off ramp": "출구로"
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

class RouteManager:
    """경로 관리 클래스"""
    def __init__(self):
        """초기화"""
        self.config = load_config()
        self.osrm_url = self.config['routing']['osrm_url']
        self.cache = RouteCache(
            max_size=100,
            expiry=self.config['routing']['cache_duration']
        )
        self.last_request_time = 0
        self.request_interval = 1.0  # 초당 요청 제한

    def get_directions(self, current_location_coords: Tuple[float, float],
                      destination_coords: Tuple[float, float]) -> Optional[Dict]:
        """경로 안내 요청 및 변환"""
        try:
            # 캐시 확인
            cached_route = self.cache.get(current_location_coords, destination_coords)
            if cached_route:
                return cached_route

            # 요청 간격 제어
            current_time = time.time()
            time_since_last = current_time - self.last_request_time
            if time_since_last < self.request_interval:
                time.sleep(self.request_interval - time_since_last)

            # OSRM API 요청
            url = (
                f"{self.osrm_url}/route/v1/driving/"
                f"{current_location_coords[1]},{current_location_coords[0]};"
                f"{destination_coords[1]},{destination_coords[0]}"
            )
            
            params = {
                'steps': 'true',
                'annotations': 'true',
                'geometries': 'geojson',
                'overview': 'full',
                'alternatives': 'false'
            }

            response = requests.get(
                url,
                params=params,
                timeout=self.config['routing']['api_timeout']
            )
            
            self.last_request_time = time.time()

            if response.status_code == 200:
                route_data = response.json()
                if route_data.get('routes'):
                    formatted_route = self.format_route(route_data['routes'][0])
                    self.cache.set(current_location_coords, destination_coords, formatted_route)
                    return formatted_route
                else:
                    logger.warning("경로를 찾을 수 없습니다.")
                    return None
            else:
                logger.error(f"OSRM API 오류: {response.status_code}")
                return None

        except requests.Timeout:
            logger.error("OSRM 서버 요청 시간 초과")
            return None
        except requests.RequestException as e:
            logger.error(f"OSRM API 요청 중 오류 발생: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"경로 검색 중 오류 발생: {str(e)}")
            return None

    def format_route(self, route: Dict) -> Dict:
        """경로 정보 포맷팅"""
        try:
            formatted_route = {
                'distance': route.get('distance', 0),  # 총 거리 (미터)
                'duration': route.get('duration', 0),  # 예상 소요 시간 (초)
                'geometry': route.get('geometry', {}),  # 경로 좌표
                'steps': []
            }

            for leg in route.get('legs', []):
                for step in leg.get('steps', []):
                    formatted_step = self.format_instruction(step)
                    if formatted_step:
                        formatted_route['steps'].append(formatted_step)

            return formatted_route

        except Exception as e:
            logger.error(f"경로 포맷팅 중 오류 발생: {str(e)}")
            return None

    def format_instruction(self, step: Dict) -> Optional[str]:
        """경로 안내 단계를 한국어로 포맷팅"""
        try:
            # 거리 포맷팅
            distance_m = int(step.get('distance', 0))
            if distance_m >= 1000:
                distance_text = f"{distance_m/1000:.1f}km"
            else:
                distance_text = f"{distance_m}m"

            # 안내문 생성
            maneuver = step.get('maneuver', {})
            instruction = self.get_korean_instruction(maneuver)

            # 도로명 추가
            road_name = step.get('name', '')
            if road_name:
                road_info = f" ({road_name})"
            else:
                road_info = ""

            # 최종 안내문 조합
            if maneuver.get('type') == 'arrive':
                return f"{distance_text} 앞에서 {instruction}입니다{road_info}"
            else:
                return f"{distance_text} 앞에서 {instruction}하세요{road_info}"

        except Exception as e:
            logger.error(f"안내문 생성 중 오류 발생: {str(e)}")
            return "안내문을 생성할 수 없습니다"

    def get_korean_instruction(self, maneuver: Dict) -> str:
        """maneuver 정보를 바탕으로 한국어 안내문을 생성"""
        try:
            maneuver_type = maneuver.get('type', '')
            modifier = maneuver.get('modifier', '')
            
            # type과 modifier를 조합한 키 생성
            instruction_key = f"{maneuver_type} {modifier}".strip()
            
            # 번역 시도 순서:
            # 1. 전체 문구 번역 시도
            # 2. type만 번역 시도
            # 3. 기본값 사용
            if instruction_key in instruction_translation:
                return instruction_translation[instruction_key]
            elif maneuver_type in instruction_translation:
                return instruction_translation[maneuver_type]
            else:
                return "직진"

        except Exception as e:
            logger.error(f"안내문 변환 중 오류 발생: {str(e)}")
            return "직진"

# 테스트 코드
if __name__ == "__main__":
    route_manager = RouteManager()
    
    # 테스트 좌표 (부산대학교 - 해운대해수욕장)
    start = (35.2333, 129.0833)  # 부산대학교 좌표
    end = (35.1589, 129.1600)    # 해운대해수욕장 좌표
    
    route = route_manager.get_directions(start, end)
    if route:
        print(f"총 거리: {route['distance']/1000:.1f}km")
        print(f"예상 소요 시간: {route['duration']/60:.0f}분")
        print("\n경로 안내:")
        for step in route['steps']:
            print(f"- {step}")