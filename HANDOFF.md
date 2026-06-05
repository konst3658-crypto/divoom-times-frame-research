# Divoom Times Frame — handoff (08 мая 2026)

Сессия с физической рамкой. Что нашли, чего не нашли, куда копать дальше.

> **Апдейт 2026-06-05 (короткая сессия).** Независимо переподтвердили локальный API — и тем самым проверили выводы 8 мая на свежую рамку.
> - IP снова уехал по DHCP: `.66` → **`.64`**. DeviceId тот же `300361651`, `DeviceType: "Frame"`.
> - Подтвердили, что `"Only accept JSON parameters"` — это **catch-all на любую нереализованную команду** (мусорная команда, пустой объект и запрос без `Command` дают тот же ответ). Значит все фото/`SetIndex`-промахи — действительно «не реализовано локально», а не «нужны параметры».
> - `Draw/SendHttpGif` рамка **принимает** (`ReturnCode 0`), но картинку не показать: рисуется в draw-канал, а переключить канал локально нельзя (`Channel/SetIndex` не реализован). Даже если показать — ~64px пиксель-буфер, не фото на весь экран. Пиксельную лазейку решили не добивать.
> - Вывод 8 мая в силе: bind-FileId локально нет, он в cloud/RongCloud. Следующий шаг прежний — mitmproxy + телефон.
> - В этой сессии наконец **закоммитили** всю незакоммиченную работу 8 мая (этот файл, `divoom_local.py`, дашборд-скрипты) и переписали устаревшие секции README под локальный API.

## Главные правки к README

README на 25 апреля утверждал «Times Frame doesn't expose anything locally — only Libuhttpd on 9000, no useful endpoints». **Это неверно.** Локальный API есть, и он на том же :9000. Мы пропустили его потому что:

- путь не корневой, а `/divoom_api`;
- метод GET, но с **JSON в теле** (нестандартная связка, port-scan её не находит).

Когда README будем переписывать, эту секцию надо переделать.

## Состояние сети / устройства

- **Старый IP** `192.168.1.65` уехал по DHCP — теперь там другой клиент (порты закрыты, но host пингуется).
- **Текущий IP рамки** `192.168.1.66`. Подтверждено через `Channel/GetConfig` → `DeviceType: "Frame"`.
- **DeviceId** `300361651` (рамка сама о себе сообщает по локалке, без cloud).
- **Действие на будущее:** в админке роутера сделать DHCP-reservation для MAC рамки → больше не теряем IP между сессиями.
- **Cloud-токен в `.divoom_token`** скорее всего протух (от 25 апреля): `divoom_cloud.py list` упал «No DeviceId on this account». Перед следующим cloud-сценарием — `python divoom_cloud.py login` заново.

## Известные локальные команды (подтверждены на нашей рамке)

Все возвращают HTTP 200 + `ReturnCode: 0`. Транспорт: `GET http://192.168.1.66:9000/divoom_api` с JSON-телом `{"Command": "...", ...}`. Исключения помечены.

| Команда | Полезная нагрузка | Что отдала наша рамка |
|---|---|---|
| `Channel/GetConfig` | — | `RotationFlag: 0, ClockTime: 60, GalleryTime: 60, ChannelIndex: 0, StartUpClockId: 1633840236` |
| `Channel/GetClockInfo` | — | `Brightness: 100, ClockId: 272785` |
| `Channel/GetOnOffScreen` | — | `OnOff: 1` |
| `Channel/GetAmbientLight` | — | `Brightness: 100, Color: "#00ffff", ColorCycle: 1, EqOnOff: 1, SelectEffect: 0` |
| `Channel/SetClockSelectId` | `{ClockId: int}` | переключение оболочки (от Vasily) |
| `Channel/SetBrightness` | `{Brightness: 0..100}` | (от Vasily) |
| `Channel/OnOffScreen` | `{OnOff: 0|1}` | (от Vasily) |
| `Device/SysReboot` | — | (от Vasily) |
| `Danmaku/SendText` | `{DeviceId, Text, TextColor, UserId}` | **POST**, не GET (от Vasily) |
| **`Device/EnterCustomControlMode`** | — | новость; ReturnCode 0; **что именно меняется — не понятно**, экран на месте, ClockId не сбросился |
| **`Device/ExitCustomControlMode`** | — | парная команда; всегда возвращает success |

Бейзлайн неизвестной команды: `HTTP 200 + {"ReturnCode": 1, "ReturnMessage": "Only accept JSON parameters"}`. На него настроен фильтр в `divoom_local.py probe`.

## Что не нашли (460 + 462 = 922 пробы)

Ни одной локальной команды для **bind FileId → photo playlist**. Все варианты `Photo/*`, `File/*`, `PhotoFrame/*`, `Picture/*`, `Image/*`, `Cloud/*`, `Slideshow/*`, `Gallery/*` × `{Add,Set,Push,Insert,Bind,Sync,Update,Play,Show,...}` отбились бейзлайном.

