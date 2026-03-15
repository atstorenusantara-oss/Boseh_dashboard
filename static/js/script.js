function updateClock() {
    const clockElement = document.getElementById('clock');
    const dateElement = document.getElementById('date');
    const now = new Date();

    // Update Time
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');
    const seconds = String(now.getSeconds()).padStart(2, '0');
    clockElement.textContent = `${hours}:${minutes}:${seconds}`;

    // Update Date
    const days = ['Minggu', 'Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu'];
    const months = [
        'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
        'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember'
    ];
    
    const dayName = days[now.getDay()];
    const date = now.getDate();
    const monthName = months[now.getMonth()];
    const year = now.getFullYear();

    dateElement.textContent = `${dayName}, ${date} ${monthName} ${year}`;
}

// Initial call
updateClock();

async function refreshSlots() {
    try {
        const response = await fetch('/api/slots');
        const data = await response.json();
        const dockingArea = document.querySelector('.docking-slots');
        
        let html = '';
        data.slots.forEach(slot => {
            html += `
                <div class="slot">
                    <span class="slot-number">${slot.slot_number}${(slot.has_bike && slot.bike_status) ? ` <span style="color: #666; font-size: 0.8em; font-weight: normal;">(${slot.bike_status})</span>` : ''}</span>
                    <div class="bike-placeholder">
                        ${slot.has_bike ? `<img src="/static/img/bike.png" alt="Bike" class="bike-img">` : ''}
                    </div>
                    ${(slot.has_bike && slot.rfid_tag) ? `<div class="rfid-display">${slot.rfid_tag}</div>` : ''}
                </div>
            `;
        });
        
        dockingArea.innerHTML = html;
        console.log('Slots updated dynamically');
    } catch (err) {
        console.error('Failed to refresh slots:', err);
    }
}

// EventSource to listen for updates from Admin/IoT
const source = new EventSource('/stream');

// Listen specifically for the named 'refresh' event
source.addEventListener('refresh', function(event) {
    console.log('Refresh event received:', event.data);
    refreshSlots();
});

// Listen for rent requests from remote API broker
source.addEventListener('rent_request', function(event) {
    console.log('Rent request received:', event.data);
    try {
        const payload = JSON.parse(event.data);
        showRentPopup(payload);
        // Refresh slots immediately just in case the backend also synced
        refreshSlots();
    } catch (e) {
        console.error("Error parsing rent_request:", e);
    }
});

let rentPopupTimeout;

function showRentPopup(rentData) {
    const modal = document.getElementById('rentModal');
    if (!modal) return;
    
    // Normalize escaped path if it exists
    let photoUrl = rentData.customer?.photo || '';
    photoUrl = photoUrl.replace(/\\\//g, '/'); // Remove JSON escape slashes
    
    document.getElementById('rentCustPhoto').src = photoUrl;
    document.getElementById('rentCustName').value = rentData.customer?.name || '';
    document.getElementById('rentBikeId').value = rentData.bike?.bike_id || '';
    document.getElementById('rentDocking').value = rentData.bike?.docking_id || '';
    
    modal.style.display = 'flex';
    
    // Clear any existing timeout
    if (rentPopupTimeout) {
        clearTimeout(rentPopupTimeout);
    }
    
    // Automatically close after 5 seconds
    rentPopupTimeout = setTimeout(() => {
        modal.style.display = 'none';
    }, 5000);
}

// Basic document interaction (dom ready)
document.addEventListener('DOMContentLoaded', () => {
    // Other DOM interactions can go here
});

// General error handling for SSE
source.onerror = function(err) {
    console.warn('EventSource connection lost. Attempting to reconnect...');
};

// Add some interaction to the kiosk button
const kioskBtn = document.querySelector('.kiosk-button');
if (kioskBtn) {
    kioskBtn.addEventListener('click', () => {
        alert('Memulai proses sewa Boseh...');
    });
}
