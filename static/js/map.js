let map;

function initMap() {
    map = L.map('map').setView([35.1795543, 129.0756416], 13);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
    }).addTo(map);
}