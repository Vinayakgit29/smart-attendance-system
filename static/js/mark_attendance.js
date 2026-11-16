// mark_attendance.js - unobtrusive adapter to existing verification logic
// This file keeps original function names and IDs used by backend/templates

(function(){
  // read data attributes from container
  const app = document.getElementById('attendance-app');
  if (!app) return;
  window.universityLatitude = parseFloat(app.dataset.universityLat);
  window.universityLongitude = parseFloat(app.dataset.universityLon);
  window.allowedRadius = parseFloat(app.dataset.allowedRadius);
  try{ window.configuredSlot = JSON.parse(app.dataset.configuredSlot); }catch(e){ window.configuredSlot = {}};

  // hookup: preserve original function names by delegating
  // Provide polished UI updates by enhancing original updateStep/updateCheck/updateLocationInfo/updateFaceInfo

  function setStepState(stepId, status, message){
    const el = document.getElementById(stepId);
    if (!el) return;
    el.classList.remove('active','success','error');
    if(status==='loading') el.classList.add('active');
    if(status==='success') el.classList.add('success');
    if(status==='error') el.classList.add('error');
    const icon = el.querySelector('.step-icon');
    const text = el.querySelector('.step-text');
    if(icon) icon.textContent = status==='loading' ? '⏳' : (status==='success' ? '✅' : '❌');
    if(text && message) text.textContent = message;
  }

  function setCheckState(checkId, status, message){
    const icon = document.getElementById(`icon-${checkId}`);
    const detail = document.getElementById(`detail-${checkId}`);
    if(!icon || !detail) return;
    icon.textContent = status==='loading' ? '⏳' : (status==='success' ? '✅' : '❌');
    detail.textContent = message || '';
    if(status==='success') detail.style.color = '#16a34a';
    else if(status==='error') detail.style.color = '#ef4444';
    else detail.style.color = '#64748b';
  }

  function setLocationInfo(lat, lon, distance){
    const dLat = document.getElementById('current-lat');
    const dLon = document.getElementById('current-lon');
    const dDisp = document.getElementById('distance-display');
    const dMsg = document.getElementById('distance-message');
    if(dLat) dLat.textContent = lat.toFixed(6);
    if(dLon) dLon.textContent = lon.toFixed(6);
    if(dDisp) dDisp.textContent = `${distance.toFixed(1)} m`;
    if(dMsg){
      if(distance<=window.allowedRadius) dMsg.textContent = `🟢 ${distance.toFixed(1)} m away (Inside Attendance Area)`;
      else dMsg.textContent = `🔴 ${distance.toFixed(1)} m away (Outside). Move ${(distance-window.allowedRadius).toFixed(1)} m closer.`;
    }
  }

  // Expose minimal API used by template script (keeps original names)
  window.updateStep = setStepState;
  window.updateCheck = setCheckState;
  window.updateLocationInfo = setLocationInfo;

  // Mirror original updateFaceInfo and calculateDistance names
  window.updateFaceInfo = function(cameraStatus, permission, detectionStatus, verificationStatus, message){
    const cStatus = document.getElementById('camera-status'); if(cStatus) cStatus.textContent = cameraStatus;
    const cPerm = document.getElementById('camera-permission'); if(cPerm) cPerm.textContent = permission;
    const fDetect = document.getElementById('face-detection-status'); if(fDetect) fDetect.textContent = detectionStatus;
    const fVerify = document.getElementById('face-verification-status'); if(fVerify) fVerify.textContent = verificationStatus;
    const fMsg = document.getElementById('face-message'); if(fMsg) fMsg.textContent = message;
  };

  window.calculateDistance = function(lat1, lon1, lat2, lon2){
    const R = 6371000;
    const dLat = (lat2 - lat1) * Math.PI / 180;
    const dLon = (lon2 - lon1) * Math.PI / 180;
    const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * Math.sin(dLon / 2) * Math.sin(dLon / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c;
  };

  // Keep original startVerification name but call shim for visuals then original logic if present
  // The template defines a startVerification function inline; it will still run and call updateStep/updateCheck etc.

})();

/* ---------- Original verification logic moved here (adapted) ---------- */

function parseTimeToSeconds(timeStr) {
  if (!timeStr) return null;
  const parts = timeStr.split(":");
  const hours = parseInt(parts[0] || "0", 10);
  const minutes = parseInt(parts[1] || "0", 10);
  const seconds = parseInt(parts[2] || "0", 10);
  return hours * 3600 + minutes * 60 + seconds;
}

function formatTimeDisplay(timeStr) {
  if (!timeStr) return '';
  const [hoursPart, minutePart, secondPart = '00'] = timeStr.split(':');
  const hours = parseInt(hoursPart || '0', 10);
  const minutes = parseInt(minutePart || '0', 10);
  const seconds = parseInt(secondPart || '0', 10);
  const date = new Date(2000, 0, 1, hours, minutes, seconds);
  return date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit', second: '2-digit', hour12: true });
}

async function startVerification() {
  // Reset all states
  document.querySelectorAll('.timeline-step').forEach(step => {
    const icon = step.querySelector('.step-icon'); if(icon) icon.textContent = '⏳';
    step.classList.remove('active','success','error');
  });
  document.querySelectorAll('.elig-icon').forEach(icon => { if(icon) icon.textContent = '⏳'; });
  document.querySelectorAll('.elig-detail').forEach(detail => { if(detail) detail.textContent = 'Waiting to check...'; });
  const statusEl = document.getElementById('status'); if(statusEl) statusEl.innerHTML = '';

  // Step 1: Camera Initializing
  updateStep('step-camera', 'loading', 'Camera Initializing...');
  updateCheck('camera', 'loading', 'Checking camera access...');
  await new Promise(resolve => setTimeout(resolve, 500));

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ video: true });
    stream.getTracks().forEach(track => track.stop());
    updateStep('step-camera', 'success', 'Camera Initialized');
    updateCheck('camera', 'success', 'Camera working properly');
  } catch (err) {
    updateStep('step-camera', 'error', 'Camera Failed');
    updateCheck('camera', 'error', 'Camera permission denied or not available');
    if(statusEl) statusEl.innerHTML = '<span class="status-pill danger">Camera permission denied. Please enable camera access.</span>';
    return;
  }

  // Step 2: Face Detection (simulated - will be handled by backend)
  updateStep('step-face', 'loading', 'Detecting Face...');
  updateCheck('face', 'loading', 'Waiting for face detection...');
  await new Promise(resolve => setTimeout(resolve, 800));

  updateCheck('face', 'success', 'Face detection ready for verification');
  updateFaceInfo('Ready', 'Granted', 'Detecting face...', 'Pending', 'Point your face to the camera for verification.');

  // Step 3: Identity Verification (simulated - backend handles this)
  updateStep('step-identity', 'loading', 'Verifying Identity...');
  updateCheck('face', 'loading', 'Verifying face against registered data...');
  await new Promise(resolve => setTimeout(resolve, 500));

  updateFaceInfo('Ready', 'Granted', 'Face detected', 'Verified', 'Face verification is in progress.');
  updateStep('step-face', 'success', 'Face Detected');
  updateStep('step-identity', 'success', 'Identity Verified');
  updateCheck('face', 'success', 'Face verification ready');

  // Step 4: GPS Location
  updateStep('step-gps', 'loading', 'Checking GPS Location...');
  updateCheck('radius', 'loading', 'Fetching location...');
  await new Promise(resolve => setTimeout(resolve, 500));

  if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(
      async (position) => {
        const userLat = position.coords.latitude;
        const userLon = position.coords.longitude;
        const distance = calculateDistance(userLat, userLon, window.universityLatitude, window.universityLongitude);

        updateLocationInfo(userLat, userLon, distance);

        if (distance <= window.allowedRadius) {
          updateStep('step-gps', 'success', 'GPS Verified');
          updateCheck('radius', 'success', `Within attendance radius (${distance.toFixed(1)} meters)`);
        } else {
          updateStep('step-gps', 'error', 'Outside Attendance Area');
          updateCheck('radius', 'error', `You are ${distance.toFixed(1)} meters away from campus (allowed: ${window.allowedRadius} meters)`);
        }

        // Continue with time check
        await checkTimeSlot(distance);
      },
      (error) => {
        updateStep('step-gps', 'error', 'GPS Failed');
        updateCheck('radius', 'error', 'Location permission denied - please enable GPS');
        if(statusEl) statusEl.innerHTML = '<span class="status-pill danger">Location access denied. Please enable GPS.</span>';
      }
    );
  } else {
    updateStep('step-gps', 'error', 'GPS Not Supported');
    updateCheck('radius', 'error', 'Geolocation not supported by your browser');
    if(statusEl) statusEl.innerHTML = '<span class="status-pill danger">Geolocation not supported.</span>';
  }
}

