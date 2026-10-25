const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
let chosenFile = null, chosenSample = null;

// ---- tabs
$$('.tab').forEach(t => t.onclick = () => {
  $$('.tab').forEach(x => x.classList.remove('active')); t.classList.add('active');
  $$('.panel').forEach(p => p.classList.remove('active')); $('#' + t.dataset.tab).classList.add('active');
  if (t.dataset.tab === 'locations') loadLocations();
  if (t.dataset.tab === 'history') loadHistory();
});

// ---- engine badges
fetch('/api/info').then(r => r.json()).then(i => {
  $('#engines').innerHTML = `<span>Detector: ${i.detector}</span>` + i.ocr.map(o => `<span>OCR: ${o}</span>`).join('');
});

// ---- choose image & camera
const fileIn = $('#file'), drop = $('#drop');
const cameraBox = $('#cameraBox'), cameraVideo = $('#cameraVideo'), cameraCanvas = $('#cameraCanvas');
const startCameraBtn = $('#startCameraBtn'), stopCameraBtn = $('#stopCameraBtn'), captureBtn = $('#captureBtn'), browseBtn = $('#browseBtn');
let cameraStream = null;

if (browseBtn) browseBtn.onclick = () => fileIn.click();

async function startCamera() {
  if (cameraStream) stopCamera();
  try {
    const constraints = {
      video: { facingMode: { ideal: "environment" }, width: { ideal: 1280 }, height: { ideal: 720 } }
    };
    cameraStream = await navigator.mediaDevices.getUserMedia(constraints);
  } catch (err) {
    try {
      cameraStream = await navigator.mediaDevices.getUserMedia({ video: true });
    } catch (err2) {
      alert("Unable to open camera: " + (err2.message || err2.name) + ".\nPlease ensure camera access is allowed in your browser settings.");
      return;
    }
  }
  cameraVideo.srcObject = cameraStream;
  cameraBox.classList.remove('hidden');
  drop.classList.add('hidden');
  $('#preview').classList.add('hidden');
  $('#status').textContent = 'Camera active. Frame the signboard and tap "Capture Photo".';
}

function stopCamera() {
  if (cameraStream) {
    cameraStream.getTracks().forEach(t => t.stop());
    cameraStream = null;
  }
  cameraBox.classList.add('hidden');
  drop.classList.remove('hidden');
}

if (startCameraBtn) startCameraBtn.onclick = startCamera;
if (stopCameraBtn) stopCameraBtn.onclick = stopCamera;

if (captureBtn) captureBtn.onclick = () => {
  if (!cameraVideo.videoWidth) return;
  cameraCanvas.width = cameraVideo.videoWidth;
  cameraCanvas.height = cameraVideo.videoHeight;
  const ctx = cameraCanvas.getContext('2d');
  ctx.drawImage(cameraVideo, 0, 0);
  cameraCanvas.toBlob(blob => {
    if (!blob) return;
    const file = new File([blob], "camera_capture.jpg", { type: "image/jpeg" });
    stopCamera();
    setFile(file);
    $('#status').textContent = 'Photo captured! Click "Scan Signboard".';
  }, 'image/jpeg', 0.95);
};

fileIn.onchange = () => { stopCamera(); setFile(fileIn.files[0]); };
['dragover', 'dragenter'].forEach(e => drop.addEventListener(e, ev => { ev.preventDefault(); drop.classList.add('over'); }));
['dragleave', 'drop'].forEach(e => drop.addEventListener(e, ev => { ev.preventDefault(); drop.classList.remove('over'); }));
drop.addEventListener('drop', ev => { stopCamera(); setFile(ev.dataTransfer.files[0]); });
function setFile(f) {
  if (!f) return;
  chosenFile = f; chosenSample = null;
  $$('.samples figure').forEach(x => x.classList.remove('sel'));
  showPreview(URL.createObjectURL(f));
}
function showPreview(src) {
  const p = $('#preview'); p.src = src; p.classList.remove('hidden'); $('#scanBtn').disabled = false;
  $('#out').innerHTML = ''; $('#status').textContent = 'Ready to scan.';
}

