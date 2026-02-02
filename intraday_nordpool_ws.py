"""
Try connecting to Nordpool WebSocket endpoints instead of BRM
"""
import asyncio
import json
import ssl
import uuid
import requests
import websockets
from datetime import datetime

# BRM SSO (what works for auth)
SSO_URL = "https://sso.test.brm-power.ro/connect/token"
CLIENT_AUTH = "Basic Y2xpZW50X2ludHJhZGF5X2FwaToxeEI5SWsxeHNFdTJuYndWYTFCUg=="
USERNAME = "Test_IntradayAPI_ADREM"
PASSWORD = "nR(B8fDY{485Nq4mu"

# Different WebSocket hosts to try
WS_HOSTS = [
    # BRM endpoint (what we use)
    "wss://intraday-pmd-api-ws-brm.test.nordpoolgroup.com",
    # Nordpool endpoints (from their example)
    "wss://intraday-pmd-api-ws-nordpool.test.nordpoolgroup.com",
    "wss://intraday2-ws.test.nordpoolgroup.com",
]

def get_token():
    headers = {
        "Authorization": CLIENT_AUTH,
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "grant_type": "password",
        "username": USERNAME,
        "password": PASSWORD,
        "scope": "intraday_api"
    }
    response = requests.post(SSO_URL, headers=headers, data=data)
    if response.status_code == 200:
        return response.json().get("access_token")
    return None

def build_sockjs_url(host):
    server_id = str(hash(datetime.now().isoformat()) % 1000).zfill(3)
    session_id = uuid.uuid4().hex[:8]
    return f"{host}/user/{server_id}/{session_id}/websocket"

class STOMPFrame:
    def __init__(self, command, headers=None, body=""):
        self.command = command
        self.headers = headers or {}
        self.body = body

    def to_sockjs(self):
        frame_str = self.command + "\n"
        for key, value in self.headers.items():
            frame_str += f"{key}:{value}\n"
        frame_str += "\n" + self.body + "\u0000"
        return json.dumps([frame_str])

async def test_ws_host(host):
    print(f"\n{'='*60}")
    print(f"HOST: {host}")
    print('='*60)

    token = get_token()
    if not token:
        print("Failed to get token")
        return

    ws_url = build_sockjs_url(host)
    print(f"URL: {ws_url}")

    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    try:
        async with websockets.connect(
            ws_url,
            ssl=ssl_context,
            max_size=10 * 1024 * 1024,
            ping_interval=20,
            ping_timeout=10
        ) as ws:
            # SockJS open
            msg = await asyncio.wait_for(ws.recv(), timeout=10)
            if msg != 'o':
                print(f"SockJS Error: {msg}")
                return
            print("[OK] SockJS connected")

            # Extract hostname for STOMP
            hostname = host.replace("wss://", "").replace("ws://", "")

            # STOMP CONNECT
            connect_frame = STOMPFrame(
                "CONNECT",
                {
                    "accept-version": "1.2",
                    "host": hostname,
                    "X-AUTH-TOKEN": token,
                    "heart-beat": "10000,10000"
                }
            )
            await ws.send(connect_frame.to_sockjs())
            msg = await asyncio.wait_for(ws.recv(), timeout=10)

            if "CONNECTED" in msg:
                print("[OK] STOMP connected")
            elif "ERROR" in msg:
                print(f"[ERROR] STOMP: {msg[:200]}")
                return
            else:
                print(f"[?] Response: {msg[:200]}")
                return

            # Try configuration
            sub_id = str(uuid.uuid4())[:8]
            config_path = f"/user/{USERNAME}/v1/configuration"
            subscribe_frame = STOMPFrame(
                "SUBSCRIBE",
                {"id": sub_id, "destination": config_path}
            )
            await ws.send(subscribe_frame.to_sockjs())
            print(f"Subscribed to: {config_path}")

            try:
                while True:
                    msg = await asyncio.wait_for(ws.recv(), timeout=3)
                    if msg == 'h':
                        continue
                    if "ERROR" in msg:
                        if "Unable to match" in msg:
                            print("[RESULT] Configuration: NO ACCESS")
                        else:
                            # Extract error
                            print(f"[ERROR] {msg[:200]}")
                    elif "MESSAGE" in msg:
                        print(f"[RESULT] Configuration: GOT DATA ({len(msg)} bytes)")
                        # Try to show portfolio info
                        if "portfolio" in msg.lower():
                            print("  >>> Contains portfolio info! <<<")
                    break
            except asyncio.TimeoutError:
                print("[RESULT] Configuration: TIMEOUT")

            disconnect_frame = STOMPFrame("DISCONNECT", {"receipt": "disconnect-1"})
            await ws.send(disconnect_frame.to_sockjs())

    except websockets.exceptions.InvalidStatusCode as e:
        print(f"[ERROR] WebSocket rejected: {e}")
    except Exception as e:
        print(f"[ERROR] {type(e).__name__}: {e}")

async def main():
    print("TESTING DIFFERENT WEBSOCKET HOSTS")
    print("=" * 60)
    print(f"User: {USERNAME}")

    for host in WS_HOSTS:
        await test_ws_host(host)
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())