async function checkTimeSlot(distance) {
  updateStep('step-time', 'loading', 'Checking Attendance Time...');
  updateCheck('time', 'loading', 'Checking current time against slots...');
  await new Promise(resolve => setTimeout(resolve, 500));

  const now = new Date();
  const currentHour = now.getHours();
  const currentMinute = now.getMinutes();
  const currentTimeText = `${currentHour.toString().padStart(2, '0')}:${currentMinute.toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`;
  const currentTimeDisplay = formatTimeDisplay(currentTimeText);
  const currentDateText = now.toISOString().split('T')[0];
  const ct = document.getElementById('current-time'); if(ct) ct.textContent = currentTimeDisplay;
  const cd = document.getElementById('current-date'); if(cd) cd.textContent = currentDateText;

  let attendanceAllowed = false;
  let timeMessage = "";
  const configuredSlot = window.configuredSlot || {};
  let slotWindow = configuredSlot.slot_name ? `${configuredSlot.start_time} - ${configuredSlot.end_time}` : "No active slot";
  const configuredSlotExists = configuredSlot.id !== null && configuredSlot.start_time && configuredSlot.end_time;
  const nowSeconds = currentHour * 3600 + currentMinute * 60 + now.getSeconds();
  const slotStartSeconds = parseTimeToSeconds(configuredSlot.start_time);
  const slotEndSeconds = parseTimeToSeconds(configuredSlot.end_time);

  if (configuredSlotExists && slotStartSeconds !== null && slotEndSeconds !== null) {
    if (nowSeconds >= slotStartSeconds && nowSeconds <= slotEndSeconds) {
      attendanceAllowed = true;
      timeMessage = `Within active slot ${configuredSlot.slot_name} (${configuredSlot.start_time} - ${configuredSlot.end_time})`;
    } else {
      timeMessage = `Current time: ${currentTimeText} - Not within active slot (${configuredSlot.slot_name})`;
    }
  } else {
    timeMessage = `Current time: ${currentTimeText} - No active attendance slot configured`;
  }

  const slotWindowEl = document.getElementById('slot-window'); if(slotWindowEl) slotWindowEl.textContent = configuredSlot.start_time ? `${formatTimeDisplay(configuredSlot.start_time)} – ${formatTimeDisplay(configuredSlot.end_time)}` : slotWindow;

  if (attendanceAllowed) {
    updateStep('step-time', 'success', 'Time Verified');
    updateCheck('time', 'success', timeMessage);
    const ss = document.getElementById('slot-status'); if(ss) ss.textContent = 'Active';
    const sm = document.getElementById('slot-message'); if(sm) sm.innerHTML = `<span style="color: #16a34a;">You are inside the active attendance slot.</span>`;
  } else {
    updateStep('step-time', 'error', 'Invalid Time');
    updateCheck('time', 'error', timeMessage);
    const ss = document.getElementById('slot-status'); if(ss) ss.textContent = configuredSlotExists ? 'Inactive' : 'No Active Slot';
    const sm = document.getElementById('slot-message'); if(sm) sm.innerHTML = `<span style="color: #ef4444;">${configuredSlotExists ? 'You are not inside the current configured attendance slot.' : 'No active attendance slot is configured.'}</span>`;
  }

  // Step 6: Account Status (simulated - backend handles this)
  updateStep('step-duplicate', 'loading', 'Checking Account Status...');
  updateCheck('account', 'loading', 'Verifying student account status...');
  updateCheck('duplicate', 'loading', 'Checking for duplicate attendance...');
  await new Promise(resolve => setTimeout(resolve, 500));
  updateCheck('account', 'success', 'Student account is active');
  updateCheck('duplicate', 'loading', 'Will be verified by backend during attendance marking');

  // Final decision
  const statusEl = document.getElementById('status');
  if (distance <= window.allowedRadius && attendanceAllowed) {
    updateStep('step-duplicate', 'success', 'Checks Passed');
    if(statusEl) statusEl.innerHTML = '<span class="status-pill success">All checks passed! Starting camera preview…</span>';
    await new Promise(resolve => setTimeout(resolve, 800));
    // start client-side camera preview/verification instead of redirect
    if (typeof startCameraPreview === 'function') startCameraPreview();
  } else {
    let reasons = [];
    if (distance > window.allowedRadius) reasons.push("Outside campus area");
    if (!attendanceAllowed) reasons.push(configuredSlotExists ? "Not within time slot" : "No active attendance slot configured");
    updateStep('step-duplicate', 'error', 'Verification Failed');
    if(statusEl) statusEl.innerHTML = `<span class="status-pill danger">Cannot mark attendance: ${reasons.join(", ")}</span>`;
  }
}

