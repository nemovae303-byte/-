import logging
import asyncio
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ----------------- НАСТРОЙКИ БОТА -----------------
BOT_TOKEN = "9060889130:AAFLvnUbCd00hljducQaPdim3z4gCLMsZyU" 
YANDEX_GEO_API_KEY = "4f3b1766-0ab7-484c-89f2-662c81824833"

TARIFS = {
    "taxi_economy": {"name": "🚕 Такси (Эконом)", "base": 80, "per_km": 15, "per_min": 6},
    "scooter": {"name": "🛴 Самокат (Шеринг)", "base": 50, "per_min": 7, "speed_kmh": 20},
    "carsharing": {"name": "🚗 Каршеринг", "base": 0, "per_min": 11, "speed_kmh": 35}
}
# --------------------------------------------------

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

class RouteStates(StatesGroup):
    waiting_for_start = State()
    waiting_for_end = State()

async def get_coordinates(address: str) -> tuple:
    url = f"https://yandex.ru{YANDEX_GEO_API_KEY}&geocode={address}&format=json"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                try:
                    pos = data['response']['GeoObjectCollection']['featureMember']['GeoObject']['Point']['pos']
                    lon, lat = map(float, pos.split())
                    return lat, lon
                except (KeyError, IndexError):
                    return None
            return None

def calculate_distance(lat1, lon1, lat2, lon2) -> float:
    from math import radians, cos, sin, asin, sqrt
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)2 + cos(lat1) * cos(lat2) * sin(dlon/2)2
    c = 2 * asin(sqrt(a))
    r = 6371
    return round((c * r) * 1.3, 2)

@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await message.answer("👋 Привет! Я помогу сравнить цены на транспорт.\n\nВведите город и адрес начала поездки (например: Москва, Тверская 5):")
    await state.set_state(RouteStates.waiting_for_start)

@dp.message(RouteStates.waiting_for_start)
async def process_start_address(message: types.Message, state: FSMContext):
    start_addr = message.text
    coords = await get_coordinates(start_addr)
    if not coords:
        await message.answer("❌ Не удалось найти такой адрес. Попробуйте ввести точнее (с указанием города):")
        return
    await state.update_data(start_coords=coords, start_name=start_addr)
    await message.answer("📍 Отлично! Теперь введите конечный адрес (куда едем):")
    await state.set_state(RouteStates.waiting_for_end)

@dp.message(RouteStates.waiting_for_end)
async def process_end_address(message: types.Message, state: FSMContext):
    end_addr = message.text
    coords = await get_coordinates(end_addr)
    if not coords:
        await message.answer("❌ Не удалось найти такой адрес. Проверьте правильность написания:")
        return
    user_data = await state.get_data()
    start_coords = user_data['start_coords']
    distance = calculate_distance(start_coords[0], start_coords[1], coords[0], coords[1])
    if distance < 0.1:
        await message.answer("📏 Кажется, точки слишком близко друг к другу. Введите другой адрес:")
        return
    await message.answer("🔄 Рассчитываю оптимальные маршруты и цены...")
    car_speed = 30
    duration_minutes_car = max(3, round((distance / car_speed) * 60))
    duration_minutes_scooter = max(3, round((distance / TARIFS["scooter"]["speed_kmh"]) * 60))
    cost_taxi = round(TARIFS["taxi_economy"]["base"] + (distance * TARIFS["taxi_economy"]["per_km"]) + (duration_minutes_car * TARIFS["taxi_economy"]["per_min"]))

cost_scooter = round(TARIFS["scooter"]["base"] + (duration_minutes_scooter * TARIFS["scooter"]["per_min"]))
    cost_carshare = round(TARIFS["carsharing"]["base"] + (duration_minutes_car * TARIFS["carsharing"]["per_min"]))
    report = (
        f"📊 Анализ маршрута:\n"
        f"🛣️ Расстояние по дорогам: ~{distance} км\n\n"
        f"⏱️ Время в пути на авто: ~{duration_minutes_car} мин\n"
        f"⏱️ Время на самокате: ~{duration_minutes_scooter} min\n\n"
        f"💰 Сравнение ориентировочной стоимости:\n"
        f"{TARIFS['taxi_economy']['name']}: ~{cost_taxi} ₽\n"
        f"{TARIFS['carsharing']['name']}: ~{cost_carshare} ₽\n"
        f"{TARIFS['scooter']['name']}: ~{cost_scooter} ₽\n\n"
        f"💡 *Где выгоднее:* Выбирайте "
        f"{'🛴 самокат' if cost_scooter < cost_taxi and distance <= 5 else '🚕 такси'}, чтобы сэкономить!"
    )
    await message.answer(report, parse_mode="Markdown")
    await state.clear()

async def main():
    await dp.start_polling(bot)

if name == "main":
    asyncio.run(main())
