const ws = new WebSocket('ws://localhost:8000/ws');

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    // 메시지 타입에 따른 처리
    console.log('받은 메시지:', data);
};

ws.onclose = function(event) {
    console.log('WebSocket 연결 종료');
};

ws.onerror = function(error) {
    console.error('WebSocket 에러:', error);
};