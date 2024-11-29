import requests
from typing import Dict, Optional, Tuple
from urllib.parse import quote
import time
from collections import OrderedDict
from config import load_config
import logging

logger = logging.getLogger('GeocodingManager')

class GeoCache:
    """주소-좌표 캐시 관리 클래스"""
    def __init__(self, max_size: int = 100):
        self.cache: OrderedDict = OrderedDict()
        self.max_size = max_size
        self.expiry_time = 300  # 5분

    def get(self, address: str) -> Optional[Dict]:
        """캐시된 좌표 정보 가져오기"""
        if address in self.cache:
            data, timestamp = self.cache[address]
            if time.time() - timestamp < self.expiry_time:
                self.cache.move_to_end(address)
                return data
            else:
                del self.cache[address]
        return None

    def set(self, address: str, data: Dict):
        """좌표 정보 캐시에 저장"""
        if len(self.cache) >= self.max_size:
            self.cache.popitem(last=False)
        self.cache[address] = (data, time.time())

class GeocodingManager:
    """지오코딩 관리 클래스"""
    def __init__(self):
        self.config = load_config()
        self.cache = GeoCache(self.config['geocoding']['cache_size'])
        self.headers = {
            'User-Agent': self.config['geocoding']['user_agent']
        }
        self.base_url = self.config['geocoding']['nominatim_url']
        self.timeout = self.config['geocoding']['timeout']
        self.max_retries = self.config['geocoding']['max_retries']

    def validate_address(self, address):
        """주소를 좌표로 변환"""
        try:
            encoded_address = quote(address + " 부산")  # 지역명 추가
            url = f"https://nominatim.openstreetmap.org/search?q={encoded_address}&format=json&limit=1"
            
            response = requests.get(
                url, 
                headers=self.headers,
                timeout=self.config['geocoding']['timeout']
            )
            
            if response.status_code == 200:
                geocode_result = response.json()
                if geocode_result:
                    location = geocode_result[0]
                    return {
                        "latitude": float(location['lat']),
                        "longitude": float(location['lon']),
                        "address": location['display_name']
                    }
                else:
                    logger.warning(f"주소를 찾을 수 없습니다: {address}")
                    return None
                    
            else:
                logger.error(f"API 응답 오류: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"주소 변환 중 오류 발생: {str(e)}")
            return None

    def get_address_details(self, lat: float, lon: float) -> Optional[Dict]:
        """좌표를 주소로 변환 (역지오코딩)"""
        try:
            url = f"{self.base_url}/reverse"
            params = {
                'lat': lat,
                'lon': lon,
                'format': 'json',
                'addressdetails': 1,
                'accept-language': 'ko'
            }
            
            response = requests.get(
                url,
                params=params,
                headers=self.headers,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                if result:
                    return {
                        "address": result['display_name'],
                        "details": result.get('address', {}),
                        "type": result.get('type'),
                        "importance": result.get('importance', 0)
                    }
            return None
            
        except Exception as e:
            print(f"역지오코딩 중 오류 발생: {str(e)}")
            return None

    def calculate_distance(self, coord1: Tuple[float, float], 
                         coord2: Tuple[float, float]) -> float:
        """두 좌표 간의 거리 계산 (미터 단위)"""
        from math import sin, cos, sqrt, atan2, radians
        
        R = 6371000  # 지구 반경 (미터)
        
        lat1, lon1 = radians(coord1[0]), radians(coord1[1])
        lat2, lon2 = radians(coord2[0]), radians(coord2[1])
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        
        return R * c
