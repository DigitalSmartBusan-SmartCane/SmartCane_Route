import os
import folium
import webbrowser
import tkinter as tk
import logging
from typing import Tuple, List, Optional, Dict
import threading

logger = logging.getLogger('NavigationGUI')

class MapGUI:
    def __init__(self, master: tk.Tk):
        self.master = master
        self.master.title("Navigation")
        self.master.geometry("800x600")
        self.master.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.current_location = None
        self.destination = None
        self.start_location = (35.1336, 129.1030)  # 부경대학교
        self.map_path = "map.html"
        self.setup_map()

    def on_closing(self):
        """창 종료 시 호출되는 함수"""
        try:
            if hasattr(self, 'map_path') and os.path.exists(self.map_path):
                os.remove(self.map_path)
            self.master.destroy()  # tkinter 창만 종료
        except Exception as e:
            logger.error(f"GUI 종료 중 오류 발생: {str(e)}")

    def setup_map(self):
        """초기 지도 설정"""
        # 부경대학교 위치로 초기화
        self.map = folium.Map(location=self.start_location, zoom_start=15)
        
        # 출발지 마커 (부경대학교)
        folium.Marker(
            location=self.start_location,
            popup="부경대학교 (출발)",
            icon=folium.Icon(color='green', icon='info-sign')
        ).add_to(self.map)

        self.add_map_to_html()
        
        # JavaScript 자동 새로고침 코드 추가 (한 번만 호출)
        self.add_auto_refresh()

    def add_auto_refresh(self):
        """JavaScript 자동 새로고침 코드 추가"""
        refresh_script = """
        <script>
        function refreshPage() {
            document.location.reload();
        }
        setInterval(refreshPage, 3000);  // 3초마다 새로고침
        </script>
        """
        with open(self.map_path, 'a', encoding='utf-8') as f:
            f.write(refresh_script)

    def add_map_to_html(self):
        """지도 데이터를 HTML 파일로 저장 및 웹 브라우저에서 열기"""
        try:
            self.map_path = "map.html"
            self.map.save(self.map_path)
            webbrowser.open("file://" + os.path.realpath(self.map_path))
            logger.info("지도 생성 및 웹 브라우저 열기 완료")
        except Exception as e:
            logger.error(f"지도 생성 중 오류 발생: {str(e)}")

    def update_map_async(self, current_location: Tuple[float, float], route: Optional[List[Tuple[float, float]]] = None, destination: Optional[Dict[str, float]] = None):
        """비동기 지도 업데이트"""
        threading.Thread(target=self.update_map, 
                         args=(current_location, route, destination),
                         daemon=True).start()

    def set_destination(self, destination: Tuple[float, float], address: str):
        """목적지 설정 및 지도 업데이트"""
        try:
            self.destination = {'latitude': destination[0], 'longitude': destination[1]}
            self.update_map(self.current_location, route=None, destination=self.destination)
            logger.info(f"목적지 설정: {destination}, 주소: {address}")
        except Exception as e:
            logger.error(f"목적지 설정 중 오류 발생: {str(e)}")

    def update_map(self, current_location: Tuple[float, float], route: Optional[List[Tuple[float, float]]] = None, destination: Optional[Dict[str, float]] = None):
        """지도 업데이트"""
        try:
            logger.debug(f"지도 업데이트 시작: 현재 위치={current_location}, 경로={'있음' if route else '없음'}, 목적지={'있음' if destination else '없음'}")
            self.current_location = current_location
            
            # 현재 위치 중심으로 지도 생성
            self.map = folium.Map(location=current_location, zoom_start=14)
            
            # 출발지 마커 (부경대학교)
            folium.Marker(
                location=self.start_location,
                popup="부경대학교 (출발)",
                icon=folium.Icon(color='green', icon='info-sign')
            ).add_to(self.map)

            # 현재 위치 마커
            folium.Marker(
                location=current_location,
                popup=f"현재 위치 ({current_location[0]:.4f}, {current_location[1]:.4f})",
                icon=folium.Icon(color='blue', icon='info-sign')
            ).add_to(self.map)

            # 목적지 마커
            if destination:
                destination_coords = (destination['latitude'], destination['longitude'])
                folium.Marker(
                    location=destination_coords,
                    popup="대연역 (목적지)",
                    icon=folium.Icon(color='red', icon='info-sign')
                ).add_to(self.map)
                logger.debug(f"목적지 마커 추가: {destination_coords}")

            # 경로 그리기
            if route:
                folium.PolyLine(
                    route,
                    weight=3,
                    color='blue',
                    opacity=0.8
                ).add_to(self.map)
                logger.debug("경로 선 추가")

            # 지도 저장 및 브라우저 새로고침
            self.map.save(self.map_path)
            logger.info("지도 업데이트 완료")
            
            # 자동 새로고침 스크립트 추가
            with open(self.map_path, 'a', encoding='utf-8') as f:
                f.write("""
                <script>
                setTimeout(function() {
                    location.reload();
                }, 2000);
                </script>
                """)
                
        except Exception as e:
            logger.error(f"지도 업데이트 중 오류 발생: {str(e)}")

    def update_map_async(self, current_location: Tuple[float, float], route: Optional[List[Tuple[float, float]]] = None, destination: Optional[Dict[str, float]] = None):
        """비동기 지도 업데이트"""
        if destination:
            self.set_destination((destination['latitude'], destination['longitude']), "목적지")
        threading.Thread(target=self.update_map, 
                         args=(current_location, route, destination),
                         daemon=True).start()

    def set_destination(self, destination: Tuple[float, float], address: str):
        """목적지 설정 및 지도 업데이트"""
        try:
            self.destination = {'latitude': destination[0], 'longitude': destination[1]}
            self.update_map(self.current_location, route=None, destination=self.destination)
            logger.info(f"목적지 설정: {destination}, 주소: {address}")
        except Exception as e:
            logger.error(f"목적지 설정 중 오류 발생: {str(e)}")

    def __del__(self):
        if hasattr(self, 'map_path') and os.path.exists(self.map_path):
            os.remove(self.map_path)