import requests
from urllib.parse import quote

def validate_address(address):
    # Nominatim geocoding API for OpenStreetMap
    encoded_address = quote(address)
    url = f"https://nominatim.openstreetmap.org/search?q={encoded_address}&format=json&limit=1"

    headers = {
        'User-Agent': 'MyApp/1.0 (http://mywebsite.com)'  # 사용자 정의 User-Agent
    }

    try:
        response = requests.get(url, headers=headers)
        #print(f"응답 상태 코드: {response.status_code}")
        #print(f"응답 내용: {response.text}")
        
        geocode_result = response.json()

        if geocode_result:
            location = geocode_result[0]
            latitude = float(location['lat'])
            longitude = float(location['lon'])
            formatted_address = location['display_name']
            return latitude, longitude, formatted_address
        else:
            print("유효하지 않은 주소입니다.")
            return None
    except Exception as e:
        print(f"주소 변환 중 오류가 발생했습니다: {str(e)}")
        return None