// ---- samples
fetch('/api/samples').then(r => r.json()).then(list => {
  $('#samples').innerHTML = list.map(s =>
    `<figure data-f="${s.file}"><img src="/samples/${s.file}"><figcaption>${s.title}</figcaption></figure>`).join('');
  $$('.samples figure').forEach(fg => fg.onclick = () => {
    stopCamera();
    chosenSample = fg.dataset.f; chosenFile = null;
    $$('.samples figure').forEach(x => x.classList.remove('sel')); fg.classList.add('sel');
    showPreview('/samples/' + chosenSample);
  });
});

// ---- scan
$('#scanBtn').onclick = async () => {
  const fd = new FormData();
  if (chosenSample) fd.append('sample', chosenSample); else if (chosenFile) fd.append('image', chosenFile); else return;
  $('#out').innerHTML = ''; $('#status').textContent = 'Reading the signboard...';
  $('#loader').classList.remove('hidden'); $('#scanBtn').disabled = true;
  try {
    const res = await fetch('/api/recognize', { method: 'POST', body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Request failed');
    render(data);
  } catch (e) { $('#status').innerHTML = `<span class="err">${e.message}</span>`; }
  $('#loader').classList.add('hidden'); $('#scanBtn').disabled = false;
};

function esc(s) { return String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }

// ================= GPS & MAP UTILITIES =================
let userGps = null;
let campusMap = null, campusMarkers = [];
let resultMap = null, resultMarkers = [], resultRouteLine = null;
let allCampusLocations = [];

// Haversine formula to compute ground distance in meters
function calcDistanceMeters(lat1, lon1, lat2, lon2) {
  const R = 6371e3;
  const rad = Math.PI / 180;
  const dLat = (lat2 - lat1) * rad;
  const dLon = (lon2 - lon1) * rad;
  const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
            Math.cos(lat1 * rad) * Math.cos(lat2 * rad) *
            Math.sin(dLon / 2) * Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return Math.round(R * c);
}

function getLiveGps(onSuccess, onError) {
  if (!navigator.geolocation) {
    if (onError) onError(new Error("Geolocation is not supported by your browser."));
    return;
  }
  navigator.geolocation.getCurrentPosition(
    pos => {
      userGps = { lat: pos.coords.latitude, lng: pos.coords.longitude, accuracy: Math.round(pos.coords.accuracy) };
      if (onSuccess) onSuccess(userGps);
    },
    err => {
      let msg = "Could not fetch GPS: ";
      if (err.code === 1) msg += "Permission denied. Please allow location access.";
      else if (err.code === 2) msg += "Position unavailable.";
      else if (err.code === 3) msg += "Request timed out.";
      else msg += err.message;
      if (onError) onError(new Error(msg));
    },
    { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
  );
}

// Create a custom pulsing user location icon
function getUserIcon() {
  return L.divIcon({
    className: 'custom-user-icon',
    html: '<div class="user-gps-pulse"></div>',
    iconSize: [20, 20],
    iconAnchor: [10, 10]
  });
}

function render(d) {
  $('#status').innerHTML = `Done in <b>${d.seconds}s</b>.`;
  let html = `<img class="annot" src="${d.annotated}" alt="annotated">`;
  if (!d.found) { html += `<p class="err">${esc(d.message)}</p>`; $('#out').innerHTML = html; return; }
  
  d.results.forEach((r, i) => {
    const m = r.match;
    html += `<div class="board ${m ? 'ok' : 'unk'}">`;
    if (m) {
      const L = m.location;
      const hasGps = L.latitude != null && L.longitude != null;
      html += `<h3>${esc(L.name)} <small class="muted">(match ${(m.score * 100).toFixed(0)}%)</small></h3>`;
      
      if (hasGps) {
        html += `<div class="gps-banner">
          <div><span class="gps-chip">📍 GPS: ${L.latitude.toFixed(6)}, ${L.longitude.toFixed(6)}</span></div>
          <div class="nav-actions">
            <a href="https://www.google.com/maps/dir/?api=1&destination=${L.latitude},${L.longitude}" target="_blank" class="btn small gmaps">🧭 Open in Google Maps</a>
            <button type="button" class="btn small gps-btn" onclick="measureUserGps(${i}, ${L.latitude}, ${L.longitude})">📡 My Live GPS &amp; Distance</button>
          </div>
        </div>
        <div id="gpsAlert${i}"></div>
        <!-- Embedded Interactive Result Map -->
        <div id="resultMap${i}" class="result-map"></div>`;
      }

      html += `<div class="kv"><b>Block</b><span>${esc(L.block)}</span><b>Floor</b><span>${esc(L.floor)}</span>
      <b>Category</b><span>${esc(L.category)}</span><b>Timings</b><span>${esc(L.timings)}</span>
      <b>About</b><span>${esc(L.description)}</span></div>`;
    } else {
      html += `<h3>Board not in database</h3><p class="muted">The text was read but no campus location matches it.</p>
      <button class="btn small ghost" onclick="prefill('${esc((r.text[0] || '').replace(/'/g, ''))}')">Add this board to the database</button>`;
    }
    html += `<img class="crop" src="${r.crop}" alt="board"><div class="chips">${r.text.map(t => `<span>${esc(t)}</span>`).join('')}</div>
      <div class="muted">Detection confidence ${(r.confidence * 100).toFixed(0)}%</div><div class="meter"><i style="width:${r.confidence * 100}%"></i></div>
      <div class="muted">OCR confidence ${(r.ocr_confidence * 100).toFixed(0)}% &middot; ${esc(r.engine)} (${esc(r.variant)})</div>
      <div class="meter"><i style="width:${r.ocr_confidence * 100}%;background:var(--blue)"></i></div>`;
    
    if (m && m.location.directions && m.location.directions.length) {
      const L = m.location;
      html += `<h3>Navigate from here</h3>
      <select id="dest${i}" onchange="pickDest(${i})"><option value="">All directions</option>${L.directions.map((x, k) => `<option value="${k}">${esc(x.destination)} (${x.distance_m} m)</option>`).join('')}</select>
      <ul class="dirs" id="dirs${i}">${L.directions.map((x, k) => `<li data-k="${k}"><b>${esc(x.destination)}</b> &ndash; ${esc(x.instruction)} <span class="muted">(${x.distance_m} m)</span></li>`).join('')}</ul>
      <button class="btn small ghost" onclick="speak(${i})">&#128266; Speak directions</button>`;
      window['_dirs' + i] = L;
    }
    html += `</div>`;
  });
  $('#out').innerHTML = html;

  // Initialize interactive map for each matched location with GPS
  d.results.forEach((r, i) => {
    if (r.match && r.match.location.latitude != null && r.match.location.longitude != null) {
      initResultMap(i, r.match.location);
    }
  });
}

function initResultMap(idx, loc) {
  const mapId = 'resultMap' + idx;
  const container = document.getElementById(mapId);
  if (!container || typeof L === 'undefined') return;

  const lat = loc.latitude, lng = loc.longitude;
  const rMap = L.map(mapId).setView([lat, lng], 17);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; OpenStreetMap'
  }).addTo(rMap);

  const marker = L.marker([lat, lng]).addTo(rMap)
    .bindPopup(`<b>${esc(loc.name)}</b><br><small>Block ${esc(loc.block || '-')}</small><br>📍 ${lat.toFixed(5)}, ${lng.toFixed(5)}`)
    .openPopup();

  window['_resultMap' + idx] = { map: rMap, marker: marker, loc: loc, userMarker: null, routeLine: null };
  setTimeout(() => rMap.invalidateSize(), 300);
}

window.measureUserGps = function(idx, targetLat, targetLng) {
  const alertBox = $('#gpsAlert' + idx);
  if (alertBox) alertBox.innerHTML = '<div class="muted">🛰️ Querying live GPS satellites...</div>';
  
  getLiveGps(
    pos => {
      const dist = calcDistanceMeters(pos.lat, pos.lng, targetLat, targetLng);
      let distText = dist < 1000 ? `${dist} meters` : `${(dist / 1000).toFixed(2)} km`;
      if (alertBox) {
        alertBox.innerHTML = `<div class="gps-dist-alert">
          <span>📏 <b>Live GPS Distance:</b> You are approx <b>${distText}</b> away (GPS Accuracy: &plusmn;${pos.accuracy}m).</span>
        </div>`;
      }
      const rObj = window['_resultMap' + idx];
      if (rObj && rObj.map) {
        if (rObj.userMarker) rObj.map.removeLayer(rObj.userMarker);
        if (rObj.routeLine) rObj.map.removeLayer(rObj.routeLine);

        rObj.userMarker = L.marker([pos.lat, pos.lng], { icon: getUserIcon() }).addTo(rObj.map)
          .bindPopup(`<b>You are here</b><br>GPS Accuracy: &plusmn;${pos.accuracy}m`);
        
        // Dotted walking line from user to signboard
        rObj.routeLine = L.polyline([[pos.lat, pos.lng], [targetLat, targetLng]], {
          color: '#1a73e8',
          weight: 4,
          dashArray: '6, 8',
          opacity: 0.8
        }).addTo(rObj.map);

        rObj.map.fitBounds(L.latLngBounds([[pos.lat, pos.lng], [targetLat, targetLng]]), { padding: [40, 40] });
      }
    },
    err => {
      if (alertBox) alertBox.innerHTML = `<div class="err">${esc(err.message)}</div>`;
    }
  );
};

function pickDest(i) {
  const k = $('#dest' + i).value;
  $$('#dirs' + i + ' li').forEach(li => { 
    li.classList.toggle('pick', k !== '' && li.dataset.k === k); 
    li.style.display = (k === '' || li.dataset.k === k) ? '' : 'none'; 
  });

  // Highlight on map if destination has GPS
  const L_source = window['_dirs' + i];
  const rObj = window['_resultMap' + i];
  if (!rObj || !rObj.map || !L_source) return;

  if (k !== '' && L_source.directions[k]) {
    const destName = L_source.directions[k].destination;
    const destLoc = allCampusLocations.find(x => x.name.toLowerCase() === destName.toLowerCase());
    if (destLoc && destLoc.latitude != null && destLoc.longitude != null) {
      if (rObj.routeLine) rObj.map.removeLayer(rObj.routeLine);
      rObj.routeLine = L.polyline([
        [L_source.latitude, L_source.longitude],
        [destLoc.latitude, destLoc.longitude]
      ], {
        color: '#1f9d55',
        weight: 5,
        opacity: 0.9
      }).addTo(rObj.map);
      rObj.map.fitBounds(L.latLngBounds([
        [L_source.latitude, L_source.longitude],
        [destLoc.latitude, destLoc.longitude]
      ]), { padding: [40, 40] });
    }
  }
}

function speak(i) {
  const L = window['_dirs' + i]; const k = $('#dest' + i).value;
  const list = k === '' ? L.directions : [L.directions[k]];
  const text = `You are at ${L.name}. ` + list.map(x => `To reach ${x.destination}: ${x.instruction}`).join(' ');
  speechSynthesis.cancel(); speechSynthesis.speak(new SpeechSynthesisUtterance(text));
}

function prefill(text) {
  $$('.tab')[1].click();
  const f = $('#addForm'); 
  f.board_text.value = text.toUpperCase(); 
  f.name.value = text.replace(/\b\w/g, c => c.toUpperCase()).toLowerCase().replace(/\b\w/g, c => c.toUpperCase());
}

// ================= LOCATIONS & CAMPUS MAP =================
async function loadLocations() {
  allCampusLocations = await (await fetch('/api/locations')).json();
  
  // Render table with GPS coordinates
  $('#locTable tbody').innerHTML = allCampusLocations.map(r => {
    const gpsStr = (r.latitude != null && r.longitude != null) 
      ? `<span class="gps-chip">${r.latitude.toFixed(4)}, ${r.longitude.toFixed(4)}</span>` 
      : '<span class="muted">-</span>';
    return `<tr>
      <td>${esc(r.board_text)}</td>
      <td><b>${esc(r.name)}</b></td>
      <td>${esc(r.block || '-')}</td>
      <td>${esc(r.floor || '-')}</td>
      <td>${gpsStr}</td>
      <td><button class="btn small danger" onclick="delLoc(${r.id})">Delete</button></td>
    </tr>`;
  }).join('');

  initCampusMap();
}

function initCampusMap() {
  const container = document.getElementById('campusMap');
  if (!container || typeof L === 'undefined') return;

  const validLocations = allCampusLocations.filter(loc => loc.latitude != null && loc.longitude != null);
  const defaultCenter = validLocations.length ? [validLocations[0].latitude, validLocations[0].longitude] : [13.0112, 80.2351];

  if (!campusMap) {
    campusMap = L.map('campusMap').setView(defaultCenter, 16);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; OpenStreetMap'
    }).addTo(campusMap);

    // Clicking anywhere on the campus map auto-fills latitude and longitude in Add form
    campusMap.on('click', e => {
      const { lat, lng } = e.latlng;
      const latIn = $('#addLat'), lngIn = $('#addLng');
      if (latIn && lngIn) {
        latIn.value = lat.toFixed(6);
        lngIn.value = lng.toFixed(6);
        $('#addMsg').innerHTML = `<span style="color:var(--blue)">📍 Picked GPS coordinates from map: <b>${lat.toFixed(5)}, ${lng.toFixed(5)}</b></span>`;
      }
    });
  }

  // Clear existing markers
  campusMarkers.forEach(m => campusMap.removeLayer(m));
  campusMarkers = [];

  const bounds = [];
  validLocations.forEach(loc => {
    const pt = [loc.latitude, loc.longitude];
    bounds.push(pt);
    const m = L.marker(pt).addTo(campusMap)
      .bindPopup(`
        <div style="font-size:0.9rem">
          <b style="font-size:1rem;color:var(--navy)">${esc(loc.name)}</b><br>
          <b>Block:</b> ${esc(loc.block || '-')}, <b>Floor:</b> ${esc(loc.floor || '-')}<br>
          <b>Category:</b> ${esc(loc.category || '-')}<br>
          <b>Timings:</b> ${esc(loc.timings || '-')}<br>
          <div style="margin-top:6px">
            <span class="gps-chip">📍 ${loc.latitude.toFixed(5)}, ${loc.longitude.toFixed(5)}</span>
            <a href="https://www.google.com/maps/dir/?api=1&destination=${loc.latitude},${loc.longitude}" target="_blank" style="display:inline-block;margin-top:4px;color:var(--blue);font-weight:600">🧭 Navigate with Google Maps</a>
          </div>
        </div>
      `);
    campusMarkers.push(m);
  });

  if (bounds.length) {
    campusMap.fitBounds(bounds, { padding: [30, 30] });
  }
  setTimeout(() => campusMap.invalidateSize(), 300);
}

