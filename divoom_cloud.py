"""
Divoom Times Frame — cloud API toolkit (partial reverse).

Status: ~80% reversed. Login + device info + photo list + file upload to CDN
all work via documented HTTP. The final step — telling the device "display this
new file" — is still missing; it almost certainly travels over the RongCloud
MQTT channel that the official mobile app keeps open. See README.md.

Endpoints discovered (all on https://appin.divoom-gz.com unless noted):
    POST /UserLogin                  — auth, returns Token + UserId
    POST /User/GetUserInfo           — confirms account + DeviceId
    POST /PhotoFrame/GetList         — current photos on the frame
    POST /Cloud/GetFileData          — fetch arbitrary file by FileId
    POST /upload.php on f.divoom-gz.com  — multipart upload, field name "upFile"

Endpoints that look real but reject calls (likely RongCloud-only):
    POST /PhotoFrame/UploadFile      — "Call to protected method ApiBase::UploadFile"

CLI:
    python divoom_cloud.py login            # uses DIVOOM_PASSWORD env or asks
    python divoom_cloud.py info             # whoami + DeviceId
    python divoom_cloud.py list             # photos currently on the frame
    python divoom_cloud.py upload <path>    # uploads jpg/png to CDN, prints FileId
    python divoom_cloud.py probe-attach <BigImageId> [<SmallImageId>]
                                            # tries every plausible "add to frame"
                                            # endpoint name. Currently finds nothing.
"""

import argparse
import getpass
import hashlib
import io
import json
import os
import sys
from pathlib import Path

import requests

API = "https://appin.divoom-gz.com"
CDN = "https://f.divoom-gz.com"
TOKEN_FILE = Path(__file__).parent / ".divoom_token"

DEFAULT_EMAIL = os.environ.get("DIVOOM_EMAIL", "")


def load_token():
    if not TOKEN_FILE.exists():
        sys.exit("No token. Run `login` first.")
    return json.loads(TOKEN_FILE.read_text())


def save_token(payload):
    TOKEN_FILE.write_text(json.dumps(payload))


def cmd_login(args):
    email = args.email or DEFAULT_EMAIL
    if not email:
        email = input("Email: ").strip()

    password = os.environ.get("DIVOOM_PASSWORD")
    if not password:
        password = getpass.getpass("Password (hidden): ")

    pwd_md5 = hashlib.md5(password.encode()).hexdigest()
    r = requests.post(
        f"{API}/UserLogin",
        json={"Email": email, "Password": pwd_md5},
        timeout=10,
    )
    data = r.json()
    if data.get("ReturnCode") != 0:
        sys.exit(f"Login failed: {data.get('ReturnMessage')}")

    save_token({
        "Token": data["Token"],
        "UserId": data["UserId"],
        "Email": email,
    })
    print(f"Logged in as {data.get('Nickname', email)} (UserId {data['UserId']})")
    print(f"Token saved to {TOKEN_FILE.name}")


def cmd_info(args):
    tok = load_token()
    r = requests.post(
        f"{API}/User/GetUserInfo",
        json={"Token": tok["Token"], "UserId": tok["UserId"]},
        timeout=10,
    )
    data = r.json()
    if data.get("ReturnCode") != 0:
        sys.exit(f"Error: {data.get('ReturnMessage')}")

    print(f"Nickname:  {data.get('Nickname')}")
    print(f"UserId:    {tok['UserId']}")
    print(f"DeviceId:  {data.get('DeviceId')}")
    print(f"Email:     {tok['Email']}")


def cmd_list(args):
    tok = load_token()
    info = requests.post(
        f"{API}/User/GetUserInfo",
        json={"Token": tok["Token"], "UserId": tok["UserId"]},
        timeout=10,
    ).json()
    device_id = info.get("DeviceId")
    if not device_id:
        sys.exit("No DeviceId on this account.")

    r = requests.post(
        f"{API}/PhotoFrame/GetList",
        json={
            "Token": tok["Token"],
            "UserId": tok["UserId"],
            "DeviceId": device_id,
            "PageIndex": 0,
        },
        timeout=10,
    )
    data = r.json()
    if data.get("ReturnCode") != 0:
        sys.exit(f"Error: {data.get('ReturnMessage')}")

    photos = data.get("PhotoList", [])
    print(f"DeviceId {device_id} — {len(photos)} photo(s):")
    for i, p in enumerate(photos):
        print(f"  [{i:2}] {p.get('PhotoName'):20}  Big={p.get('BigImageId')}")


