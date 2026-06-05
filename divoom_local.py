"""
Divoom Times Frame — LOCAL HTTP API probing.

May 2026 discovery (via vsimanin/ha-divoom-timesframe):
The frame *does* expose a local HTTP API on `http://<ip>:9000/divoom_api`.
Our April scan missed it because the request shape is GET-with-JSON-body
to a sub-path — unusual enough to slip through naive port probes.

Known-working commands (from Vasily's HA integration):
    Channel/SetClockSelectId  GET  {ClockId}
    Channel/SetBrightness     GET  {Brightness}
    Channel/OnOffScreen       GET  {OnOff}
    Channel/GetOnOffScreen    GET  {}
    Channel/GetConfig         GET  {}        -> includes StartUpClockId
    Channel/GetClockInfo      GET  {}
    Channel/GetAmbientLight   GET  {}
    Device/SysReboot          GET  {}
    Danmaku/SendText          POST {Text, TextColor, DeviceId, UserId}

Goal of this script: see if the same local channel exposes a "bind FileId
to photo playlist" command — the gap our cloud-side reverse couldn't close.

CLI:
    python divoom_local.py info  --ip 192.168.x.x
    python divoom_local.py call  --ip 192.168.x.x Channel/GetConfig
    python divoom_local.py probe --ip 192.168.x.x <FileId>
"""

import argparse
import json
import sys

import requests

PORT = 9000
PATH = "/divoom_api"
TIMEOUT = 4


def url_for(ip):
    return f"http://{ip}:{PORT}{PATH}"


def call(ip, command, extra=None, method="GET"):
    """One request. Returns (status_code, parsed_json_or_text)."""
    payload = {"Command": command}
    if extra:
        payload.update(extra)
    try:
        r = requests.request(method, url_for(ip), json=payload, timeout=TIMEOUT)
        try:
            return r.status_code, r.json()
        except ValueError:
            return r.status_code, {"_text": r.text[:200]}
    except requests.exceptions.RequestException as e:
        return None, {"_error": str(e)}


def cmd_info(args):
    """Hit every known-good command, print state. Confirms frame is reachable."""
    known = [
        "Channel/GetConfig",
        "Channel/GetClockInfo",
        "Channel/GetOnOffScreen",
        "Channel/GetAmbientLight",
    ]
    print(f"Pinging {url_for(args.ip)} ...\n")
    for cmd in known:
        sc, body = call(args.ip, cmd)
        print(f"=== {cmd}  (HTTP {sc}) ===")
        print(json.dumps(body, indent=2, ensure_ascii=False))
        print()


def cmd_call(args):
    """Manually fire one command with optional JSON kwargs."""
    extra = json.loads(args.body) if args.body else None
    sc, body = call(args.ip, args.command, extra, method=args.method)
    print(f"HTTP {sc}")
    print(json.dumps(body, indent=2, ensure_ascii=False))


def cmd_probe(args):
    """
    Brute-force search for a 'bind FileId to photo playlist' command on the
    LOCAL API. Tries every plausible group/verb with a real FileId payload.

    A 'hit' = anything that doesn't look like the unknown-command response.
    First we probe a deliberately-bogus command to learn the baseline reply.
    """
    file_id = args.file_id

    # Step 1 — discover the unknown-command signature for this firmware.
    print("Step 1: probing a deliberate bogus command to learn the 'unknown' reply ...")
    sc, baseline = call(args.ip, "Nonsense/DefinitelyNotReal")
    print(f"  HTTP {sc}, body: {json.dumps(baseline, ensure_ascii=False)[:200]}")
    print()

    # Heuristic: if baseline has a recognizable error_code/message, treat that
    # signature as "miss". Otherwise treat empty / nonexistent endpoint as miss.
    miss_signature = None
    if isinstance(baseline, dict):
        for key in ("error_code", "ErrorCode", "ReturnCode"):
            if key in baseline:
                miss_signature = (key, baseline[key])
                break

    print(f"Step 2: brute-forcing photo-bind verbs (miss signature: {miss_signature})\n")

    groups = [
        "Channel", "Device", "Photo", "PhotoFrame", "Picture", "Image",
        "File", "Cloud", "Slideshow", "Gallery",
    ]
    verbs = [
        # add / push family
        "AddPhoto", "AddPic", "AddImage", "AddFile",
        "PushPhoto", "PushPic", "PushImage", "PushFile",
        "InsertPhoto", "InsertPic", "InsertImage", "InsertFile",
        # set family
        "SetPhoto", "SetPic", "SetImage", "SetFile",
        "SetCustomPageIndex", "SetPhotoPlay", "SetPlayFile",
        # play / show family
        "PlayPhoto", "PlayPic", "PlayImage", "PlayFile",
        "ShowPhoto", "ShowPic", "ShowImage", "ShowFile",
        # bind / sync / update
        "BindPhoto", "BindFile", "SyncPhoto", "SyncFile",
        "UpdatePhoto", "UpdateFile", "UpdateList", "UpdatePlayList",
        # generic
        "Add", "Set", "Push", "Play", "Show", "Bind", "Sync", "Update",
        # custom-mode hints from Vasily's notes
        "EnterCustomControlMode", "SetCustomPage", "ShowCustomPage",
    ]

    # Field set covers what the cloud probe used + extras the local API might want.
    payload_extra = {
        "FileId": file_id,
        "PicId": file_id,
        "ImageId": file_id,
        "BigImageId": file_id,
        "SmallImageId": file_id,
        "PhotoName": "ProbeAttach",
        "FileName": "probe.jpg",
        "PixelStartX": "120",
        "PixelStartY": "115",
        "Index": 0,
    }

    hits = []
    total = len(groups) * len(verbs)
    print(f"Total probes: {total}\n")

    for g in groups:
        for v in verbs:
            cmd = f"{g}/{v}"
            sc, body = call(args.ip, cmd, payload_extra)

            # Skip clear misses
            if sc is None:
                continue
            if isinstance(body, dict) and miss_signature:
                key, val = miss_signature
                if body.get(key) == val:
                    continue

            # Anything else is interesting enough to report
            mark = "[!]" if isinstance(body, dict) and not body.get("_error") else "[?]"
            preview = json.dumps(body, ensure_ascii=False)[:160]
            print(f"  {mark} {cmd:40} HTTP {sc}  {preview}")
            hits.append((cmd, sc, body))

    print(f"\nProbed {total} commands. Interesting: {len(hits)}")
    if not hits:
        print("Local API gave no candidate. Next step: ADB into the device "
              "(root / Divoom~!@#) and read the app binary.")


def main():
    p = argparse.ArgumentParser(description="Divoom Times Frame local API probe")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("info", help="Hit known-good commands, print state")
    s.add_argument("--ip", required=True)
    s.set_defaults(func=cmd_info)

    s = sub.add_parser("call", help="Fire one command manually")
    s.add_argument("--ip", required=True)
    s.add_argument("command", help="e.g. Channel/GetConfig")
    s.add_argument("--body", help='Extra JSON payload, e.g. \'{"ClockId": 123}\'')
    s.add_argument("--method", default="GET", choices=["GET", "POST"])
    s.set_defaults(func=cmd_call)

    s = sub.add_parser("probe", help="Brute-force 'bind photo' command names")
    s.add_argument("--ip", required=True)
    s.add_argument("file_id", help="A real FileId from `divoom_cloud.py upload`")
    s.set_defaults(func=cmd_probe)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
