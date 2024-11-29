import asyncio
import websockets
import json
import time

async def simulate_navigation():
    # 웹소켓 서버 연결 (로컬 테스트용)
    uri = "ws://localhost:8000/ws"
    async with websockets.connect(uri) as websocket:
        print("서버에 연결되었습니다.")
        
        try:
            # 1. 목적지 설정 (테스트용)
            destination_msg = {
                "type": "destination",
                "data": "부경대학교 부산광역시"  # 테스트할 목적지
            }
            print("\n목적지 전송:", destination_msg["data"])
            await websocket.send(json.dumps(destination_msg))
            response = await websocket.recv()
            print("서버 응답:", response)

            # 2. GPS 위치 시뮬레이션
            test_coordinates = [
                {"latitude": 35.1456, "longitude": 129.0783},  # 부경대학교
                {"latitude": 35.1367, "longitude": 129.0711},
                {"latitude": 35.1278, "longitude": 129.0639},
                {"latitude": 35.1189, "longitude": 129.0567},
                {"latitude": 35.1100, "longitude": 129.0495},  # 경성대역
            ]

            # 위치 데이터 전송
            for coord in test_coordinates:
                message = {
                    "type": "location",
                    "data": coord
                }
                await websocket.send(json.dumps(message))
                await asyncio.sleep(5)  # 5초 간격으로 위치 업데이트

            print("\n테스트 완료")

        except Exception as e:
            print(f"오류 발생: {str(e)}")

if __name__ == "__main__":
    print("내비게이션 테스트를 시작합니다...")
    asyncio.get_event_loop().run_until_complete(simulate_navigation())