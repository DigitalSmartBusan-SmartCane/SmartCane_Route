import pyttsx3
import logging
import queue
import threading
import time
from typing import Optional
from config import load_config

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('tts.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('TTSManager')

class TTSManager:
    def __init__(self):
        """TTS 관리자 초기화"""
        self.config = load_config()
        self.engine = None
        self.message_queue = queue.Queue()
        self.is_speaking = False
        self.should_stop = False
        self.voice_enabled = True
        self._lock = threading.Lock()
        
        # TTS 설정
        self.rate = self.config['tts'].get('rate', 150)
        self.volume = self.config['tts'].get('volume', 1.0)
        self.voice_id = self.config['tts'].get('voice_id', None)
        self.language = self.config['tts'].get('language', 'ko')
        
        # TTS 엔진 초기화
        self.initialize_engine()
        
        # 메시지 처리 스레드 시작
        self.speech_thread = threading.Thread(target=self._process_speech_queue, daemon=True)
        self.speech_thread.start()

    def initialize_engine(self) -> None:
        """TTS 엔진 초기화"""
        try:
            self.engine = pyttsx3.init()
            
            # 기본 설정
            self.engine.setProperty('rate', self.rate)
            self.engine.setProperty('volume', self.volume)
            
            # 사용 가능한 음성 확인 및 설정
            voices = self.engine.getProperty('voices')
            selected_voice = None
            
            # 한국어 음성 찾기
            for voice in voices:
                if self.language in voice.languages:
                    selected_voice = voice
                    break
            
            # 지정된 음성 ID가 있는 경우 해당 음성 사용
            if self.voice_id:
                for voice in voices:
                    if voice.id == self.voice_id:
                        selected_voice = voice
                        break
            
            if selected_voice:
                self.engine.setProperty('voice', selected_voice.id)
                logger.info(f"선택된 음성: {selected_voice.name}")
            else:
                logger.warning("한국어 음성을 찾을 수 없습니다. 기본 음성을 사용합니다.")
            
            logger.info("TTS 엔진이 초기화되었습니다.")
            
        except Exception as e:
            logger.error(f"TTS 엔진 초기화 중 오류 발생: {str(e)}")
            raise

    def text_to_speech(self, text: str, priority: bool = False) -> None:
        """텍스트를 음성으로 변환"""
        with self._lock:
            if not self.voice_enabled:
                logger.debug("음성 출력이 비활성화되어 있습니다.")
                return

            try:
                if priority:
                    # 우선순위 메시지는 큐의 앞부분에 추가
                    temp_queue = queue.Queue()
                    temp_queue.put(text)
                    while not self.message_queue.empty():
                        temp_queue.put(self.message_queue.get())
                    self.message_queue = temp_queue
                else:
                    self.message_queue.put(text)
                    
                logger.debug(f"메시지 큐에 추가됨: {text}")
                
            except Exception as e:
                logger.error(f"메시지 큐 처리 중 오류 발생: {str(e)}")
            
            pass

    def _process_speech_queue(self) -> None:
        """메시지 큐 처리"""
        while not self.should_stop:
            try:
                if not self.message_queue.empty() and not self.is_speaking:
                    text = self.message_queue.get()
                    self.is_speaking = True
                    
                    try:
                        logger.debug(f"음성 출력 시작: {text}")
                        self.engine.say(text)
                        self.engine.runAndWait()
                        logger.debug("음성 출력 완료")
                    except Exception as e:
                        logger.error(f"음성 출력 중 오류 발생: {str(e)}")
                        # 엔진 재초기화 시도
                        self.initialize_engine()
                    finally:
                        self.is_speaking = False
                        
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"메시지 큐 처리 중 오류 발생: {str(e)}")
                time.sleep(1)

    def clear_queue(self) -> None:
        """메시지 큐 초기화"""
        while not self.message_queue.empty():
            self.message_queue.get()
        logger.info("메시지 큐가 초기화되었습니다.")

    def stop_speaking(self) -> None:
        """현재 음성 출력 중지"""
        if self.is_speaking:
            self.engine.stop()
            self.is_speaking = False
            logger.info("음성 출력이 중지되었습니다.")

    def set_voice_enabled(self, enabled: bool) -> None:
        """음성 출력 활성화/비활성화"""
        self.voice_enabled = enabled
        logger.info(f"음성 출력이 {'활성화' if enabled else '비활성화'}되었습니다.")

    def change_rate(self, rate: int) -> None:
        """음성 속도 변경"""
        try:
            self.rate = rate
            self.engine.setProperty('rate', rate)
            logger.info(f"음성 속도가 변경되었습니다: {rate}")
        except Exception as e:
            logger.error(f"음성 속도 변경 중 오류 발생: {str(e)}")

    def change_volume(self, volume: float) -> None:
        """음성 볼륨 변경"""
        try:
            self.volume = max(0.0, min(1.0, volume))
            self.engine.setProperty('volume', self.volume)
            logger.info(f"음성 볼륨이 변경되었습니다: {self.volume}")
        except Exception as e:
            logger.error(f"음성 볼륨 변경 중 오류 발생: {str(e)}")

    def get_available_voices(self) -> list:
        """사용 가능한 음성 목록 반환"""
        try:
            voices = []
            for voice in self.engine.getProperty('voices'):
                voices.append({
                    'id': voice.id,
                    'name': voice.name,
                    'languages': voice.languages,
                    'gender': voice.gender,
                    'age': voice.age
                })
            return voices
        except Exception as e:
            logger.error(f"음성 목록 조회 중 오류 발생: {str(e)}")
            return []

    def __del__(self):
        """소멸자"""
        try:
            self.should_stop = True
            if self.speech_thread.is_alive():
                self.speech_thread.join(timeout=1)
            if self.engine:
                self.engine.stop()
        except Exception as e:
            logger.error(f"TTS 매니저 정리 중 오류 발생: {str(e)}")

# 테스트 코드
if __name__ == "__main__":
    try:
        tts_manager = TTSManager()
        
        # 사용 가능한 음성 출력
        print("\n사용 가능한 음성:")
        voices = tts_manager.get_available_voices()
        for voice in voices:
            print(f"- {voice['name']} ({voice['languages']})")
        
        # 테스트 메시지
        test_messages = [
            "안녕하세요, 음성 안내를 시작합니다.",
            "500미터 앞에서 우회전하세요.",
            "목적지까지 남은 거리는 1.5킬로미터입니다.",
            "경로 안내를 종료합니다."
        ]
        
        # 메시지 출력 테스트
        print("\n음성 출력 테스트를 시작합니다...")
        for message in test_messages:
            print(f"\n재생: {message}")
            tts_manager.text_to_speech(message)
            time.sleep(3)
        
        # 우선순위 메시지 테스트
        print("\n우선순위 메시지 테스트...")
        tts_manager.text_to_speech("일반 메시지입니다.")
        tts_manager.text_to_speech("긴급 메시지입니다!", priority=True)
        
        # 음성 설정 테스트
        print("\n음성 설정 테스트...")
        tts_manager.change_rate(130)
        tts_manager.text_to_speech("속도가 변경되었습니다.")
        time.sleep(2)
        
        tts_manager.change_volume(0.8)
        tts_manager.text_to_speech("볼륨이 변경되었습니다.")
        time.sleep(2)
        
        # 프로그램 종료까지 대기
        input("\n종료하려면 Enter를 누르세요...")
        
    except KeyboardInterrupt:
        print("\n프로그램을 종료합니다.")
    except Exception as e:
        print(f"오류 발생: {str(e)}")