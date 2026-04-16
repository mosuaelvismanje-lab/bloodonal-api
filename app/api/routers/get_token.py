import requests

# Your Project Data
API_KEY = "AIzaSyB5hs_wdcc7Z3HNpbiXTL-ilpAuThEjtB8"
EMAIL = "norbertmulango@gmail.com"
PASSWORD = "mulango"


def get_new_token():
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={API_KEY}"
    payload = {"email": EMAIL, "password": PASSWORD, "returnSecureToken": True}

    response = requests.post(url, json=payload)
    if response.status_code == 200:
        token = response.json().get("idToken")
        print("-" * 50)
        print("COPY EVERYTHING BELOW THIS LINE:")
        print("-" * 50)
        print(f"Bearer {token}")
        print("-" * 50)
    else:
        print(f"Error: {response.json()}")


if __name__ == "__main__":
    get_new_token()