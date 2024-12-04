from typing import Tuple, List, Optional, Dict
import subprocess
import os
import time
import sys
import signal
import psutil
import requests
import logging
from typing import Optional
from config import load_config
import threading

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('OSRMServer')

class OSRMServer:
    def __init__(self, config: dict = None):
        self.config = config or load_config()
        self.process = None
        self.start_time = None
        self.port = self.config['osrm']['port']
        
        # config.yaml에서 경로 읽어오기
        self.osrm_path = self.config['osrm']['path']
        self.map_path = self.config['osrm']['map_path']

        logger.debug(f"OSRM 경로: {self.osrm_path}")
        logger.debug(f"지도 파일 경로: {self.map_path}")

    def is_server_running(self) -> bool:
        """OSRM 서버가 실행 중인지 확인"""
        try:
            # 단순한 상태 체크 URL로 변경
            response = requests.get(
                f"http://localhost:{self.port}/nearest/v1/driving/0,0",
                timeout=2
            )
            return True
        except requests.exceptions.RequestException as e:
            logger.debug(f"서버 상태 확인 중 오류: {e}")
            return False

    def start(self) -> bool:
        """OSRM 서버 시작"""
        try:
            logger.info("OSRM 서버 시작 프로세스 시작...")
            
            if self.is_server_running():
                logger.info("OSRM 서버가 이미 실행 중입니다.")
                return True

            # 명령어를 분리하여 실행
            cmd = [
                'wsl',
                '-d', 'Ubuntu',  # Ubuntu 배포판 명시
                '/mnt/c/Users/user/Desktop/OSRM/osrm-backend/build/osrm-routed',
                '--algorithm', 'mld',
                '--port', str(self.port),
                '/mnt/c/Users/user/Desktop/OSRM/maps/south-korea-latest.osrm'
            ]

            logger.info(f"실행할 명령어: {' '.join(cmd)}")
            
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=1,
                universal_newlines=True
            )

            # 프로세스 출력 읽기 위한 스레드 시작
            def log_output(pipe, prefix):
                for line in pipe:
                    logger.info(f"{prefix}: {line.strip()}")

            threading.Thread(target=log_output, args=(self.process.stdout, "OSRM stdout"), daemon=True).start()
            threading.Thread(target=log_output, args=(self.process.stderr, "OSRM stderr"), daemon=True).start()

            # 서버 시작 대기
            start_time = time.time()
            while time.time() - start_time < 30:  # 30초 타임아웃
                if self.process.poll() is not None:
                    # 프로세스가 종료된 경우
                    error_output = self.process.stderr.read()
                    logger.error(f"OSRM 서버 프로세스가 종료됨. 종료 코드: {self.process.returncode}")
                    logger.error(f"오류 출력: {error_output}")
                    return False
                
                if self.is_server_running():
                    logger.info("OSRM 서버가 성공적으로 시작되었습니다.")
                    return True
                
                time.sleep(1)
                logger.info(f"서버 시작 대기 중... ({int(time.time() - start_time)}초)")

            logger.error("서버 시작 시간 초과")
            return False

        except Exception as e:
            logger.error(f"OSRM 서버 시작 중 오류 발생: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return False
        
    def calculate_distance_from_route(self, current_location: Tuple[float, float], 
                                route_coordinates: List[List[float]]) -> float:
        """현재 위치와 경로 간의 최단 거리를 계산"""
        min_distance = float('inf')
        
        for i in range(len(route_coordinates) - 1):
            point1 = route_coordinates[i]
            point2 = route_coordinates[i + 1]
            
            # 선분과 현재 위치 사이의 거리 계산
            distance = self.point_to_line_distance(
                current_location,
                (point1[1], point1[0]),  # OSRM은 [경도, 위도] 순서로 반환
                (point2[1], point2[0])
            )
            min_distance = min(min_distance, distance)
        
        return min_distance

    def point_to_line_distance(self, point: Tuple[float, float],
                            line_start: Tuple[float, float],
                            line_end: Tuple[float, float]) -> float:
        """점과 선분 사이의 최단 거리 계산"""
        # 선분의 길이가 0인 경우
        if line_start == line_end:
            return self.calculate_distance(point, line_start)
        
        # 선분의 방향 벡터
        line_vec = (
            line_end[0] - line_start[0],
            line_end[1] - line_start[1]
        )
        
        # 시작점에서 현재 위치까지의 벡터
        point_vec = (
            point[0] - line_start[0],
            point[1] - line_start[1]
        )
        
        # 내적 계산
        dot_product = (line_vec[0] * point_vec[0] + 
                    line_vec[1] * point_vec[1])
        
        # 선분의 길이의 제곱
        line_length_sq = (line_vec[0] * line_vec[0] + 
                        line_vec[1] * line_vec[1])
        
        # 사영 비율
        t = max(0, min(1, dot_product / line_length_sq))
        
        # 최단 거리 지점
        closest_point = (
            line_start[0] + t * line_vec[0],
            line_start[1] + t * line_vec[1]
        )
        
        # 최단 거리 계산
        return self.calculate_distance(point, closest_point)

    def should_update_route(self, current_location: Tuple[float, float], 
                        current_route: Dict) -> bool:
        """경로 업데이트가 필요한지 판단"""
        if not current_route or 'geometry' not in current_route:
            return True
            
        try:
            coordinates = current_route['geometry']['coordinates']
            distance = self.calculate_distance_from_route(
                current_location, 
                coordinates
            )
            
            # 설정된 임계값보다 멀어진 경우 재탐색
            threshold = self.config['routing']['reroute_threshold']
            return distance > threshold
            
        except Exception as e:
            logger.error(f"경로 이탈 확인 중 오류 발생: {str(e)}")
            return True

    def stop(self) -> bool:
        """OSRM 서버 중지"""
        try:
            if self.process:
                # 먼저 정상 종료 시도
                subprocess.run(['wsl', '-d', 'Ubuntu', 'pkill', 'osrm-routed'], 
                            capture_output=True,
                            text=True)
                
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                
                logger.info("OSRM 서버가 종료되었습니다.")
                self.process = None
                self.start_time = None
                return True
            return True

        except Exception as e:
            logger.error(f"OSRM 서버 종료 중 오류 발생: {str(e)}")
            return False

    def restart(self) -> bool:
        """OSRM 서버 재시작"""
        logger.info("OSRM 서버 재시작 중...")
        self.stop()
        time.sleep(2)
        return self.start()

    def __del__(self):
        """소멸자"""
        self.stop()