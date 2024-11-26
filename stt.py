import speech_recognition as sr

def speech_to_text():
    
    recognizer = sr.Recognizer()
    mic = sr.Microphone()
    with mic as source:
        print("목적지를 말씀해 주세요...")
        audio = recognizer.listen(source)
    try:
        text = recognizer.recognize_google(audio, language="ko-KR")
        print(f"인식된 텍스트: {text}")
        return text
    except sr.UnknownValueError:
        print("음성을 인식할 수 없습니다.")
        return None
    
    #return "대연역"