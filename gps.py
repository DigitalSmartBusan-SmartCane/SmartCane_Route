import serial
import time
import pynmea2
from typing import Optional, Dict, List, Tuple
from datetime import datetime, timedelta
from math import sin, cos, sqrt, atan2, radians
from config import load_config
import json
import logging

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('GPSManager')

class GPSManager:
    def __init__(self, port: str = None, baudrate: int = None):
        """GPS 관리자 초기화"""
        self.config = load_config()
        self.port = port or self.config['client']['gps']['port']
        self.baudrate = baudrate or self.config['client']['gps']['baudrate']
        self.ser = None
        
        # 위치 관련 변수
        self.last_coords: Optional[Tuple[float, float]] = None
        self.last_positions: List[Dict] = []  # 최근 위치 기록
        self.max_positions = 5  # 저장할 최대 위치 수
        
        # 시간 관련 변수
        self.last_update_time = 0
        self.update_interval = self.config['client']['gps']['update_interval']
        self.stationary_update_interval = 10  # 정지 시 업데이트 간격
        
        # 설정값
        self.retry_count = self.config['client']['gps']['retry_count']
        self.timeout = self.config['client']['gps']['timeout']
        
        # 초기 연결
        self.connect()

    def connect(self) -> bool:
        """GPS 장치 연결"""
        retry = 0
        while retry < self.retry_count:
            try:
                if self.ser and self.ser.is_open:
                    self.ser.close()
                
                self.ser = serial.Serial(
                    port=self.port,
                    baudrate=self.baudrate,
                    timeout=1
                )
                logger.info("GPS 장치에 연결되었습니다.")
                return True
                
            except serial.SerialException as e:
                retry += 1
                logger.error(f"GPS 연결 실패 ({retry}/{self.retry_count}): {e}")
                time.sleep(2)
                
        raise ConnectionError("GPS 장치 연결에 실패했습니다.")

    def read_gps_data(self) -> Optional[Tuple[float, float]]:
        """GPS 모듈로부터 데이터 읽기"""
        start_time = time.time()
        
        while time.time() - start_time < self.timeout:
            try:
                if not self.ser or not self.ser.is_open:
                    self.connect()
                    
                line = self.ser.readline().decode('ascii', errors='ignore')
                if line.startswith('$GPGGA'):
                    return self.parse_gga(line)
                    
            except serial.SerialException as e:
                logger.error(f"시리얼 포트 읽기 오류: {e}")
                self.connect()
                
            except Exception as e:
                logger.error(f"GPS 데이터 읽기 오류: {e}")
                
        return None

    def parse_gga(self, nmea_sentence: str) -> Optional[Tuple[float, float]]:
        """NMEA GGA 문장 파싱"""
        try:
            msg = pynmea2.parse(nmea_sentence)
            if msg.latitude and msg.longitude:
                return (msg.latitude, msg.longitude)
            else:
                logger.warning("위도와 경도를 받을 수 없습니다.")
                return None
                
        except pynmea2.nmea.ChecksumError as e:
            logger.error(f"체크섬 오류: {e}")
            return None
        except Exception as e:
            logger.error(f"NMEA 파싱 오류: {e}")
            return None

    def get_current_location(self) -> Optional[Tuple[float, float]]:
        """현재 위치 가져오기"""
        coords = self.read_gps_data()
        if coords:
            self.last_coords = coords
            self.update_position_history(coords)
            logger.info(f"현재 위치: 위도 {coords[0]}, 경도 {coords[1]}")
            return coords
        return None

    def update_position_history(self, coords: Tuple[float, float]):
        """위치 기록 업데이트"""
        self.last_positions.append({
            'coords': coords,
            'timestamp': time.time()
        })
        if len(self.last_positions) > self.max_positions:
            self.last_positions.pop(0)

    def calculate_speed(self) -> float:
        """현재 이동 속도 계산 (km/h)"""
        if len(self.last_positions) < 2:
            return 0.0
            
        first = self.last_positions[0]
        last = self.last_positions[-1]
        
        time_diff = last['timestamp'] - first['timestamp']
        if time_diff == 0:
            return 0.0
            
        distance = self.calculate_distance(first['coords'], last['coords'])
        speed = (distance / time_diff) * 3.6  # m/s를 km/h로 변환
        
        return speed

    def is_moving(self, threshold: float = 1.0) -> bool:
        """이동 중인지 확인"""
        if len(self.last_positions) < 2:
            return True
            
        recent_speed = self.calculate_speed()
        return recent_speed > threshold

    def calculate_distance(self, coord1: Tuple[float, float], 
                         coord2: Tuple[float, float]) -> float:
        """두 좌표 간 거리 계산 (미터)"""
        R = 6371000  # 지구 반경 (미터)
        
        lat1, lon1 = radians(coord1[0]), radians(coord1[1])
        lat2, lon2 = radians(coord2[0]), radians(coord2[1])
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        
        return R * c

    def calculate_eta(self, current_coords: Tuple[float, float],
                     destination_coords: Tuple[float, float],
                     avg_speed: float) -> Optional[datetime]:
        """예상 도착 시간 계산"""
        if avg_speed <= 0:
            return None
            
        distance = self.calculate_distance(current_coords, destination_coords)
        time_seconds = distance / (avg_speed / 3.6)  # km/h를 m/s로 변환
        
        return datetime.now() + timedelta(seconds=time_seconds)

    def should_update_route(self, current_coords: Tuple[float, float],
                          threshold: float = None) -> bool:
        """경로 업데이트가 필요한지 확인"""
        if not self.last_coords:
            return True
            
        if threshold is None:
            threshold = self.config['routing']['reroute_threshold']
            
        return self.calculate_distance(current_coords, self.last_coords) > threshold

    def is_near_destination(self, current_coords: Tuple[float, float],
                          destination_coords: Tuple[float, float],
                          threshold: float = None) -> bool:
        """목적지 근처인지 확인"""
        if threshold is None:
            threshold = self.config['routing']['arrival_threshold']
            
        return self.calculate_distance(current_coords, destination_coords) < threshold

    def can_update(self) -> bool:
        """위치 업데이트가 필요한 시간인지 확인"""
        current_time = time.time()
        interval = self.stationary_update_interval if not self.is_moving() else self.update_interval
        
        if current_time - self.last_update_time >= interval:
            self.last_update_time = current_time
            return True
        return False

    def to_json(self) -> Optional[Dict]:
        """GPS 데이터를 JSON 형식으로 변환"""
        if self.last_coords:
            return {
                "latitude": self.last_coords[0],
                "longitude": self.last_coords[1],
                "timestamp": self.last_update_time,
                "speed": self.calculate_speed(),
                "moving": self.is_moving()
            }
        return None

    def __del__(self):
        """소멸자: 시리얼 포트 정리"""
        if self.ser and self.ser.is_open:
            self.ser.close()