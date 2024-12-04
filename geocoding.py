import requests
from typing import Dict, Optional, Tuple
from urllib.parse import quote
import time
from collections import OrderedDict
from config import load_config
import logging
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderServiceError

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

    def cleanup_expired(self):
        """만료된 캐시 항목 정리"""
        current_time = time.time()
        expired_keys = [k for k, (_, t) in self.cache.items() 
                    if current_time - t > self.expiry_time]
        for k in expired_keys:
            del self.cache[k]

    def set(self, address: str, data: Dict):
        """좌표 정보 캐시에 저장"""
        if len(self.cache) >= self.max_size:
            self.cache.popitem(last=False)
        self.cache[address] = (data, time.time())

class GeocodingManager:
    """지오코딩 관리 클래스"""
    def __init__(self, user_agent: str = "MyApp/1.0"):
        self.config = load_config()
        self.cache = GeoCache(self.config['geocoding']['cache_size'])
        self.headers = {
            'User-Agent': 'YourAppName/1.0 (your.email@example.com)'
        }
        self.base_url = self.config['geocoding']['nominatim_url']
        self.timeout = self.config['geocoding']['timeout']
        self.max_retries = self.config['geocoding']['max_retries']
        self.geocoding_api_url = "https://nominatim.openstreetmap.org/search"
        self.headers = {
            'User-Agent': 'MyNavigationApp/1.0 (contact@myapp.com)'
        }
        self.geolocator = Nominatim(user_agent=user_agent)

    def validate_address(self, address: str) -> Optional[Dict[str, float]]:
        """주소를 좌표로 변환"""
        try:
            location = self.geolocator.geocode(address)
            if location:
                logger.debug(f"지오코딩 성공: {address} -> ({location.latitude}, {location.longitude})")
                return {'latitude': location.latitude, 'longitude': location.longitude}
            else:
                logger.warning(f"지오코딩 실패: {address}을 찾을 수 없습니다.")
                return None
        except GeocoderServiceError as e:
            logger.error(f"지오코딩 서비스 오류: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"지오코딩 중 예외 발생: {str(e)}")
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
