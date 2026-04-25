# Divoom Times Frame — cloud API research (~80% reversed)

Notes from a one-evening attempt to push a custom dashboard image to a Divoom **Times Frame** (10.1″ Wi-Fi photo frame, 2024–25 model).

**Status:** got most of the cloud API working — login, account info, photo list, file upload to the CDN. The very last step — telling the frame "now display this freshly uploaded file" — is closed off in the public HTTP API and almost certainly travels over the **RongCloud MQTT** channel that the official mobile app keeps open. Without intercepting the app's traffic we can't see those messages.

If you finish the missing piece, please open a PR — this is exactly where someone with mitmproxy and an iPhone could close the loop in an hour.

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

## Why this device, not Pixoo

The Pixoo line (Pixoo 16/64) has a fully open local HTTP API on port 80 — there are dozens of libraries, Home Assistant integrations, the works. **Times Frame doesn't expose anything locally** (we scanned all common ports — only `Libuhttpd` on 9000, no useful endpoints). It's pure-cloud.

That's a deliberate Divoom decision: Times Frame is sold as a no-subscription premium photo frame for non-technical users. Locking everything behind their app keeps the experience simple and protects the bundle. Open-source community hasn't reverse-engineered it yet because the addressable audience of hackers-who-bought-this-device is small.

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

* `divoom_cloud.py` — CLI: login, info, list, upload, probe-attach
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
