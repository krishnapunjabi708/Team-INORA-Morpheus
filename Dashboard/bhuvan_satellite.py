import requests

# Your access token (treat this securely)
token = "14db7df704890c5a48ec40b4cf4e19ceb71e00ed"

# API endpoint (example for LULC Statistics — replace if you have another)
url = "https://bhuvan-isdsp.nrsc.gov.in/api/lulcStats"  # Confirm this from Bhuvan docs

# Request headers
headers = {
    "Content-Type": "application/json",
    "Authorization": token
}

# Sample payload — update this based on your needs
payload = {
    "state": "Maharashtra",
    "district": "Pune",
    "year": "2022"
}

# Send POST request
response = requests.post(url, headers=headers, json=payload)

# Output the result
if response.status_code == 200:
    print("✅ API call successful!")
    print("Response:")
    print(response.json())
else:
    print("❌ API call failed!")
    print("Status Code:", response.status_code)
    print("Message:", response.text)