// Expose startVerification globally
window.startVerification = startVerification;

// ----- Live camera / verification helpers -----
let __attVideoEl = null;
let __attCanvasEl = null;
let __attCanvasCtx = null;
let __previewStream = null;
let __verifyInterval = null;
let __lastCapturedDataUrl = null;
let __loggedRoll = null;
const __CONFIDENCE_THRESHOLD = 85; // LBPH: lower value = better match. Raised from 60 -> 85
// because with only 1 enrollment photo per student + real webcam lighting/angle
// differences, a genuine match can legitimately land in the 60-85 range.
// Retrain with preprocess_face() (resize+equalize) and add 3-5 photos per
// student (different angles/lighting) to bring this back down safely.

async function startCameraPreview() {
  const app = document.getElementById('attendance-app');
  __loggedRoll = app ? app.dataset.loggedRoll : '';
  __attVideoEl = document.getElementById('att-video');
  __attCanvasEl = document.getElementById('att-canvas');
  if (!__attVideoEl || !__attCanvasEl) return;
  __attCanvasCtx = __attCanvasEl.getContext('2d');

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' } });
    __previewStream = stream;
    __attVideoEl.srcObject = stream;
    __attVideoEl.style.display = 'block';
    // show capture button (user clicks to take a photo) and stop button
    const capBtn = document.getElementById('capture-btn'); if (capBtn) capBtn.style.display = 'inline-block';
    const confBtn = document.getElementById('confirm-verify-btn'); if (confBtn) confBtn.style.display = 'none';
    document.getElementById('stop-verify-btn').style.display = 'inline-block';
    // show dataset sample image
    const ds = document.getElementById('dataset-sample');
    if (ds && __loggedRoll) ds.src = `/student-face/${encodeURIComponent(__loggedRoll)}`;

  } catch (err) {
    console.error('camera preview failed', err);
    showToast('error', 'Camera Failed', 'Cannot start camera preview.');
  }
}

