# valhalla_clone

Набор DSP-обработок, повторяющих параметры и режимы плагинов Valhalla DSP.
Алгоритмы написаны с нуля на основе классических схем: FDN-реверб, пластина
Датторро, частотный сдвиг через преобразование Гильберта, питч-шифтер на
линии задержки. Исходный код Valhalla не используется, поэтому звук близок
к оригиналу, но не совпадает с ним бит в бит. Набор параметров, их диапазоны
и названия режимов совпадают с плагинами, так что настройки переносятся
напрямую.

| Эффект | Модуль | Режимы |
|---|---|---|
| ValhallaVintageVerb | `vintageverb` | 22 режима реверба (Concert Hall … Hall1984) × цвет 1970s / 1980s / Now |
| ValhallaRoom | `room` | Large Room, Medium Room, Bright Room, Large Chamber, Dark Room, Large Space, Dark Space, Small Space, Nonlinear, Narrow Tail |
| ValhallaPlate | `plate` | Steel, Aluminum, Brass, Gold, Bronze, Copper, Silver, Platinum, Titanium |
| ValhallaShimmer | `shimmer` | Mono, Stereo, Reverse, Bloom |
| Valhalla Supermassive | `supermassive` | 18 режимов (Gemini … Virgo) |
| ValhallaDelay | `delay` | Tape, HiFi, BBD, Digital, Ghost, Pitch, RevTape × Single / Dual / PingPong |
| Valhalla Freq Echo | `freqecho` | Normal, Analog (+ Low Shift) |
| Valhalla Space Modulator | `spacemod` | Flange, ThruZero, Barberpole Up/Down, Chorus, Doubler, Vibrato |
| ValhallaUberMod | `ubermod` | Clean, Tape, Dark Tape, BBD, Lo-Fi, Diffuse, Rhythmic |

## Установка

```bash
pip install -r requirements.txt   # numpy обязателен; numba — ускорение примерно в 100 раз
```

## Командная строка

```bash
python -m valhalla_clone list                         # все эффекты и режимы
python -m valhalla_clone info vintageverb             # параметры и значения по умолчанию

# обработать WAV
python -m valhalla_clone process vintageverb in.wav out.wav \
    --set ReverbMode="Concert Hall" --set Decay=3.5 --set Mix=30

# применить пресет: свой JSON или .vpreset, сохранённый из самого плагина
python -m valhalla_clone process presets/plate/gold.json in.wav out.wav
python -m valhalla_clone process "My Hall.vpreset" in.wav out.wav

# цепочка обработок
python -m valhalla_clone process delay in.wav out.wav --chain presets/room/largeroom.json

# скопировать совпадающие настройки (Mix, PreDelay, Decay, ModRate, HighCut, …) в другой эффект
python -m valhalla_clone copy hall.json room room_from_hall.json

# выгрузить банк стандартных настроек: один пресет на каждый режим каждого эффекта
python -m valhalla_clone bank presets
```

Готовый банк из 86 пресетов лежит в `presets/<эффект>/<режим>.json`.

### Импорт `.vpreset`

Пресеты Valhalla хранятся в XML, значения параметров в нём нормализованы
к диапазону 0…1. Импортёр сам определяет плагин по корневому тегу и
сопоставляет атрибуты с параметрами без учёта регистра. Неизвестные ключи
выводятся в stderr. Если в файле записаны реальные значения (секунды, Гц),
добавьте `--plain`.

## Python API

```python
from valhalla_clone import get_effect, load_preset
from valhalla_clone.wavio import read_wav, write_wav

x, sr = read_wav("vocal.wav")
verb = get_effect("vintageverb")(ReverbMode="Plate", ColorMode="1970s", Decay=1.8, Mix=25)
y = verb.process(x, sr)              # стерео, с хвостом реверба
write_wav("vocal_plate.wav", y, sr)

room = get_effect("room")()
room.copy_settings_from(verb)        # перенос одноимённых настроек
```

## Тесты

```bash
python -m pytest -q
```

Тесты проверяют все 86 режимов на устойчивость и отсутствие NaN, сухой
сигнал при Mix = 0 и совпадение измеренного RT60 с параметром Decay
(±20 %). Отдельно проверяются направление частотного сдвига, импорт
`.vpreset`, перенос настроек, чтение и запись WAV, а также CLI.