// Locate Me button in campus map
const locateMeBtn = $('#locateMeBtn');
let campusUserMarker = null;
if (locateMeBtn) {
  locateMeBtn.onclick = () => {
    const status = $('#gpsStatus');
    status.textContent = '🛰️ Querying your real-time GPS position...';
    getLiveGps(
      pos => {
        if (!campusMap) return;
        if (campusUserMarker) campusMap.removeLayer(campusUserMarker);

        campusUserMarker = L.marker([pos.lat, pos.lng], { icon: getUserIcon() }).addTo(campusMap)
          .bindPopup(`<b>You are here!</b><br>Accuracy: &plusmn;${pos.accuracy}m`).openPopup();

        // Find nearest campus location
        let nearest = null, minDist = Infinity;
        allCampusLocations.forEach(loc => {
          if (loc.latitude != null && loc.longitude != null) {
            const d = calcDistanceMeters(pos.lat, pos.lng, loc.latitude, loc.longitude);
            if (d < minDist) { minDist = d; nearest = loc; }
          }
        });

        if (nearest) {
          status.innerHTML = `📍 <b>Your GPS location locked!</b> Nearest building: <b>${esc(nearest.name)}</b> (~${minDist < 1000 ? minDist + 'm' : (minDist/1000).toFixed(2) + 'km'} away).`;
        } else {
          status.innerHTML = `📍 <b>Your GPS location locked!</b> (Lat: ${pos.lat.toFixed(5)}, Lng: ${pos.lng.toFixed(5)})`;
        }
        campusMap.setView([pos.lat, pos.lng], 17);
      },
      err => {
        status.innerHTML = `<span class="err">${esc(err.message)}</span>`;
      }
    );
  };
}