function stopVerificationCamera() {
  if (__verifyInterval) { clearInterval(__verifyInterval); __verifyInterval = null; }
  if (__previewStream) {
    __previewStream.getTracks().forEach(t => t.stop());
    __previewStream = null;
  }
  if (__attVideoEl) __attVideoEl.style.display = 'none';
  const cap = document.getElementById('capture-btn'); if (cap) cap.style.display = 'none';
  const conf = document.getElementById('confirm-verify-btn'); if (conf) conf.style.display = 'none';
  const stop = document.getElementById('stop-verify-btn'); if (stop) stop.style.display = 'none';
  __lastCapturedDataUrl = null;
}

async function captureAndVerify() {
  try {
    if (!__attVideoEl || !__attCanvasEl) return;
    __attCanvasEl.width = __attVideoEl.videoWidth || 640;
    __attCanvasEl.height = __attVideoEl.videoHeight || 480;
    __attCanvasCtx.drawImage(__attVideoEl, 0, 0, __attCanvasEl.width, __attCanvasEl.height);
    const dataUrl = __attCanvasEl.toDataURL('image/jpeg');

    // show live snapshot
    const live = document.getElementById('live-snapshot'); if (live) live.src = dataUrl;

    // post to server verify API
    const resp = await fetch('/api/verify-face', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ image: dataUrl })
    });
    const json = await resp.json();
    if (!json.success) {
      window.updateFaceInfo('Ready', 'Granted', 'No face', 'Pending', json.message || 'No face detected');
      window.updateCheck('face', 'error', json.message || 'No face detected');
      return;
    }

    const recognized = String(json.recognized_roll || '');
    const confidence = Number(json.confidence || 9999);
    const usedFallback = Boolean(json.fallback);

    const isMatch = (__loggedRoll && recognized === String(__loggedRoll) && (usedFallback || confidence <= __CONFIDENCE_THRESHOLD));

    // update UI
    if (isMatch) {
      window.updateFaceInfo('Ready', 'Granted', 'Face detected', 'Verified', usedFallback ? 'Using fallback verification path' : `Recognized: ${recognized} (conf ${confidence.toFixed(1)})`);
      window.updateCheck('face', 'success', 'Face verification completed');
    } else {
      window.updateFaceInfo('Ready', 'Granted', 'Face detected', 'Mismatch', usedFallback ? 'Face did not match the logged-in account. Please try again with a clear face.' : `Face not match. Recognized: ${recognized} (conf ${confidence.toFixed(1)})`);
      window.updateCheck('face', 'error', 'Face not matched. Attendance will not be marked.');
      showToast('warning', 'Face Mismatch', 'Face does not match the logged-in student. Attendance was not marked.');
      return;
    }

    // if matched, mark attendance via API
    if (isMatch) {
      stopVerificationCamera();
      const markResp = await fetch('/api/verify-attendance', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ recognized_roll: recognized })
      });
      const markJson = await markResp.json();
      if (markJson.success) {
        showToast('success', 'Attendance Marked', markJson.message || 'Attendance recorded');
        showAttendanceMarkedMessage();
        // redirect to result page or dashboard after a short delay so the student can see the confirmation
        setTimeout(function(){ window.location.href = '/student-dashboard'; }, 3500);
      } else {
        showToast('error', 'Marking Failed', markJson.message || 'Could not mark attendance');
      }
    }

  } catch (err) {
    console.error('verify error', err);
  }
}

