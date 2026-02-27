import requests

url = "https://rituja04-farmmatrix-chatbot-api.hf.space/queue/join"  # try changing this if needed
headers = {
    "Content-Type": "application/json"
}
data = {
    "data": ["Hello"],  # replace with what your chatbot expects
    "event_data": None,
    "fn_index": 0        # update this if needed (check from network calls)
}

response = requests.post(url, json=data, headers=headers)
print(response.text)