def cmd_upload(args):
    path = Path(args.path)
    if not path.is_file():
        sys.exit(f"Not a file: {path}")

    files = {"upFile": (path.name, path.read_bytes(), "application/octet-stream")}
    r = requests.post(f"{CDN}/upload.php", files=files, timeout=60)
    data = r.json()
    if data.get("ReturnCode") != 0:
        sys.exit(f"Upload failed: {data.get('ReturnMessage')}")
    print(f"FileId: {data['FileId']}")


def cmd_probe_attach(args):
    """
    Walks every plausible endpoint name with a real FileId payload.
    Currently finds zero hits. Kept as a tool for future researchers —
    if Divoom ever exposes the bind-photo-to-frame method via HTTP,
    this script will find it on the next run.
    """
    tok = load_token()
    info = requests.post(
        f"{API}/User/GetUserInfo",
        json={"Token": tok["Token"], "UserId": tok["UserId"]},
        timeout=10,
    ).json()
    device_id = info.get("DeviceId")

    big_id = args.big_id
    small_id = args.small_id or args.big_id  # if no small, reuse big

    base = {"Token": tok["Token"], "UserId": tok["UserId"], "DeviceId": device_id}
    payload = {
        **base,
        "PhotoName": "ProbeAttach",
        "BigImageId": big_id,
        "SmallImageId": small_id,
        "PixelStartX": "120",
        "PixelStartY": "115",
    }

    groups = ["PhotoFrame", "Photoframe", "photoframe", "Device", "Channel", "Cloud", "Photo"]
    verbs = [
        "AddPhoto", "SavePhoto", "InsertPhoto", "SetPhoto", "PushPhoto",
        "SendPhoto", "CreatePhoto", "UploadPhoto", "PostPhoto", "UpdatePhoto",
        "Add", "Save", "Insert", "Set", "Push", "Send", "Create", "Upload",
        "AddPic", "SavePic", "SetPic", "AddImage", "SaveImage", "SendImage",
        "SetList", "SaveList", "UpdateList", "SyncList",
    ]

    hits = 0
    for g in groups:
        for v in verbs:
            ep = f"{g}/{v}"
            try:
                r = requests.post(f"{API}/{ep}", json=payload, timeout=4)
                d = r.json() if r.text.startswith("{") else {"_text": r.text[:80]}
                rc = d.get("ReturnCode", "?")
                if rc != 10:  # 10 = "Command is not match" (endpoint missing)
                    mark = "✅" if rc == 0 else "⚠️ "
                    print(f"  {mark} {ep:40} rc={rc} \"{d.get('ReturnMessage', '')}\"")
                    hits += 1
            except Exception:
                pass
    print(f"\nHits: {hits}")
    if hits == 0:
        print("Still no public attach endpoint. Try mitmproxy on the official app.")


def main():
    p = argparse.ArgumentParser(description="Divoom Times Frame cloud toolkit")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("login", help="Authenticate (uses DIVOOM_PASSWORD env if set)")
    s.add_argument("--email", help=f"override email (default: {DEFAULT_EMAIL or 'DIVOOM_EMAIL env or prompt'})")
    s.set_defaults(func=cmd_login)

    sub.add_parser("info", help="Show account + DeviceId").set_defaults(func=cmd_info)
    sub.add_parser("list", help="List photos on the frame").set_defaults(func=cmd_list)

    s = sub.add_parser("upload", help="Upload a file to Divoom CDN, get FileId")
    s.add_argument("path")
    s.set_defaults(func=cmd_upload)

    s = sub.add_parser("probe-attach", help="Brute-force search for the missing 'attach photo to frame' endpoint")
    s.add_argument("big_id")
    s.add_argument("small_id", nargs="?")
    s.set_defaults(func=cmd_probe_attach)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