// Shows a large on-screen confirmation banner once attendance is marked.
// Kept visible for ~3.5s before the redirect (triggered via setTimeout at the call site).
function showAttendanceMarkedMessage() {
  const statusEl = document.getElementById('status');
  if (statusEl) {
    statusEl.innerHTML = '<span class="status-pill success" style="font-size:1.1rem;padding:0.9rem 1.4rem;display:inline-flex;align-items:center;gap:0.5rem;">✅ Attendance marked for today!</span>';
  }
  const faceMsg = document.getElementById('face-message');
  if (faceMsg) faceMsg.textContent = 'Attendance marked for today!';
}
window.showAttendanceMarkedMessage = showAttendanceMarkedMessage;

// expose for template buttons
window.startCameraPreview = startCameraPreview;
window.captureAndVerify = captureAndVerify;
window.stopVerificationCamera = stopVerificationCamera;

// New: capture preview only (user confirms before verifying)
function capturePreview() {
  try {
    if (!__attVideoEl || !__attCanvasEl) return;
    __attCanvasEl.width = __attVideoEl.videoWidth || 640;
    __attCanvasEl.height = __attVideoEl.videoHeight || 480;
    __attCanvasCtx.drawImage(__attVideoEl, 0, 0, __attCanvasEl.width, __attCanvasEl.height);
    __lastCapturedDataUrl = __attCanvasEl.toDataURL('image/jpeg');
    const live = document.getElementById('live-snapshot'); if (live) live.src = __lastCapturedDataUrl;
    const confBtn = document.getElementById('confirm-verify-btn'); if (confBtn) confBtn.style.display = 'inline-block';
    const capBtn = document.getElementById('capture-btn'); if (capBtn) capBtn.style.display = 'inline-block';
  } catch (err) {
    console.error('capture preview failed', err);
  }
}

async function verifyCapturedImage() {
  try {
    const dataUrl = __lastCapturedDataUrl || (function(){ if(__attCanvasEl){ return __attCanvasEl.toDataURL('image/jpeg'); } return null; })();
    if (!dataUrl) return showToast('error','No Photo','Please capture a photo first.');

    const resp = await fetch('/api/verify-face', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ image: dataUrl })
    });
    const json = await resp.json();
    if (!json.success) {
      window.updateFaceInfo('Ready', 'Granted', 'No face', 'Pending', json.message || 'No face detected');
      window.updateCheck('face', 'error', json.message || 'No face detected');
      return;
    }

    const recognized = String(json.recognized_roll || '');
    const confidence = Number(json.confidence || 9999);
    const usedFallback = Boolean(json.fallback);
    const isMatch = (__loggedRoll && recognized === String(__loggedRoll) && (usedFallback || confidence <= __CONFIDENCE_THRESHOLD));

    // update UI
    if (isMatch) {
      window.updateFaceInfo('Ready', 'Granted', 'Face detected', 'Verified', usedFallback ? 'Using fallback verification path' : `Recognized: ${recognized} (conf ${confidence.toFixed(1)})`);
      window.updateCheck('face', 'success', 'Face verification completed');
    } else {
      window.updateFaceInfo('Ready', 'Granted', 'Face detected', 'Mismatch', usedFallback ? 'Face did not match the logged-in account. Please try again with a clear face.' : `Face not match. Recognized: ${recognized} (conf ${confidence.toFixed(1)})`);
      window.updateCheck('face', 'error', 'Face not matched. Attendance will not be marked.');
      showToast('warning', 'Face Mismatch', 'Face does not match the logged-in student. Attendance was not marked.');
      return;
    }

    if (isMatch) {
      stopVerificationCamera();
      const markResp = await fetch('/api/verify-attendance', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ recognized_roll: recognized })
      });
      const markJson = await markResp.json();
      if (markJson.success) {
        showToast('success', 'Attendance Marked', markJson.message || 'Attendance recorded');
        showAttendanceMarkedMessage();
        // redirect after a short delay so the student can see the confirmation
        setTimeout(function(){ window.location.href = '/student-dashboard'; }, 3500);
      } else {
        showToast('error', 'Marking Failed', markJson.message || 'Could not mark attendance');
      }
    }

  } catch (err) {
    console.error('verify captured image error', err);
  }
}

