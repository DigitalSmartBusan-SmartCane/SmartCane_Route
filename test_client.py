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
        locations = [
            {"latitude": 35.1336, "longitude": 129.1030},  # 출발지
            {"latitude": 35.1340, "longitude": 129.1020},
            {"latitude": 35.1345, "longitude": 129.1000},
            {"latitude": 35.1348, "longitude": 129.0980},
            {"latitude": 35.1349, "longitude": 129.0950},
            {"latitude": 35.1349964, "longitude": 129.091565},  # 대연역
        ]

        for loc in locations:
            location_message = {
                "type": "location",
                "data": loc
            }
            await websocket.send(json.dumps(location_message))
            response = await websocket.recv()
            print(f"서버 응답: {response}")
            time.sleep(3)  # 3초 간격으로 전송

if __name__ == "__main__":
    asyncio.run(test_navigation())