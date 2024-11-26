import serial
import time
import pynmea2

class GPSManager:
    def __init__(self, port='/dev/ttyAMA0', baudrate=9600):
        """GPS 관리자 초기화"""
        self.port = port  # 시리얼 포트 (라즈베리파이의 경우 보통 /dev/ttyAMA0 또는 /dev/ttyUSB0)
        self.baudrate = baudrate  # GPS 모듈의 보드레이트
        self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
        self.last_coords = None
        self.last_update_time = 0
        self.update_interval = 5  # 5초마다 위치 체크
    
    def read_gps_data(self):
        """GPS 모듈로부터 데이터를 읽어들입니다."""
        while True:
            try:
                line = self.ser.readline().decode('ascii', errors='ignore')  # 시리얼 포트에서 데이터 읽기
                if line.startswith('$GPGGA'):  # GPGGA NMEA sentence (위도, 경도 정보)
                    return self.parse_gga(line)
            except Exception as e:
                print(f"GPS 데이터 읽기 오류: {e}")
                return None

    def parse_gga(self, nmea_sentence):
        """NMEA GPGGA 문장을 파싱하여 위도, 경도 정보를 반환합니다."""
        try:
            msg = pynmea2.parse(nmea_sentence)
            latitude = msg.latitude
            longitude = msg.longitude
            if latitude and longitude:
                return [latitude, longitude]
            else:
                print("위도와 경도를 받을 수 없습니다.")
                return None
        except pynmea2.nmea.ChecksumError as e:
            print(f"체크섬 오류: {e}")
            return None
        except Exception as e:
            print(f"파싱 오류: {e}")
            return None

    def get_current_location(self):
        """현재 위치를 가져오는 함수"""
        coords = self.read_gps_data()
        if coords:
            print(f"현재 위치: 위도 {coords[0]}, 경도 {coords[1]}")
            return coords
        return None

    @staticmethod
    def calculate_distance(coord1, coord2):
        """두 좌표 간의 거리를 미터 단위로 계산"""
        from geopy import distance
        return distance.distance(
            (coord1[0], coord1[1]),
            (coord2[0], coord2[1])
        ).meters

    def should_update_route(self, current_coords, threshold=10):
        """경로 업데이트가 필요한지 확인"""
        if not self.last_coords:
            return True
        
        # 마지막 위치에서 10미터 이상 이동했으면 업데이트 필요
        return self.calculate_distance(current_coords, self.last_coords) > threshold

    def is_near_destination(self, current_coords, destination_coords, threshold=20):
        """목적지 근처(기본값 20m)에 도달했는지 확인"""
        return self.calculate_distance(current_coords, destination_coords) < threshold

    def can_update(self):
        """위치 업데이트가 필요한 시간인지 확인"""
        current_time = time.time()
        if current_time - self.last_update_time >= self.update_interval:
            self.last_update_time = current_time
            return True
        return False

    def update_last_coords(self, coords):
        """마지막 좌표 업데이트"""
        self.last_coords = coords
