# Divoom Times Frame — cloud API research (~80% reversed)

Notes from a one-evening attempt to push a custom dashboard image to a Divoom **Times Frame** (10.1″ Wi-Fi photo frame, 2024–25 model).

**Status:** got most of the cloud API working — login, account info, photo list, file upload to the CDN. The very last step — telling the frame "now display this freshly uploaded file" — is closed off in the public HTTP API and almost certainly travels over the **RongCloud MQTT** channel that the official mobile app keeps open. Without intercepting the app's traffic we can't see those messages.

If you finish the missing piece, please open a PR — this is exactly where someone with mitmproxy and an iPhone could close the loop in an hour.

> **Correction to the original "pure-cloud" claim:** the frame *does* expose a local LAN HTTP API on `:9000/divoom_api` — see [Local HTTP API on :9000](#local-http-api-on-9000-partial) below. It controls brightness / screen / built-in faces / danmaku, but **not** the photo-bind step, so it doesn't shorten the missing piece. Full session log: `HANDOFF.md`.

---

## What works ✅

| Step | Endpoint | Result |
|---|---|---|
| Login | `POST appin.divoom-gz.com/UserLogin` with `{Email, Password: md5(pwd)}` | Returns `Token` + `UserId` + `UserToken` (the latter contains a RongCloud nav URL — see "Why we got stuck") |
| Whoami / DeviceId | `POST appin.divoom-gz.com/User/GetUserInfo` | Confirms your `DeviceId` |
| Photos on the frame | `POST appin.divoom-gz.com/PhotoFrame/GetList` | Array of `{PhotoName, BigImageId, SmallImageId, PixelStartX, PixelStartY}` |
| Read any file | `POST appin.divoom-gz.com/Cloud/GetFileData` | Downloads by `FileId` (`group1/M00/...`) |
| **Upload arbitrary image to Divoom CDN** | `POST f.divoom-gz.com/upload.php` (multipart, field `upFile`, no auth needed) | Returns a real `FileId` in the same `group1/M00/...` format the frame uses |

The CDN upload is the discovery I'm most surprised by — it's totally unauthenticated and gives back a real `FileId` that the official app uses for Big/Small image references. So you can park files on Divoom's CDN today.

## What we couldn't crack ❌

The "bind this `FileId` to my frame's playlist" call. We tried ~160 method names across `PhotoFrame/*`, `Device/*`, `Channel/*`, `Cloud/*`, `Photo/*` with every plausible verb (`Add`, `Save`, `Set`, `Push`, `Insert`, `Sync`, `Update`, …). Every miss returned `ReturnCode: 10 "Command is not match"`. The single suggestive hit was:

```
POST /PhotoFrame/UploadFile
→ "Call to protected method app\\Controllers\\ApiBase::UploadFile()
   from context 'Server\\CoreBase\\Http'"
```

i.e. the endpoint exists in their PHP routing but is `protected` — not callable from outside.

## Why we got stuck (the RongCloud hypothesis)

The login response contains `UserToken: "...@ynfz.cn.rongnav.com;ynfz.cn.rongcfg.com"`. RongCloud is China's enterprise MQTT/IM SDK. The official Divoom app appears to keep an MQTT connection open and push device commands directly through that channel — so "show this photo" is a RongCloud message addressed to the device's user-token, not an HTTP call.

If true, the public HTTP API will *never* expose an attach-photo method, by design. The path forward is:

1. **mitmproxy** the official Android/iOS app, capture exactly what happens when you upload a photo from the gallery, copy that flow.
2. If SSL pinning blocks step 1: Frida bypass on a rooted Android emulator, or APK decompilation.

## Local HTTP API on :9000 (partial)

**Found 2026-05, re-confirmed 2026-06.** The frame exposes a local HTTP command API on the LAN. Credit to **Vasily Simanin** (`vsimanin`, issue #1), whose Home Assistant integration first used it. The original April writeup wrongly called the device "pure-cloud" because the endpoint is an unusual **GET-with-JSON-body** to `:9000/divoom_api` (not Pixoo's `:80/post`), so a naive port scan slips past it.

- **Transport:** `http://<frame-ip>:9000/divoom_api`, JSON body `{"Command": "...", ...}`. Same Divoom JSON-RPC family as Pixoo, different port + path.
- **No auth, LAN only.** The frame answers with its own `DeviceId` and `DeviceType: "Frame"`.
- **Unimplemented-command baseline:** `{"ReturnCode": 1, "ReturnMessage": "Only accept JSON parameters"}`. Verified as a catch-all — a garbage command, an empty object, and a request with no `Command` field all return it. So this reply means "not routed by the firmware", **not** "needs more params".

### Implemented locally (return `ReturnCode: 0`)

| Command | Payload | Notes |
|---|---|---|
| `Channel/GetConfig` | — | `RotationFlag, ClockTime, GalleryTime, SingleGalleyTime, ChannelIndex, StartUpClockId, GalleryShowTimeFlag` |
| `Channel/GetClockInfo` | — | `Brightness, ClockId` |
| `Channel/GetOnOffScreen` | — | `OnOff` |
| `Channel/GetAmbientLight` | — | `Brightness, Color, ColorCycle, EqOnOff, SelectEffect` |
| `Channel/GetEqPosition` | — | `EqPosition` |
| `Device/GetWeatherInfo` | — | `Weather, CurTemp, MinTemp, MaxTemp, Pressure, …` |
| `Channel/SetClockSelectId` | `{ClockId}` | switch built-in face (write) |
| `Channel/SetBrightness` | `{Brightness 0..100}` | write |
| `Channel/OnOffScreen` | `{OnOff 0\|1}` | screen on/off (write) |
| `Device/SysReboot` | — | reboot (write) |
| `Danmaku/SendText` | `{DeviceId, Text, TextColor, UserId}` | **POST**, not GET |
| `Device/EnterCustomControlMode` / `ExitCustomControlMode` | — | accepted; effect unclear, screen unchanged |
| `Draw/ResetHttpGifId`, `Draw/SendHttpGif`, `Draw/GetHttpGifId` | Pixoo pixel-buffer format | **accepted** (`ReturnCode 0`) but not visible: targets a draw channel, and channel-switching (`Channel/SetIndex`) is *not* implemented locally, so you can't bring it on screen via the API. Even if shown it's a ~64px pixel buffer, not a full-screen photo. |

### NOT implemented locally

Photo/playlist control is absent. ~920 probes across `Photo/*`, `PhotoFrame/*`, `Picture/*`, `Image/*`, `File/*`, `Cloud/*`, `Slideshow/*`, `Gallery/*`, `Channel/*` × `{Add, Set, Push, Insert, Bind, Sync, Update, Play, Show, …}` with a real `FileId` all hit the catch-all baseline. Channel switching (`Channel/SetIndex` / `GetIndex`) is also absent.

**Conclusion:** the local API controls brightness / screen / built-in faces / danmaku / a custom-control mode — but **not** the bind-FileId-to-playlist step. That still lives in the cloud / RongCloud channel; the local API does not shorten the missing piece. The mitmproxy path below remains the way to finish.

> **IP note:** the frame's LAN IP moves with DHCP (seen at `.65` → `.66` → `.64` across sessions). Reserve it by MAC in the router. To find it: scan `:9000` and check which host returns `DeviceType: "Frame"` to `Channel/GetConfig`.

## Why this device, not Pixoo

The Pixoo line (Pixoo 16/64) has a fully open local HTTP API on port 80 — dozens of libraries, Home Assistant integrations, the works. Times Frame exposes a **narrower** local API (above): screen/brightness/faces yes, photo control no. The photo experience is deliberately cloud-locked — Times Frame is sold as a no-subscription premium photo frame for non-technical users, and keeping the gallery behind their app protects the bundle. The open-source community hasn't fully cracked it yet because the addressable audience of hackers-who-bought-this-device is small.

## Use the toolkit

Requirements: Python 3.10+, `requests`, `pillow`.

```bash
# 1. Login (password from env keeps it out of shell history)
DIVOOM_PASSWORD='your-password' python divoom_cloud.py login --email you@example.com

# 2. Check that DeviceId came through
python divoom_cloud.py info

# 3. List what's on the frame today
python divoom_cloud.py list

# 4. Upload any JPG/PNG to the CDN, get a FileId
python divoom_cloud.py upload my_dashboard.jpg
# → FileId: group1/M00/17/E6/...jpg

# 5. (Doesn't work yet) Try every plausible attach endpoint with that FileId
python divoom_cloud.py probe-attach group1/M00/17/E6/...jpg
```

Token is cached in `.divoom_token` (gitignored). Email lives in `DIVOOM_EMAIL` env or the cached token. Password is **never** written to disk.

## What you'd need to finish this

* iPhone or Android with the Divoom app + your Times Frame paired
* mitmproxy on a laptop on the same network (~10 min setup)
* Capture one photo upload from the app — the missing call is in there
* Cross-reference with this repo's findings; the upload step we already have, you only need the second call

## File map

* `divoom_cloud.py` — cloud CLI: login, info, list, upload, probe-attach
* `divoom_local.py` — local `:9000/divoom_api` CLI: `info`, `call`, `probe`
* `divoom_timesframe.py`, `divoom_dashboard.py`, `divoom-dashboard-prompt.md` — dashboard-image generation experiments
* `probe_test.jpg` — 800×1280 test image for CDN upload
* `HANDOFF.md` — full session log (2026-05 physical-frame session + co-op notes)
* `.gitignore` — excludes `.divoom_token`
* `README.md` — this file

## Findings table for quick reference

| Host | Endpoint | Method | Auth | Status |
|---|---|---|---|---|
| `appin.divoom-gz.com` | `/UserLogin` | POST | none | ✅ `{Email, Password: md5(pwd)}` |
| `appin.divoom-gz.com` | `/User/GetUserInfo` | POST | Token+UserId | ✅ |
| `appin.divoom-gz.com` | `/PhotoFrame/GetList` | POST | Token+UserId+DeviceId | ✅ |
| `appin.divoom-gz.com` | `/Cloud/GetFileData` | POST | Token+UserId+FileId | ✅ |
| `appin.divoom-gz.com` | `/PhotoFrame/UploadFile` | POST | — | ⚠️ 200 OK but `protected method` (internal only) |
| `appin.divoom-gz.com` | `/PhotoFrame/{Add,Save,Set,…}Photo` | POST | — | ❌ `Command is not match` (~160 variants tried) |
| `f.divoom-gz.com` | `/upload.php` | POST multipart, field `upFile` | **none** | ✅ returns `FileId` |
| `<frame-ip>:9000` | `/divoom_api` (`Channel/Get*`, `OnOffScreen`, `SetBrightness`, `Draw/*`, `Danmaku/SendText`) | GET/POST + JSON body | **none (LAN)** | ✅ local control subset (screen/brightness/faces/danmaku) |
| `<frame-ip>:9000` | `/divoom_api` photo/playlist bind (`Photo/*`, `Cloud/*`, `Channel/SetIndex`, …) | GET/POST + JSON body | — | ❌ catch-all baseline (~920 variants tried) — not local |
