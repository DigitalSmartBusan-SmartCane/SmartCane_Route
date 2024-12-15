import yaml
import os
from typing import Dict, Any

class ConfigManager:
    DEFAULT_CONFIG = {
        'server': {
            'host': "0.0.0.0",
            'port': 8000,
            'ws_path': "/ws"
        },
        'osrm': {
            'path': "C:/osrm",
            'map_path': "C:/osrm/maps/korea-latest.osrm",
            'port': 5000,
            'algorithm': "mld"
        },
        'client': {
            'server_url': "ws://localhost:8000/ws",
            'audio': {
                'input_device': 1,
                'output_device': 20
            }
        },
        'routing': {
            'osrm_url': "http://localhost:5000",
            'reroute_threshold': 10,
            'arrival_threshold': 20
        },
        'geocoding': {
            'user_agent': "MyApp/1.0",
            'timeout': 10
        },
        'tts': {
            'rate': 150,
            'language': "ko"
        }
    }

    def __init__(self, config_path: str = 'config.yaml'):
        """설정 관리자 초기화"""
        self.config_path = config_path
        self.config = self.load_config()

    def load_config(self) -> Dict[str, Any]:
        """설정 파일 로드"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as file:
                    user_config = yaml.safe_load(file)
                    # 기본 설정과 사용자 설정 병합
                    return self.merge_configs(self.DEFAULT_CONFIG, user_config)
            else:
                print(f"설정 파일을 찾을 수 없습니다: {self.config_path}")
                print("기본 설정을 사용합니다.")
                self.save_config(self.DEFAULT_CONFIG)  # 기본 설정 파일 생성
                return self.DEFAULT_CONFIG

        except Exception as e:
            print(f"설정 파일 로드 중 오류 발생: {str(e)}")
            print("기본 설정을 사용합니다.")
            return self.DEFAULT_CONFIG

    def merge_configs(self, default: Dict, user: Dict) -> Dict:
        """기본 설정과 사용자 설정을 재귀적으로 병합"""
        merged = default.copy()

        for key, value in user.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = self.merge_configs(merged[key], value)
            else:
                merged[key] = value

        return merged

    def save_config(self, config: Dict = None):
        """설정을 파일로 저장"""
        try:
            if config is None:
                config = self.config

            with open(self.config_path, 'w', encoding='utf-8') as file:
                yaml.dump(config, file, allow_unicode=True, default_flow_style=False)
            print(f"설정이 저장되었습니다: {self.config_path}")

        except Exception as e:
            print(f"설정 저장 중 오류 발생: {str(e)}")

    def get(self, key: str, default: Any = None) -> Any:
        """설정값 가져오기"""
        try:
            keys = key.split('.')
            value = self.config
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default

    def update(self, key: str, value: Any, save: bool = True):
        """설정값 업데이트"""
        try:
            keys = key.split('.')
            current = self.config
            for k in keys[:-1]:
                current = current.setdefault(k, {})
            current[keys[-1]] = value

            if save:
                self.save_config()

        except Exception as e:
            print(f"설정 업데이트 중 오류 발생: {str(e)}")

    def validate(self) -> bool:
        """설정 유효성 검사"""
        try:
            required_fields = [
                'server.host',
                'server.port',
                'client.server_url',
                'routing.osrm_url'
            ]

            for field in required_fields:
                if not self.get(field):
                    print(f"필수 설정이 없습니다: {field}")
                    return False

            return True

        except Exception as e:
            print(f"설정 검증 중 오류 발생: {str(e)}")
            return False

# 전역 설정 관리자 인스턴스
config_manager = ConfigManager()

def load_config():
    """전역 설정 가져오기"""
    return config_manager.config

def get_config(key: str, default: Any = None) -> Any:
    """특정 설정값 가져오기"""
    return config_manager.get(key, default)

def update_config(key: str, value: Any, save: bool = True):
    """설정값 업데이트"""
    config_manager.update(key, value, save)

def validate_routing_config(config: Dict) -> bool:
    """라우팅 설정 유효성 검사"""
    required_fields = ['osrm_url', 'reroute_threshold', 'arrival_threshold']
    return all(field in config['routing'] for field in required_fields)