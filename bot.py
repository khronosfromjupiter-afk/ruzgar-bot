import os
import json
import requests

from telegram import Update
from telegram.ext import Application, CommandHandler

TOKEN = os.environ["BOT_TOKEN"]
PORT = int(os.environ.get("PORT", "10000"))
PUBLIC_URL = os.environ.get("RENDER_EXTERNAL_URL")

POINTS_FILE = "noktalar.json"
def get_elevation(lat, lon):
    try:
        url = "https://api.open-meteo.com/v1/elevation"
        response = requests.get(
            url,
            params={"latitude": lat, "longitude": lon},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        return round(data["elevation"][0])
    except Exception:
        return 0


DEFAULT_POINTS = {
    "gencan": {
        "name": "Gencan",
        "lat": 38.04898,
        "lon": 40.27268,
        "altitude": 631
    },
    "hani": {
        "name": "Hani",
        "lat": 38.4442142,
        "lon": 40.2847178,
        "altitude": get_elevation(38.4442142, 40.2847178)
    },
    "yesildalli": {
        "name": "Yeşildallı",
        "lat": 37.9023469,
        "lon": 40.1392847,
        "altitude": get_elevation(37.9023469, 40.1392847)
    }
}

def load_points():
    if not os.path.exists(POINTS_FILE):
        save_points(DEFAULT_POINTS)
        return DEFAULT_POINTS

    try:
        with open(POINTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        save_points(DEFAULT_POINTS)
        return DEFAULT_POINTS


def save_points(points):
    with open(POINTS_FILE, "w", encoding="utf-8") as f:
        json.dump(points, f, ensure_ascii=False, indent=2)


def wind_direction(degrees):
    directions = [
        "K", "KKD", "KD", "DKD",
        "D", "DGD", "GD", "GGB",
        "G", "GBG", "GB", "BGB",
        "B", "BKB", "KB", "KKB"
    ]
    return directions[round(degrees / 22.5) % 16]


def get_weather(lat, lon):
    url = "https://api.open-meteo.com/v1/forecast"

    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": [
            "temperature_2m",
            "wind_speed_10m",
            "wind_direction_10m",
            "wind_gusts_10m",
            "precipitation_probability",
            
        ],
        "forecast_days": 1,
        "timezone": "Europe/Istanbul"
    }

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()

    return response.json()


async def start(update, context):
    await update.message.reply_text(
        "🪂 Rüzgar Botu\n\n"
        "/noktalar — Kayıtlı uçuş noktaları\n"
        "/ruzgar Gencan — Rüzgar bilgisi\n"
        "/ekle İsim enlem boylam — Yeni nokta ekle\n"
        "/sil İsim — Nokta sil"
    )


async def noktalar(update, context):
    points = load_points()

    message = "📍 Kayıtlı uçuş noktaları:\n\n"

    for point in points.values():
        message += (
            f"🪂 {point['name']}\n"
            f"   {point['lat']}, {point['lon']}\n"
            f"   Rakım: {point['altitude']} m\n\n"
        )

    await update.message.reply_text(message)


async def ekle(update, context):
    if len(context.args) != 3:
        await update.message.reply_text(
            "Kullanım:\n"
            "/ekle İsim enlem boylam\n\n"
            "Örnek:\n"
            "/ekle Hani-TO 38.4442142 40.2847178"
        )
        return

    name = context.args[0]
    key = name.lower()

    try:
        lat = float(context.args[1])
        lon = float(context.args[2])

        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError

    except ValueError:
        await update.message.reply_text(
            "❌ Enlem/boylam değerleri hatalı."
        )
        return

    try:
        url = "https://api.open-meteo.com/v1/forecast"

        params = {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m",
            "timezone": "Europe/Istanbul"
        }

        response = requests.get(
            url,
            params=params,
            timeout=30
        )

        response.raise_for_status()

        altitude = response.json()["elevation"]

    except Exception as e:
        await update.message.reply_text(
            f"⚠️ Rakım alınamadı:\n{type(e).__name__}: {e}"
        )
        return

    points = load_points()

    points[key] = {
        "name": name,
        "lat": lat,
        "lon": lon,
        "altitude": altitude
    }

    save_points(points)

    await update.message.reply_text(
        f"✅ {name} eklendi.\n\n"
        f"📍 Enlem: {lat}\n"
        f"📍 Boylam: {lon}\n"
        f"🏔️ Rakım: {altitude} m"
    )


async def sil(update, context):
    if len(context.args) != 1:
        await update.message.reply_text(
            "Kullanım:\n/sil İsim"
        )
        return

    key = context.args[0].lower()
    points = load_points()

    if key not in points:
        await update.message.reply_text(
            "❌ Bu isimde kayıtlı bir nokta yok."
        )
        return

    if key == "gencan":
        await update.message.reply_text(
            "❌ Gencan varsayılan noktadır, silinemez."
        )
        return

    name = points[key]["name"]

    del points[key]
    save_points(points)

    await update.message.reply_text(
        f"🗑️ {name} silindi."
    )


async def ruzgar(update, context):
    points = load_points()

    if len(context.args) == 0:
        key = "gencan"
    else:
        key = context.args[0].lower()

    if key not in points:
        await update.message.reply_text(
            "❌ Bu isimde kayıtlı bir nokta yok.\n\n"
            "Kayıtlı noktalar için /noktalar"
        )
        return

    point = points[key]

    try:
        data = get_weather(
            point["lat"],
            point["lon"]
        )

        h = data["hourly"]

        message = (
            f"🪂 {point['name']}\n"
            f"🏔️ Zemin rakımı: {point['altitude']} m\n\n"
        )

        for i in range(8):
            time = h["time"][i][11:16]

            message += "━━━━━━━━━━━━━━\n"
            message += f"🕐 {time}\n"
            message += f"🌡️ {h['temperature_2m'][i]:.1f}°C\n"
            message += (
                f"🌧️ Yağış: "
                f"%{h['precipitation_probability'][i]}\n\n"
            )

            message += (
                f"💨 Rüzgâr: "
                f"{h['wind_speed_10m'][i]:.0f} km/sa "
                f"{wind_direction(h['wind_direction_10m'][i])}\n"
            )

            message += (
                f"💥 Gust: "
                f"{h['wind_gusts_10m'][i]:.0f} km/sa\n"
            )

        await update.message.reply_text(message)

    except Exception as e:
        await update.message.reply_text(
            f"❌ Veri alınırken hata oluştu:\n"
            f"{type(e).__name__}: {e}"
        )

def main():
    application = (
        Application.builder()
        .token(TOKEN)
        .build()
    )

    application.add_handler(
        CommandHandler("start", start)
    )
    application.add_handler(
        CommandHandler("noktalar", noktalar)
    )
    application.add_handler(
        CommandHandler("ekle", ekle)
    )
    application.add_handler(
        CommandHandler("sil", sil)
    )
    application.add_handler(
        CommandHandler("ruzgar", ruzgar)
    )

    webhook_url = f"{PUBLIC_URL}/telegram"

    print("🪂 Bot webhook ile çalışıyor...")
    print(f"Webhook: {webhook_url}")

    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="telegram",
        webhook_url=webhook_url
    )


if __name__ == "__main__":
    main()
