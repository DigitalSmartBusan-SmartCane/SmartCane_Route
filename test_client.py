# test_client.py
import asyncio
import websockets
import json
import time

async def test_navigation():
    uri = "ws://localhost:8000/ws"
    async with websockets.connect(uri) as websocket:
        # 목적지 설정: 대연역
        destination = {
            "type": "destination",
            "data": {
                "latitude": 35.1349964,
                "longitude": 129.091565
            }
        }
        await websocket.send(json.dumps(destination))
        response = await websocket.recv()
        print(f"서버 응답: {response}")

        # 위치 업데이트: 부경대학교에서 대연역까지 이동
        # 더 상세한 경로 포인트 추가
        locations = [
            {"latitude": 35.132786, "longitude": 129.106946},  # 부경대 창의관
            {"latitude": 35.133770, "longitude": 129.105906},  
            {"latitude": 35.133481, "longitude": 129.102365},  
            {"latitude": 35.133832, "longitude": 129.100343}, 
            {"latitude": 35.134055, "longitude": 129.098454},  
            {"latitude": 35.134744, "longitude": 129.097306},  
            {"latitude": 35.135235, "longitude": 129.095949},  
            {"latitude": 35.135332, "longitude": 129.094667},  
            {"latitude": 35.135126, "longitude": 129.093498},  
            {"latitude": 35.1349964, "longitude": 129.091565},  # 대연역 도착
        ]

        for loc in locations:
            location_message = {
                "type": "location",
                "data": loc
            }
            await websocket.send(json.dumps(location_message))
            response = await websocket.recv()
            print(f"서버 응답: {response}")
            await asyncio.sleep(5)  # 5초 간격으로 위치 업데이트

if __name__ == "__main__":
    asyncio.run(test_navigation())