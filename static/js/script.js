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

// Initial call and set interval for real-time updates
updateClock();
setInterval(updateClock, 1000);

async function refreshSlots() {
    try {
        const response = await fetch('/api/slots');
        const data = await response.json();
        const dockingArea = document.querySelector('.docking-slots');
        
        let html = '';
        data.slots.forEach(slot => {
            // Extract countdown number if exists in bike_status (e.g. "Silahkan ambil sepeda (53s)")
            let countdownHtml = '';
            let displayStatus = slot.bike_status || '';
            
            const match = displayStatus.match(/\(([^)]+)\)/);
            if (match && slot.has_bike) {
                countdownHtml = `<div class="countdown-box">${match[1]}</div>`;
                // Clean the status string for the top text display
                displayStatus = displayStatus.replace(/\s*\([^)]+\)/, '');
            } else if (match && !slot.has_bike) {
                // If countdown data exists but bike is gone, just hide everything
                displayStatus = '';
            }

            html += `
                <div class="slot">
                    <span class="slot-number">${slot.slot_number}${(slot.has_bike && displayStatus) ? ` <span style="color: #666; font-size: 0.8em; font-weight: normal;">(${displayStatus})</span>` : ''}</span>
                    <div class="bike-placeholder">
                        ${countdownHtml}
                        ${slot.has_bike ? `<img src="/static/img/bike.png" alt="Bike" class="bike-img">` : ''}
                        ${slot.maintenance ? `
                            <div class="maintenance-overlay">
                                <div class="maint-icon">
                                    <svg width="60" height="60" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                        <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"></path>
                                    </svg>
                                </div>
                                <span>MAINTENANCE</span>
                            </div>
                        ` : ''}
                    </div>
                    ${(slot.has_bike && (slot.rfid_tag || slot.bike_name)) ? `<div class="rfid-display">${slot.bike_name ? slot.bike_name : slot.rfid_tag}</div>` : ''}
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
    
    // FILTER: Only show if customer has a valid name (or not empty)
    // To handle the user's specific request for "User" vs "Customer" roles
    const name = rentData.customer?.name || '';
    const role = (rentData.customer?.role || '').toLowerCase(); // Fallback to check role if exists
    
    // If name is empty or it's explicitly a "customer" role, we hide the popup
    if (!name || role === 'customer') {
        console.log("Rent request: Skipping popup for generic customer/empty name.");
        return; 
    }

    document.getElementById('rentCustPhoto').src = photoUrl;
    document.getElementById('rentCustName').value = name;
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

// Payment UI logic
let paymentPopupTimeout;

// Listen for payment requests from remote API broker
source.addEventListener('payment_request', function(event) {
    console.log('Payment request received:', event.data);
    try {
        const payload = JSON.parse(event.data);
        showPaymentPopup(payload);
    } catch (e) {
        console.error("Error parsing payment_request:", e);
    }
});

function showPaymentPopup(paymentData) {
    const modal = document.getElementById('paymentModal');
    if (!modal) return;
    
    // Safety check objects
    const customerName = paymentData.customer?.name || 'Unknown User';
    const amount = paymentData.payment?.amount || 0;
    let qrisContent = paymentData.payment?.qris_content || '';
    
    // Normalize escaped path if it exists
    qrisContent = qrisContent.replace(/\\\//g, '/'); // Remove JSON escape slashes
    
    // Format currency to IDR
    const formatRp = new Intl.NumberFormat('id-ID', {
        style: 'currency',
        currency: 'IDR',
        minimumFractionDigits: 0
    }).format(amount);

    document.getElementById('paymentCustName').value = customerName;
    document.getElementById('paymentAmount').value = formatRp;
    
    // Fetch QR Code from backend generate endpoint
    document.getElementById('paymentQrcode').src = `/api/qris?data=${encodeURIComponent(qrisContent)}`;
    
    modal.style.display = 'flex';
    
    // Clear any existing timeout
    if (paymentPopupTimeout) {
        clearTimeout(paymentPopupTimeout);
    }
    
    // Automatically close after 10 seconds as requested
    paymentPopupTimeout = setTimeout(() => {
        modal.style.display = 'none';
    }, 10000);
}

function toggleNavModal() {
    const modal = document.getElementById('navModal');
    if (!modal) return;
    if (modal.style.display === 'none' || modal.style.display === '') {
        modal.style.display = 'flex';
    } else {
        modal.style.display = 'none';
    }
}

async function updateServerStatus() {
    try {
        const response = await fetch('/api/health');
        const data = await response.json();
        
        const light = document.getElementById('serverStatusLight');
        const label = document.getElementById('serverStatusLabel');
        
        if (data.status) {
            light.classList.remove('offline');
            label.textContent = 'Server';
            label.style.color = 'white';
        } else {
            light.classList.add('offline');
            label.textContent = data.message || 'Offline';
            label.style.color = '#f87171';
        }
    } catch (err) {
        console.error('Failed to check server health:', err);
        const light = document.getElementById('serverStatusLight');
        const label = document.getElementById('serverStatusLabel');
        if (light) light.classList.add('offline');
        if (label) {
            label.textContent = 'Connection Error';
            label.style.color = '#f87171';
        }
    }
}

// Basic document interaction (dom ready)
document.addEventListener('DOMContentLoaded', () => {
    // Other DOM interactions can go here
    refreshSlots(); // Populate slots on load
    updateServerStatus(); // Initial status check
    setInterval(updateServerStatus, 15000); // Check every 15 seconds
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
