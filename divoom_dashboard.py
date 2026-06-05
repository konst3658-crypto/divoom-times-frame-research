"""
Divoom Times Gate Dashboard — Gifty Dev Monitor
Библиотека: pixoo-next (поддерживает Times Gate!)
IP: 192.168.1.65

Установка:
  git clone https://github.com/TheSecondLugia/pixoo-next.git
  cd pixoo-next
  pip install -e . --break-system-packages

Затем запуск:
  python divoom_dashboard.py
"""

import sys
import subprocess
from datetime import datetime, date

IP = "192.168.1.65"
LCD_SCREEN = 0  # 0=левый, 1, 2, 3, 4=правый экран Times Gate

# ─── Установка pixoo-next если нет ──────────────────────
def install_pixoo_next():
    try:
        from pixoo import Pixoo
        return True
    except ImportError:
        print("Устанавливаю pixoo-next...")
        subprocess.run([
            sys.executable, "-m", "pip", "install",
            "git+https://github.com/TheSecondLugia/pixoo-next.git",
            "--break-system-packages"
        ], check=True)
        return True

# ─── Создание дашборда ───────────────────────────────────
def build_and_push():
    from pixoo import Pixoo

    print(f"\n🔌 Подключаюсь к Times Gate ({IP})...")
    pixoo = Pixoo(IP, model="TIMESGATE")

    # Чёрный фон
    pixoo.fill_rgb(4, 6, 16)

    # Заголовок
    pixoo.draw_text_at_location_rgb("GIFTY", 4, 3, 90, 140, 255)

    # Горизонтальная линия
    for x in range(4, 124):
        pixoo.draw_pixel_at_location_rgb(x, 18, 25, 35, 75)

    # Дней до релиза
    release = date(2026, 6, 30)
    days = (release - date.today()).days

    pixoo.draw_text_at_location_rgb("DO RELIZA", 4, 23, 60, 90, 160)
    pixoo.draw_text_at_location_rgb(str(days), 4, 34, 255, 210, 40)
    pixoo.draw_text_at_location_rgb("dney", 44, 48, 60, 90, 160)

    # Линия
    for x in range(4, 124):
        pixoo.draw_pixel_at_location_rgb(x, 62, 25, 35, 75)

    # Этап
    pixoo.draw_text_at_location_rgb("ETAP 8", 4, 66, 60, 90, 160)
    pixoo.draw_text_at_location_rgb("Predreliz", 4, 77, 200, 220, 255)

    # Линия
    for x in range(4, 124):
        pixoo.draw_pixel_at_location_rgb(x, 95, 25, 35, 75)

    # Время
    now = datetime.now()
    pixoo.draw_text_at_location_rgb(now.strftime("%H:%M"), 4, 99, 50, 70, 130)
    pixoo.draw_text_at_location_rgb(now.strftime("%d.%m.%y"), 4, 110, 40, 60, 110)

    # Зелёная точка — статус ОК
    pixoo.draw_filled_rectangle_from_location_rgb(113, 113, 122, 122, 45, 200, 75)

    # Push на нужный экран (lcd_index — номер экрана 0-4)
    print(f"📡 Пушу на экран #{LCD_SCREEN}...")
    pixoo.push(lcd_index=LCD_SCREEN)
    print("✅ Готово! Дашборд на рамке.")


# ─── MAIN ─────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 45)
    print("  Divoom Times Gate — Gifty Dashboard v2")
    print("=" * 45)

    install_pixoo_next()

    try:
        build_and_push()
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        print("\nДиагностика:")
        print(f"  - Рамка IP: {IP}")
        print("  - Убедись что оба устройства в одной Wi-Fi сети")
        print("  - Попробуй изменить LCD_SCREEN (0-4) если не тот экран")
        print(f"  - Полная ошибка: {type(e).__name__}: {e}")
        raise
