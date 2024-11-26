import requests

# 더 상세한 한국어 번역 사전
instruction_translation = {
    # 기본 방향
    "turn": "회전",
    "turn right": "우회전",
    "turn left": "좌회전",
    "depart": "출발",
    "arrive": "도착",
    "continue": "직진",
    "straight": "직진",
    
    # 상세 방향
    "slight right": "우측 방향",
    "slight left": "좌측 방향",
    "sharp right": "급우회전",
    "sharp left": "급좌회전",
    "uturn": "유턴",
    
    # 기타 안내
    "roundabout": "로터리",
    "merge": "차선 합류",
    "ramp": "램프",
    "exit": "출구",
    "keep right": "우측 유지",
    "keep left": "좌측 유지"
}

def get_korean_instruction(maneuver):
    """maneuver 정보를 바탕으로 한국어 안내문을 생성합니다."""
    maneuver_type = maneuver.get("type", "")
    modifier = maneuver.get("modifier", "")
    
    # type과 modifier를 조합한 키 생성
    instruction_key = f"{maneuver_type} {modifier}".strip()
    
    # 번역 시도 순서:
    # 1. 전체 문구 번역 시도
    # 2. type만 번역 시도
    # 3. 기본값 사용
    if instruction_key in instruction_translation:
        return instruction_translation[instruction_key]
    elif maneuver_type in instruction_translation:
        return instruction_translation[maneuver_type]
    else:
        return "직진"  # 기본값

def format_instruction(step):
    """경로 안내 단계를 한국어로 포맷팅합니다."""
    try:
        # 거리 포맷팅
        distance_m = int(step.get("distance", 0))
        if distance_m >= 1000:
            distance_text = f"{distance_m/1000:.1f}km"
        else:
            distance_text = f"{distance_m}m"
        
        # 안내문 생성
        maneuver = step.get("maneuver", {})
        instruction = get_korean_instruction(maneuver)
        
        # 최종 안내문 조합
        if maneuver.get("type") == "arrive":
            return f"{distance_text} 앞에서 {instruction}입니다"
        else:
            return f"{distance_text} 앞에서 {instruction}하세요"
        
    except Exception as e:
        print(f"안내문 생성 중 오류 발생: {str(e)}")
        return "안내문을 생성할 수 없습니다"

def get_directions(current_location_coords, destination_coords):
    """경로 안내를 요청하고 한국어로 변환된 안내문을 반환합니다."""
    osrm_url = (
        f"http://localhost:5000/route/v1/driving/"
        f"{current_location_coords[1]},{current_location_coords[0]};"
        f"{destination_coords[1]},{destination_coords[0]}"
        "?overview=false&steps=true"
    )
    
    try:
        response = requests.get(osrm_url)
        directions_result = response.json()
        
        if not directions_result.get('routes'):
            return ["경로를 찾을 수 없습니다."]
            
        steps = []
        for leg in directions_result['routes'][0].get('legs', []):
            for step in leg.get('steps', []):
                formatted_instruction = format_instruction(step)
                steps.append(formatted_instruction)
                
        return steps
        
    except Exception as e:
        print(f"경로 검색 중 오류가 발생했습니다: {str(e)}")
        return None