"""
Divoom Times Frame Dashboard — через облачный API
Загружает картинку дашборда на рамку через аккаунт Divoom

Установка: pip install requests pillow --break-system-packages
Запуск: python divoom_timesframe.py
"""

import requests
import hashlib
import json
import base64
import getpass
from datetime import datetime, date
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import sys

# ─── Настройки ────────────────────────────────────────────
EMAIL = "knikulichev@yandex.ru"  # email предзаполнен
API_BASE = "https://appin.divoom-gz.com"

# ─── Логин ────────────────────────────────────────────────
def login(email, password):
    """Авторизация в Divoom cloud API"""
    pwd_md5 = hashlib.md5(password.encode()).hexdigest()

    r = requests.post(f"{API_BASE}/UserLogin", json={
        "Email": email,
        "Password": pwd_md5
    }, timeout=10)

    data = r.json()
    if data.get("ReturnCode") != 0:
        print(f"❌ Ошибка входа: {data.get('ReturnMessage', 'Unknown')}")
        return None, None, None

    token = data["Token"]
    user_id = data["UserId"]
    print(f"✅ Вошёл как {email}")
    return token, user_id, data


def get_devices(token, user_id):
    """Получить список устройств"""
    r = requests.post(f"{API_BASE}/GetDeviceList", json={
        "Token": token,
        "UserId": user_id,
        "PageIndex": 0
    }, timeout=10)

    data = r.json()
    devices = data.get("DeviceList", [])
    print(f"\n📱 Найдено устройств: {len(devices)}")
    for i, d in enumerate(devices):
        print(f"  [{i}] {d.get('DeviceName', '?')} — ID: {d.get('DeviceId', '?')}")
    return devices


# ─── Создание изображения ─────────────────────────────────
def build_image(width=800, height=600):
    """Генерирует дашборд под большой экран Times Frame"""
    img = Image.new("RGB", (width, height), (4, 6, 18))
    draw = ImageDraw.Draw(img)

    # Попробуем шрифты
    try:
        font_huge  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 120)
        font_big   = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 60)
        font_med   = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 36)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
    except:
        try:
            font_huge  = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 120)
            font_big   = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 60)
            font_med   = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 36)
            font_small = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 24)
        except:
            font_huge = font_big = font_med = font_small = ImageFont.load_default()

    # Фоновые линии
    for y in range(0, height, 40):
        draw.line([(0, y), (width, y)], fill=(10, 15, 35), width=1)

    # Заголовок
    draw.text((50, 40), "GIFTY", font=font_big, fill=(90, 140, 255))

    # Разделитель
    draw.line([(50, 120), (width-50, 120)], fill=(30, 45, 100), width=2)

    # Дней до релиза
    release = date(2026, 6, 30)
    days = (release - date.today()).days

    draw.text((50, 145), "ДО РЕЛИЗА", font=font_med, fill=(60, 90, 160))
    draw.text((50, 185), str(days), font=font_huge, fill=(255, 210, 40))
    draw.text((220, 260), "дней", font=font_med, fill=(60, 90, 160))

    # Разделитель
    draw.line([(50, 320), (width-50, 320)], fill=(30, 45, 100), width=2)

    # Этап
    draw.text((50, 345), "ЭТАП 8 — ПРЕДРЕЛИЗ", font=font_med, fill=(100, 160, 255))

    # Прогресс
    items = [
        ("Google / Apple OAuth", False),
        ("Домен gifty.app", False),
        ("Аналитика", False),
        ("Privacy Policy", False),
        ("Иконка и сплэш", False),
    ]
    y_pos = 390
    for item, done in items:
        color = (50, 200, 80) if done else (80, 80, 120)
        mark = "✓" if done else "○"
        draw.text((60, y_pos), f"{mark}  {item}", font=font_small, fill=color)
        y_pos += 36

    # Время обновления
    now = datetime.now()
    draw.line([(50, height-70), (width-50, height-70)], fill=(20, 30, 70), width=1)
    draw.text((50, height-55), f"Обновлено: {now.strftime('%d.%m.%Y  %H:%M')}",
              font=font_small, fill=(40, 60, 110))

    # Статус точка
    draw.ellipse([(width-70, height-60), (width-40, height-30)], fill=(50, 200, 80))

    return img


# ─── Загрузка на рамку ────────────────────────────────────
def upload_to_frame(img, token, user_id, device_id):
    """Загружает изображение через облако"""

    # Конвертируем в JPEG bytes
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=90)
    img_bytes = buf.getvalue()
    img_b64 = base64.b64encode(img_bytes).decode()

    # Метод 1 — попробуем SendLocalNotification или PictureRedirection
    endpoints = [
        "Device/SetPicturePushingUrl",
        "Device/SendRemoteNotification",
        "Device/PlayDivoomItemId",
    ]

    # Основной метод — загрузка через Photo
    print("\n📤 Загружаю изображение...")

    r = requests.post(f"{API_BASE}/device/photo/upload", json={
        "Token": token,
        "UserId": user_id,
        "DeviceId": device_id,
        "FileBase64": img_b64,
        "FileName": "dashboard.jpg"
    }, timeout=30)

    print(f"Ответ: {r.status_code} — {r.text[:300]}")
    return r.json() if r.ok else None


# ─── MAIN ─────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 50)
    print("  Divoom Times Frame — Gifty Dashboard")
    print("=" * 50)

    # Авторизация
    print(f"\nEmail: {EMAIL}")
    password = getpass.getpass("Пароль Divoom (не отображается): ")

    token, user_id, login_data = login(EMAIL, password)
    if not token:
        sys.exit(1)

    # Список устройств
    devices = get_devices(token, user_id)
    if not devices:
        print("❌ Устройств не найдено")
        print(f"\nПолный ответ: {json.dumps(login_data, indent=2, ensure_ascii=False)}")
        sys.exit(1)

    # Выбор устройства
    if len(devices) == 1:
        device = devices[0]
    else:
        idx = int(input(f"\nВыбери устройство [0-{len(devices)-1}]: "))
        device = devices[idx]

    device_id = device["DeviceId"]
    print(f"\n✅ Выбрано: {device.get('DeviceName')} (ID: {device_id})")

    # Генерация изображения
    print("\n🎨 Генерирую дашборд...")
    img = build_image()
    img.save("dashboard_preview.jpg", quality=90)
    print("✅ Превью: dashboard_preview.jpg")

    # Загрузка
    result = upload_to_frame(img, token, user_id, device_id)
    if result:
        print(f"\n📊 Результат: {json.dumps(result, indent=2, ensure_ascii=False)}")
    else:
        print("\nℹ️  Проверь ответ выше — возможно нужен другой endpoint")
        print("    Покажи вывод мне — подберём правильный метод")
