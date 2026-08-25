#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TELEGRAM BOT SCANNER ДЛЯ ФУТБОЛЬНОЙ СТРАТЕГИИ
Версия 1.2 (24/7 Cloud Ready + Дата и время по МСК)
"""

import time
import requests
from datetime import datetime
import pytz

# ============================================================================
# НАСТРОЙКИ И АВТОРИЗАЦИЯ
# ============================================================================
TELEGRAM_TOKEN = "8604691930:AAHrF69O3VVkamn-RB7IJGexYj86N8Dq3Uo"
TELEGRAM_CHAT_ID = "5770149140"
ODDS_API_KEY = "aa68140b05d3fb8a1619dd2bdf7286e7"

# Часовой пояс Москва
MSK_TZ = pytz.timezone("Europe/Moscow")

WEEKDAYS_RU = {
    0: "Пн", 1: "Вт", 2: "Ср", 3: "Чт", 4: "Пт", 5: "Сб", 6: "Вс"
}

# ============================================================================
# РАБОЧИЕ ЛИГИ ПО БЭКТЕСТУ
# ============================================================================
MONITORED_LEAGUES = {
    "soccer_germany_bundesliga": {"name": "Германия, Бундеслига", "strat": "2X_TB15"},
    "soccer_germany_bundesliga2": {"name": "Германия, 2. Бундеслига", "strat": "BOTH"},
    "soccer_spain_la_liga": {"name": "Испания, Ла Лига", "strat": "2X_TB15"},
    "soccer_greece_super_league": {"name": "Греция, Суперлига", "strat": "1X_TB15"},
    "soccer_turkey_super_league": {"name": "Турция, Суперлига", "strat": "1X_TB15"},
    "soccer_france_ligue_two": {"name": "Франция, Лига 2", "strat": "1X_TB15"},
}

sent_matches = set()

def send_telegram_message(text: str):
    """Отправляет сообщение в Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(f"Ошибка отправки Telegram: {e}")
        return False

def format_commence_time(utc_iso_string: str) -> str:
    """Переводит UTC дату из API в удобный формат МСК"""
    try:
        # Пример: 2026-08-28T18:30:00Z
        utc_dt = datetime.strptime(utc_iso_string, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=pytz.utc)
        msk_dt = utc_dt.astimezone(MSK_TZ)
        day_str = msk_dt.strftime("%d.%m")
        weekday = WEEKDAYS_RU.get(msk_dt.weekday(), "")
        time_str = msk_dt.strftime("%H:%M")
        return f"{day_str} ({weekday}) в {time_str} МСК"
    except Exception:
        return "Время уточняется"

def check_match_criteria(p1, px, p2, allowed_strat):
    """Проверка фильтра стратегии"""
    fav_odd = min(p1, p2)
    
    # 1. Диапазон фаворита 2.15-2.70 и ничья >= 3.25
    if not (2.15 <= fav_odd <= 2.70 and px >= 3.25):
        return None

    # 2. Определение стратегии под лигу
    is_home_fav = (p1 < p2)
    required_market = "1X + ТБ 1.5" if is_home_fav else "2X + ТБ 1.5"

    if allowed_strat == "1X_TB15" and not is_home_fav:
        return None
    if allowed_strat == "2X_TB15" and is_home_fav:
        return None

    return required_market

def scan_lines():
    """Сканирует линии букмекеров"""
    now_str = datetime.now(MSK_TZ).strftime('%Y-%m-%d %H:%M:%S')
    print(f"\n[{now_str} МСК] Проверка линий...")
    remaining_requests = "N/A"
    
    for league_key, league_info in MONITORED_LEAGUES.items():
        url = f"https://api.the-odds-api.com/v4/sports/{league_key}/odds/"
        params = {
            "apiKey": ODDS_API_KEY,
            "regions": "eu",
            "markets": "h2h",
            "oddsFormat": "decimal"
        }
        
        try:
            res = requests.get(url, params=params, timeout=15)
            if res.status_code != 200:
                print(f"  ✗ {league_info['name']}: статус {res.status_code}")
                continue
                
            games = res.json()
            remaining_requests = res.headers.get("x-requests-remaining", remaining_requests)
            
            for game in games:
                game_id = game.get("id")
                if game_id in sent_matches:
                    continue

                home_team = game.get("home_team")
                away_team = game.get("away_team")
                commence_time_raw = game.get("commence_time")
                match_time_msk = format_commence_time(commence_time_raw)

                matched_books = []

                for bookmaker in game.get("bookmakers", []):
                    b_title = bookmaker.get("title", "Букмекер")
                    markets = bookmaker.get("markets", [])
                    h2h = next((m for m in markets if m.get("key") == "h2h"), None)
                    if not h2h:
                        continue

                    outcomes = {o["name"]: float(o["price"]) for o in h2h.get("outcomes", [])}
                    p1 = outcomes.get(home_team)
                    p2 = outcomes.get(away_team)
                    px = outcomes.get("Draw")

                    if not (p1 and px and p2):
                        continue

                    market = check_match_criteria(p1, px, p2, league_info["strat"])
                    if market:
                        matched_books.append({
                            "book": b_title,
                            "p1": p1, "x": px, "p2": p2,
                            "market": market
                        })

                if matched_books:
                    sent_matches.add(game_id)
                    target_market = matched_books[0]["market"]

                    msg = f"⚽ <b>{league_info['name']}</b>\n"
                    msg += f"⚔️ <b>{home_team} — {away_team}</b>\n"
                    msg += f"📅 <b>Начало:</b> {match_time_msk}\n"
                    msg += f"🎯 Ставка: <b>{target_market}</b>\n\n"
                    msg += "📊 <b>Линия 1X2 на рынке:</b>\n"
                    for b in matched_books[:3]:
                        msg += f"▫️ {b['book']}: П1 ({b['p1']:.2f}) | X ({b['x']:.2f}) | П2 ({b['p2']:.2f})\n"
                    
                    msg += "\n📌 <i>Проверь этот матч в <b>Betcity</b> или <b>Vave</b>.</i>\n"
                    msg += "<i>Если прематч кэф от 2.00 — ставим сразу. Если ниже — ловим 2.00+ на 10-15 минуте лайва!</i>"
                    
                    if send_telegram_message(msg):
                        print(f"  ✓ Сигнал отправлен: {home_team} — {away_team} ({match_time_msk})")
                    time.sleep(1.2)

        except Exception as e:
            print(f"  ✗ Ошибка при обработке {league_key}: {e}")
            
        time.sleep(1.5)

    print(f"Осталось запросов к API: {remaining_requests}")

if __name__ == "__main__":
    print("=" * 60)
    print("БОТ-СКАНЕР ЗАПУЩЕН")
    print("=" * 60)
    
    send_telegram_message("🚀 <b>Сканер обновлен: добавлено время матчей по МСК!</b>")
    
    while True:
        try:
            scan_lines()
        except Exception as e:
            print(f"Глобальная ошибка: {e}")
        
        print("\n⏳ Следующая проверка через 30 минут...")
        time.sleep(1800)