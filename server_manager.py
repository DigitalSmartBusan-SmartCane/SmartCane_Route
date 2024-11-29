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

        # Ubuntu 환경에서 경로 설정
        self.osrm_path = "/mnt/c/Users/user/Desktop/OSRM/osrm-backend/build/osrm-routed"
        self.map_path = "/mnt/c/Users/user/Desktop/OSRM/maps/south-korea-latest.osrm"

    def is_server_running(self) -> bool:
        """OSRM 서버가 실행 중인지 확인"""
        try:
            response = requests.get(
                f"http://localhost:{self.port}/status",
                timeout=5,
                headers={'User-Agent': 'osrm-server-manager'}
            )
            # 200 또는 400 응답 모두 서버가 실행 중임을 의미
            return response.status_code in [200, 400]
        except requests.RequestException:
            return False

    def start(self) -> bool:
        """OSRM 서버 시작"""
        try:
            logger.info("서버 시작 프로세스 시작...")
            
            if self.is_server_running():
                logger.info("OSRM 서버가 이미 실행 중입니다.")
                return True

            cmd = [
                'wsl',
                '-d',
                'Ubuntu',
                'bash',
                '-c',
                'cd /mnt/c/Users/user/Desktop/OSRM/osrm-backend/build && '
                './osrm-routed --algorithm mld --port 5000 '
                '/mnt/c/Users/user/Desktop/OSRM/maps/south-korea-latest.osrm'
            ]

            logger.info(f"실행할 명령어: {' '.join(cmd)}")
            logger.info("프로세스 시작 중...")
            
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=1,
                universal_newlines=True
            )
            self.start_time = time.time()
            logger.info("프로세스가 시작되었습니다.")

            # 초기 서버 시작 로그만 표시
            def read_initial_output(pipe, log_func):
                for line in iter(pipe.readline, ''):
                    if "running and waiting for requests" in line:
                        log_func(f"서버 출력: {line.strip()}")
                        break

            # 출력 읽기 스레드 시작
            stdout_thread = threading.Thread(
                target=read_initial_output, 
                args=(self.process.stdout, logger.info),
                daemon=False
            )
            stderr_thread = threading.Thread(
                target=read_initial_output, 
                args=(self.process.stderr, logger.error),
                daemon=False
            )
            stdout_thread.start()
            stderr_thread.start()

            # 서버 시작 대기
            for i in range(10):
                if self.process.poll() is not None:
                    error_output = self.process.stderr.read()
                    logger.error(f"프로세스가 예기치 않게 종료됨. 에러 메시지:\n{error_output}")
                    return False

                if self.is_server_running():
                    logger.info("OSRM 서버가 성공적으로 시작되었습니다.")
                    return True
                
                time.sleep(1)
                logger.info(f"서버 시작 대기 중... ({i+1}/10)")

            logger.error("서버 시작 시간 초과")
            return False

        except Exception as e:
            logger.error(f"OSRM 서버 시작 중 오류 발생: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return False

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

# 테스트 코드
if __name__ == "__main__":
    try:
        logger.info("=== OSRM 서버 관리자 시작 ===")
        server = OSRMServer()
        logger.info("OSRM 서버를 시작합니다...")
        
        if server.start():
            logger.info("=== 서버가 성공적으로 시작되었습니다 ===")
            logger.info("서버를 종료하려면 Ctrl+C를 누르세요...")
            try:
                while True:
                    if not server.is_server_running():
                        logger.error("서버가 예기치 않게 종료되었습니다.")
                        break
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("\n서버 종료 요청을 받았습니다.")
        else:
            logger.error("=== 서버 시작 실패 ===")
    except Exception as e:
        logger.error(f"예기치 않은 오류 발생: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        if 'server' in locals():
            logger.info("서버 종료 시도 중...")
            server.stop()
            logger.info("=== 서버가 종료되었습니다 ===")