После `EnterCustomControlMode` повторный probe тоже ничего нового не открыл (попробованы `Device/Send*`, `Custom/*`, `Draw/*`, `Pixel/*`, `Display/*`, `Buffer/*`, `Frame/*`, `SendImage/SendBuffer/SetImage/PushImage/...` × GET и POST).

**Вывод:** local API скорее всего не предназначен для bind-FileId. Это разные каналы — bind лежит в cloud/RongCloud, а local — для управления яркостью/экраном/выбора оболочек/danmaku/некоего custom-режима, для которого данные ожидаются по неизвестному пока второму каналу.

## Файлы в репо после этой сессии

- `divoom_local.py` — новый CLI: `info`, `call`, `probe`. Покрывает локальный `:9000/divoom_api`.
- `probe_test.jpg` — тестовая 800×1280 заливка для CDN-аплоада. Можно удалить, можно оставить.
- `HANDOFF.md` — этот файл.
- (без изменений) `divoom_cloud.py`, `divoom_dashboard.py`, `divoom_timesframe.py`, `README.md`.

`README.md` пока **не правил** — после следующей сессии перепишем секции «What we couldn't crack» и «Why we got stuck» с учётом находок.

## Кооперация на гитхабе

- Issue #1 на нашем репо открыл **Vasily Simanin** (`vsimanin`) — пишет HA-интеграцию для Times Frame, имеет прямой канал в Divoom support. Я ответил [комментарием #4399880664](https://github.com/konst3658-crypto/divoom-times-frame-research/issues/1#issuecomment-4399880664) с тремя вопросами и предложением кооперации. Жду ответ.
- В его репо (`vsimanin/ha-divoom-timesframe`, issue #1) **Alex Posypanov** (`mierovingin`) копал через root-телефон + Dexterceptor (mitm на телефоне). Он же первый достал инфу про **ADB-доступ к самой рамке** (root / `Divoom~!@#`, только USB, кабель из коробки только зарядный, нужен дата-кабель).

## План на следующую сессию (по убыванию ROI)

### Вариант 1 — mitmproxy на телефоне (рекомендую)
Самый короткий путь. Открыть Divoom-приложение на телефоне → отправить любую картинку на рамку → mitmproxy на ноуте ловит ровно тот HTTP/MQTT/WebSocket-вызов, который мы ищем. Закрывает сразу обе задачи: и bind-FileId (cloud-сторона), и custom-mode payload (local-сторона). Время: ~30 минут setup + 10 минут наблюдения.

Вход:
- mitmproxy на ноуте (`pip install mitmproxy` или brew/choco)
- На телефоне: подключиться к нашей wifi, в настройках прокси указать IP ноута :8080
- Установить cert mitmproxy (на android — рутованный либо через Magisk, на iOS — через профиль; SSL-pinning у Divoom-приложения, скорее всего, отсутствует; если есть — Frida)

### Вариант 2 — ADB на саму рамку
Дешевле в setup (нужен только USB-кабель с данными), но требует физический доступ. Зайти `adb shell`, root, вытащить главный бинарь приложения с разделов `/overlay` или `/userdata`, посмотреть как handler `Device/EnterCustomControlMode` инициализирует второй канал данных (порт/протокол).

Структура устройства (от mierovingin, без проверки):
- SoC: Allwinner sun8iw20, ARM Cortex-A7 ×2, ~128 MB RAM, ~56 GB UDISK
- ОС: TinaLinux, ядро 5.4 RT, embedded Linux (не Android)
- ФС: `/rom` ro squashfs, `/overlay` rw ext4, `/divoom-config`, `/userdata`, `/mnt/SDCARD`
- ADB только по USB (не по wifi), root-доступ открыт, пароль `Divoom~!@#`
- Рекомендованное разрешение для подложек 800×1280, форматы webp/jpg, gif тоже работает

### Вариант 3 — допросить Vasily / дождаться его ответа
Если он успел спросить Divoom support про bind-FileId — мы получим ответ напрямую без реверса. Время = 0, риск = 100% что не ответит вовремя.

## Команды для быстрого старта в новую сессию

```bash
cd "c:\Users\kniku\claude's folder\divoom-research"

# 1. Найти текущий IP (DHCP всё время скачет):
python -c "import socket, concurrent.futures as cf; \
hits=[ip for ip in (f'192.168.1.{i}' for i in range(2,255)) \
if (lambda: (socket.create_connection((ip,9000),timeout=0.6).close(), True))() \
in [True]]; print(hits)"
# затем ткнуть GetConfig в каждый, у кого DeviceType=Frame.

# Когда IP найден:
python divoom_local.py info --ip <IP>

# Перелогиниться в cloud (токен от апреля, скорее всего, мёртв):
DIVOOM_PASSWORD='...' python divoom_cloud.py login --email knikulichev@yandex.ru
python divoom_cloud.py info

# Свежий FileId для probe:
python divoom_cloud.py upload <jpg>
python divoom_local.py probe --ip <IP> '<FileId>'
```
