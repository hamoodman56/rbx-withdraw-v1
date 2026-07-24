import os
from flask import Flask, jsonify, request
import requests

app = Flask(__name__)

# Configuration loaded from Render Environment Variables
BOT_COOKIE = os.environ.get("BOT_COOKIE", "").strip()
PROXY_IP = os.environ.get("PROXY_IP", "")
PROXY_PORT = os.environ.get("PROXY_PORT", "")
PROXY_USER = os.environ.get("PROXY_USER", "")
PROXY_PASS = os.environ.get("PROXY_PASS", "")

proxies = {
    "http": f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_IP}:{PROXY_PORT}",
    "https": f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_IP}:{PROXY_PORT}",
}

# Standard Desktop Chrome Browser Headers
DESKTOP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.roblox.com/",
    "Origin": "https://www.roblox.com",
    "Content-Type": "application/json",
    "Cookie": f".ROBLOSECURITY={BOT_COOKIE}",
}


@app.route("/purchase", methods=["POST"])
def handle_purchase():
  try:
    body = request.json
    user_id = body.get("userId")
    amount = body.get("amount")

    if not user_id or not amount:
      return jsonify({"error": "Missing required fields."}), 400

    target_price = int(amount)

    # 1. Fetch CSRF Token via Webshare Proxy using Desktop Headers
    csrf_res = requests.post(
        "https://auth.roblox.com/v2/logout",
        headers=DESKTOP_HEADERS,
        proxies=proxies,
        timeout=15,
    )
    csrf_token = csrf_res.headers.get("x-csrf-token")

    if not csrf_token:
      return (
          jsonify({
              "error": "Failed to get CSRF token through proxy.",
              "details": csrf_res.text,
          }),
          401,
      )

    auth_headers = {**DESKTOP_HEADERS, "X-CSRF-TOKEN": csrf_token}

    # 2. Scan Gamepasses
    scan_url = (
        f"https://apis.roblox.com/game-passes/v1/users/{user_id}/game-passes?count=100"
    )
    scan_res = requests.get(
        scan_url, headers=auth_headers, proxies=proxies, timeout=15
    )

    if not scan_res.ok:
      return (
          jsonify(
              {"error": "Failed to scan gamepasses.", "details": scan_res.text}
          ),
          400,
      )

    scan_data = scan_res.json()
    passes_array = scan_data.get("gamePasses") or scan_data.get("data") or scan_data

    target_pass = next(
        (
            p
            for p in passes_array
            if p.get("price") == target_price and p.get("isForSale") is True
        ),
        None,
    )

    if not target_pass:
      return (
          jsonify({
              "error": "No matching gamepass found for sale.",
              "details": passes_array,
          }),
          404,
      )

    gamepass_id = target_pass.get("id") or target_pass.get("gamePassId")

    # 3. Execute Purchase via Webshare Proxy using Desktop Headers
    purchase_url = f"https://apis.roblox.com/game-passes/v1/game-passes/{gamepass_id}/purchase"
    purchase_res = requests.post(
        purchase_url,
        headers=auth_headers,
        json={"expectedPrice": target_price},
        proxies=proxies,
        timeout=15,
    )

    purchase_data = purchase_res.json()

    if not purchase_res.ok or purchase_data.get("purchased") is not True:
      return (
          jsonify({
              "success": False,
              "error": "Roblox rejected the desktop transaction.",
              "status": purchase_res.status_code,
              "details": purchase_data,
          }),
          400,
      )

    return (
        jsonify({
            "success": True,
            "message": (
                "Gamepass purchased via Webshare proxy with desktop headers!"
            ),
            "data": purchase_data,
        }),
        200,
    )

  except Exception as e:
    return jsonify({"error": "Internal Python Error", "details": str(e)}), 500


if __name__ == "__main__":
  app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
