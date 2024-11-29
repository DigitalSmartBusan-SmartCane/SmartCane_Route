import tkinter as tk
import folium
import webbrowser
import os
from typing import Optional, Tuple, List
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('MapGUI')

class MapGUI:
    def __init__(self, master: tk.Tk):
        self.master = master
        self.master.title("Map View")
        self.master.geometry("800x600")
        self.current_location = None
        self.destination = None
        self.setup_map()

    def setup_map(self):
        try:
            # 초기 지도 생성 (부산 중심)
            default_location = [35.1795543, 129.0756416]
            self.map = folium.Map(
                location=default_location,
                zoom_start=13,
                tiles="OpenStreetMap"
            )
            
            self.map_path = os.path.join(os.getcwd(), "map.html")
            self.map.save(self.map_path)
            webbrowser.open(self.map_path)
                
        except Exception as e:
            logger.error(f"지도 초기화 오류: {str(e)}")

    def update_map(self, current_location: Tuple[float, float], route: Optional[List] = None):
        try:
            self.map = folium.Map(
                location=current_location,
                zoom_start=15,
                tiles="OpenStreetMap"
            )

            folium.Marker(
                current_location,
                popup="현재 위치",
                icon=folium.Icon(color='red', icon='info-sign')
            ).add_to(self.map)

            if self.destination:
                folium.Marker(
                    self.destination,
                    popup="목적지",
                    icon=folium.Icon(color='green', icon='info-sign')
                ).add_to(self.map)

            if route:
                coordinates = [list(coord) for coord in route]
                folium.PolyLine(
                    coordinates,
                    weight=2,
                    color='blue',
                    opacity=0.8
                ).add_to(self.map)

            self.map.save(self.map_path)
            with open(self.map_path, 'a', encoding='utf-8') as f:
                f.write(
                    '''
                    <script>
                    setTimeout(function() {
                        location.reload();
                    }, 4000);
                    </script>
                    '''
                )
        except Exception as e:
            logger.error(f"지도 업데이트 오류: {str(e)}")

    def __del__(self):
        if hasattr(self, 'map_path') and os.path.exists(self.map_path):
            os.remove(self.map_path)