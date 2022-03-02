from http.server import BaseHTTPRequestHandler, HTTPServer
import webbrowser
from urllib.parse import quote_plus, urlencode
import json
import requests

LISTEN_PORT = 42246
CLIENT_ID = "bgm2195621e24d107557"
CLIENT_SECRET = "02c1429f8f299328dade092920a75f97"
CALLBACK_URL = f"http://localhost:{LISTEN_PORT}"

AUTH_URL = f"https://bgm.tv/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={quote_plus(CALLBACK_URL)}"
EXCHANGE_CODE_URL = "https://bgm.tv/oauth/access_token"

CODE = ""


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        global CODE

        self.send_response(200)
        self.send_header('Content-type','text/html')
        self.end_headers()

        code = self.path.split("=")[1]

        message = f"You can close this window now. <br> (debug) code={code}"
        self.wfile.write(bytes(message, "utf8"))

        CODE = code

def get_access_token():
    body = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": CODE,
        "redirect_uri": CALLBACK_URL
    }
    data = urlencode(body)
    header = {'Content-Type': 'application/x-www-form-urlencoded', 'User-Agent': 'bangumi-takeout-py'}
    response = requests.post(EXCHANGE_CODE_URL, data=data, headers=header)
    if response.status_code != 200:
        raise Exception(f"failed to get access token, status code={response.status_code}")
    with open(".bgm_token","w", encoding="u8") as f:
        json.dump(response.json(), f, ensure_ascii=False, indent=4)
    print("access token received. written to .bgm_token")

def do_auth():
    print("opening browser to authorize... please click 'allow' on next page")
    webbrowser.open(AUTH_URL)
    print("waiting for code...(check your browser)")
    with HTTPServer(('', LISTEN_PORT), handler) as server:
        server.handle_request()
    print("code received, starting to get access token...")
    get_access_token()

def main():
    do_auth()

if __name__ == "__main__":
    main()