// "Use My Current GPS" in Add form
const pickCurrentGpsBtn = $('#pickCurrentGpsBtn');
if (pickCurrentGpsBtn) {
  pickCurrentGpsBtn.onclick = () => {
    $('#addMsg').textContent = 'Fetching current GPS...';
    getLiveGps(
      pos => {
        $('#addLat').value = pos.lat.toFixed(6);
        $('#addLng').value = pos.lng.toFixed(6);
        $('#addMsg').innerHTML = `📍 Current GPS filled: <b>${pos.lat.toFixed(5)}, ${pos.lng.toFixed(5)}</b> (&plusmn;${pos.accuracy}m)`;
      },
      err => {
        $('#addMsg').innerHTML = `<span class="err">${esc(err.message)}</span>`;
      }
    );
  };
}

async function delLoc(id) { 
  if (confirm('Delete this location?')) { 
    await fetch('/api/locations/' + id, { method: 'DELETE' }); 
    loadLocations(); 
  } 
}

$('#addForm').onsubmit = async e => {
  e.preventDefault();
  const data = Object.fromEntries(new FormData(e.target));
  const res = await fetch('/api/locations', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
  const j = await res.json();
  $('#addMsg').innerHTML = res.ok ? 'Saved. Scan the board again to see it recognized with GPS!' : `<span class="err">${esc(j.error)}</span>`;
  if (res.ok) { e.target.reset(); loadLocations(); }
};

// ================= HISTORY TAB =================
async function loadHistory() {
  const [h, s] = await Promise.all([fetch('/api/history').then(r => r.json()), fetch('/api/stats').then(r => r.json())]);
  const rate = s.total ? Math.round(100 * s.recognized / s.total) : 0;
  $('#statCards').innerHTML = `<div class="stat"><b>${s.total}</b><span>Total scans</span></div><div class="stat"><b>${rate}%</b><span>Recognized</span></div>
   <div class="stat"><b>${s.avg_seconds}s</b><span>Average time</span></div><div class="stat"><b>${s.top[0] ? esc(s.top[0].name) : '-'}</b><span>Most scanned</span></div>`;
  $('#histTable tbody').innerHTML = h.map(r => `<tr><td>${esc(r.created)}</td><td>${esc(r.read_text)}</td><td>${esc(r.location || 'Not matched')}</td><td>${r.confidence != null ? (r.confidence * 100).toFixed(0) + '%' : '-'}</td><td>${r.seconds}</td></tr>`).join('');
}

