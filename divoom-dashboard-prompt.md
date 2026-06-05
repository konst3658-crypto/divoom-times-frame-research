# Промпт для Claude Code — Divoom Times Gate Dashboard

Вставь это в Claude Code и он сделает всё сам.

---

## Задача

Подключиться к Divoom Times Gate по локальному HTTP API и вывести на один из экранов девелопмент-дашборд для проекта Gifty.

**IP устройства:** `192.168.1.65`
**Устройство:** Divoom Times Gate (5 LCD-экранов по 128×128 пикселей, серия Pixoo)

---

## Шаг 1 — Проверить связь

Попробуй базовый запрос к API устройства:

```python
import requests
import json

ip = "192.168.1.65"

# Вариант 1 — стандартный Divoom API endpoint
response = requests.post(
    f"http://{ip}/post",
    json={"Command": "Device/GetDeviceTime"},
    timeout=5
)
print(response.status_code, response.text)
```

Если не отвечает на `/post` — попробуй `/api` и `GET http://{ip}/`. Выведи что вернул сервер.

---

## Шаг 2 — Установить библиотеку

```bash
pip install pixoo pillow requests --break-system-packages
```

Попробуй подключиться через библиотеку pixoo:

```python
from pixoo import Pixoo

pixoo = Pixoo('192.168.1.65')
pixoo.fill_rgb(0, 0, 0)  # чёрный фон
pixoo.push()
print("Подключение успешно")
```

Если pixoo не работает с Times Gate — используй raw HTTP requests напрямую.

---

## Шаг 3 — Нарисовать дашборд

Создай файл `divoom_dashboard.py`:

```python
from PIL import Image, ImageDraw, ImageFont
import requests
import json
from datetime import datetime, date

ip = "192.168.1.65"
SCREEN_SIZE = 128  # Times Gate: 128x128 на каждый экран

def create_dashboard_image():
    """Генерирует изображение дашборда 128x128"""
    img = Image.new('RGB', (SCREEN_SIZE, SCREEN_SIZE), color=(5, 5, 15))
    draw = ImageDraw.Draw(img)

    # Попробуй найти шрифт, если нет — использует дефолтный
    try:
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 9)
        font_med = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
        font_big = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
    except:
        font_small = ImageFont.load_default()
        font_med = font_small
        font_big = font_small

    # === КОНТЕНТ ===
    
    # Заголовок
    draw.text((4, 4), "GIFTY", font=font_med, fill=(100, 150, 255))
    draw.line([(4, 20), (124, 20)], fill=(30, 40, 80), width=1)

    # Дней до релиза (считаем до 30 июня 2026)
    release_date = date(2026, 6, 30)
    days_left = (release_date - date.today()).days
    
    draw.text((4, 26), "ДО РЕЛИЗА", font=font_small, fill=(80, 100, 160))
    draw.text((4, 36), f"{days_left}", font=font_big, fill=(255, 220, 50))
    draw.text((42, 46), "дней", font=font_small, fill=(80, 100, 160))

    draw.line([(4, 65), (124, 65)], fill=(30, 40, 80), width=1)

    # Текущий этап
    draw.text((4, 70), "ЭТАП 8", font=font_small, fill=(80, 100, 160))
    draw.text((4, 80), "Предрелиз", font=font_small, fill=(200, 220, 255))

    draw.line([(4, 95), (124, 95)], fill=(30, 40, 80), width=1)

    # Время обновления
    now = datetime.now()
    draw.text((4, 100), now.strftime("%H:%M"), font=font_small, fill=(60, 80, 140))
    draw.text((4, 112), now.strftime("%d.%m.%Y"), font=font_small, fill=(40, 60, 110))

    # Статус-точка (зелёная = всё ок)
    draw.ellipse([(112, 112), (122, 122)], fill=(50, 200, 80))

    return img

def push_to_divoom(img):
    """Пушит PIL-изображение на Times Gate"""
    
    # Метод 1 — через библиотеку pixoo
    try:
        from pixoo import Pixoo
        pixoo = Pixoo(ip)
        pixoo.draw_image(img)
        pixoo.push()
        print("✅ Отправлено через pixoo")
        return
    except Exception as e:
        print(f"pixoo не сработал: {e}")

    # Метод 2 — raw HTTP API (Divoom local protocol)
    try:
        # Конвертируем в массив RGB
        pixels = list(img.getdata())
        pic_data = ""
        for r, g, b in pixels:
            pic_data += f"{r:02x}{g:02x}{b:02x}"

        payload = {
            "Command": "Draw/SendHttpGif",
            "PicNum": 1,
            "PicWidth": SCREEN_SIZE,
            "PicOffset": 0,
            "PicID": 1,
            "PicSpeed": 1000,
            "PicData": pic_data
        }

        response = requests.post(
            f"http://{ip}/post",
            json=payload,
            timeout=10
        )
        print(f"HTTP ответ: {response.status_code} {response.text}")
    except Exception as e:
        print(f"HTTP метод не сработал: {e}")

if __name__ == "__main__":
    print("Генерирую дашборд...")
    img = create_dashboard_image()
    img.save("dashboard_preview.png")  # Сохраняем превью
    print("Превью сохранено: dashboard_preview.png")
    
    print(f"Отправляю на Times Gate ({ip})...")
    push_to_divoom(img)
    print("Готово!")
```

---

## Шаг 4 — Запустить и показать превью

```bash
python divoom_dashboard.py
```

Покажи мне файл `dashboard_preview.png` — посмотрю как выглядит до отправки на рамку.

---

## Шаг 5 — Автообновление каждые 30 минут

Если всё работает — добавь в cron (macOS/Linux):

```bash
crontab -e
# Добавить:
*/30 * * * * /usr/bin/python3 /путь/к/divoom_dashboard.py
```

Или запусти loop внутри скрипта:

```python
import time
while True:
    img = create_dashboard_image()
    push_to_divoom(img)
    time.sleep(1800)  # каждые 30 минут
```

---

## Важно

- Рамка и компьютер должны быть в одной Wi-Fi сети (`MGTS_GPON5_9727`)
- Times Gate использует тот же Divoom API что Pixoo — должно работать
- Если `/post` не отвечает — попробуй `Draw/SendHttpGif` вместо `Draw/SendHttpText`
- Покажи мне вывод каждого шага чтобы отладить если что-то не так
