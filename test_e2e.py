import requests

BASE = 'http://127.0.0.1:5000'

session = requests.Session()

# Test student details
name = 'E2E Student'
roll_number = '9001'
aadhaar = '111122223333'
email = 'e2e_student@example.com'
password = 'E2Epass@1'

# tiny transparent PNG
captured_image = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAAWgmWQ0AAAAASUVORK5CYII='

# 1) Signup
print('Signing up...')
resp = session.post(f'{BASE}/signup', data={
    'name': name,
    'roll_number': roll_number,
    'aadhaar': aadhaar,
    'email': email,
    'password': password,
    'captured_image': captured_image,
})
print('Signup status:', resp.status_code)

# 2) Login
print('Logging in...')
resp = session.post(f'{BASE}/login', data={'email': email, 'password': password}, allow_redirects=True)
print('Login status:', resp.status_code)

# 3) Verify attendance via API
print('Marking attendance via API...')
resp = session.post(f'{BASE}/api/verify-attendance', json={'recognized_roll': roll_number})
print('API response code:', resp.status_code)
try:
    print('API response JSON:', resp.json())
except Exception:
    print('Non-JSON response:', resp.text[:500])

# 4) Fetch student dashboard
print('Fetching student dashboard...')
resp = session.get(f'{BASE}/student-dashboard')
print('Student dashboard status:', resp.status_code)
print('Dashboard snippet:')
print(resp.text[:400])
