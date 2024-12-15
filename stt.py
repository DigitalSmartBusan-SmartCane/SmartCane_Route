import speech_recognition as sr
import time
import logging
from typing import Optional, Dict
from config import load_config

# 로깅 설정 수정 - 파일 핸들러 제거
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('STTManager')

class STTManager:
    def __init__(self):
        """음성 인식 관리자 초기화"""
        self.config = load_config()
        self.recognizer = sr.Recognizer()
        self.mic = sr.Microphone()
        
        # 음성 인식 설정
        self.language = 'ko-KR'
        self.timeout = 5
        self.phrase_time_limit = 5
        
        # 명령어 사전
        self.commands = {
            "경로안내": "start_navigation",
            "안내종료": "stop_navigation",
            "재탐색": "reroute",
            "안내일시중지": "pause_navigation",
            "안내재개": "resume_navigation",
            "음성안내켜기": "enable_voice",
            "음성안내끄기": "disable_voice"
        }
        
        # 초기화 시 마이크 보정
        self.calibrate_microphone()

    def calibrate_microphone(self) -> None:
        """주변 소음 레벨에 맞춰 마이크 보정"""
        try:
            logger.info("마이크 보정을 시작합니다...")
            with self.mic as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=2)
            logger.info("마이크 보정이 완료되었습니다.")
        except Exception as e:
            logger.error(f"마이크 보정 중 오류 발생: {str(e)}")

    def listen_for_command(self) -> Optional[str]:
        """음성 명령어 대기 및 인식"""
        try:
            with self.mic as source:
                logger.debug("음성 명령을 기다립니다...")
                audio = self.recognizer.listen(
                    source,
                    timeout=self.timeout,
                    phrase_time_limit=self.phrase_time_limit
                )
                
                text = self.recognizer.recognize_google(
                    audio,
                    language=self.language
                )
                logger.info(f"인식된 명령어: {text}")
                
                # 명령어 매칭
                for command, action in self.commands.items():
                    if command in text:
                        logger.info(f"매칭된 명령어: {command} -> {action}")
                        return action
                
                logger.debug("매칭되는 명령어가 없습니다.")
                return None
                
        except sr.WaitTimeoutError:
            logger.debug("음성 입력 시간 초과")
            return None
        except sr.UnknownValueError:
            logger.debug("인식할 수 없는 음성입니다.")
            return None
        except sr.RequestError as e:
            logger.error(f"Google STT 서비스 오류: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"음성 인식 중 오류 발생: {str(e)}")
            return None

    def listen_for_destination(self) -> Optional[str]:
        """목적지 음성 인식"""
        try:
            retry_count = 0
            max_retries = 3
            
            while retry_count < max_retries:
                with self.mic as source:
                    logger.info("목적지를 말씀해 주세요...")
                    
                    # 소음 레벨 재조정
                    self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                    
                    audio = self.recognizer.listen(
                        source,
                        timeout=self.timeout,
                        phrase_time_limit=self.phrase_time_limit
                    )
                    
                    text = self.recognizer.recognize_google(
                        audio,
                        language=self.language
                    )
                    
                    if text:
                        logger.info(f"인식된 목적지: {text}")
                        return text
                    
                retry_count += 1
                logger.debug(f"목적지 인식 재시도 ({retry_count}/{max_retries})")
                time.sleep(1)
            
            logger.warning("목적지 인식 실패")
            return None
            
        except sr.WaitTimeoutError:
            logger.debug("목적지 입력 시간 초과")
            return None
        except sr.UnknownValueError:
            logger.debug("인식할 수 없는 음성입니다.")
            return None
        except sr.RequestError as e:
            logger.error(f"Google STT 서비스 오류: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"목적지 인식 중 오류 발생: {str(e)}")
            return None

    def verify_audio_input(self) -> bool:
        """오디오 입력 장치 확인"""
        try:
            with self.mic as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
            return True
        except Exception as e:
            logger.error(f"오디오 입력 장치 확인 중 오류 발생: {str(e)}")
            return False

    def get_available_microphones(self) -> Dict[str, int]:
        """사용 가능한 마이크 목록 반환"""
        try:
            mics = {}
            for index, name in enumerate(sr.Microphone.list_microphone_names()):
                mics[name] = index
            return mics
        except Exception as e:
            logger.error(f"마이크 목록 조회 중 오류 발생: {str(e)}")
            return {}

    def change_microphone(self, device_index: int) -> bool:
        """마이크 변경"""
        try:
            self.mic = sr.Microphone(device_index=device_index)
            self.calibrate_microphone()
            return True
        except Exception as e:
            logger.error(f"마이크 변경 중 오류 발생: {str(e)}")
            return False

# 테스트 코드
if __name__ == "__main__":
    try:
        stt_manager = STTManager()
        
        # 사용 가능한 마이크 출력
        mics = stt_manager.get_available_microphones()
        print("\n사용 가능한 마이크:")
        for name, index in mics.items():
            print(f"- {name} (인덱스: {index})")
        
        # 오디오 입력 확인
        if not stt_manager.verify_audio_input():
            print("오디오 입력 장치를 확인할 수 없습니다.")
            exit(1)
        
        print("\n음성 인식 테스트를 시작합니다...")
        print("'경로안내'라고 말씀해 주세요.")
        
        while True:
            command = stt_manager.listen_for_command()
            
            if command == "start_navigation":
                print("\n목적지를 말씀해 주세요.")
                destination = stt_manager.listen_for_destination()
                if destination:
                    print(f"입력된 목적지: {destination}")
                else:
                    print("목적지를 인식하지 못했습니다.")
            elif command == "stop_navigation":
                print("내비게이션을 종료합니다.")
                break
            elif command:
                print(f"인식된 명령: {command}")
            
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\n프로그램을 종료합니다.")
    except Exception as e:
        print(f"오류 발생: {str(e)}")