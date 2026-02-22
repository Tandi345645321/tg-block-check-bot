#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import io
import json
import time
import os
from datetime import datetime

import requests
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ===== ТОКЕН =====
# Берём токен из переменной окружения (так безопаснее)
TOKEN = os.environ.get('TELEGRAM_TOKEN', '8403715390:AAEdo8Tbl6Ns70X27CbLGBxjg5S_u3ctwzY')
# =================

logger = logging.getLogger(__name__)

# Список стран для проверки
LOCATIONS = [
    {"country": "RU", "name": "🇷🇺 Россия"},
    {"country": "US", "name": "🇺🇸 США"},
    {"country": "DE", "name": "🇩🇪 Германия"},
    {"country": "JP", "name": "🇯🇵 Япония"},
    {"country": "BR", "name": "🇧🇷 Бразилия"},
    {"country": "AU", "name": "🇦🇺 Австралия"},
]

# Файл для хранения списка заблокированных доменов (используем /tmp, так как это единственная папка для записи на Render)
BLOCKED_FILE = "/tmp/blocked.json"

def load_blocked():
    try:
        with open(BLOCKED_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_blocked(blocked_list):
    with open(BLOCKED_FILE, "w") as f:
        json.dump(blocked_list, f, indent=2)

def is_blocked(domain):
    return domain in load_blocked()

# Константы для админа и друга
CREATOR_USERNAME = "hfvjw"
FRIEND_USERNAME = "Nonkap"
FRIEND_GREETING = "АХУЕТЬ ЭТО ЖЕ АРТЁМ ЖАДОВ, ЛЮБИМЫЙ ИЗ ЛЮБИМЫХ, СПАСИБО ЧТО ТЫ ЕСТЬ, ТЕБЯ МЫ ВСЕ ЛЮБИМ, ПОЛЬЗУЙСЯ НА ЗДОРОВЬЕ, Я ТЕБЯ ЛЮБЛЮ"

friend_greeted = set()

# ---------- Основные функции бота ----------
async def check_site_global(domain: str):
    results = []
    for loc in LOCATIONS:
        payload = {
            "type": "http",
            "target": domain,
            "locations": [{"country": loc["country"]}],
            "measurementOptions": {
                "protocol": "HTTPS",
                "port": 443,
                "request": {"path": "/", "method": "HEAD"},
            },
        }
        try:
            resp = requests.post(
                "https://api.globalping.io/v1/measurements",
                json=payload,
                timeout=15,
            )
            if resp.status_code != 202:
                results.append({
                    "country": loc["country"],
                    "status": "⚠️ Ошибка создания",
                    "response_time": 0,
                    "error": f"HTTP {resp.status_code}",
                })
                continue
            data = resp.json()
            measurement_id = data["id"]
            time.sleep(3)
            result_resp = requests.get(
                f"https://api.globalping.io/v1/measurements/{measurement_id}",
                timeout=10,
            )
            if result_resp.status_code != 200:
                results.append({
                    "country": loc["country"],
                    "status": "⚠️ Нет результатов",
                    "response_time": 0,
                    "error": f"HTTP {result_resp.status_code}",
                })
                continue
            result_data = result_resp.json()
            if "results" in result_data and len(result_data["results"]) > 0:
                probe_result = result_data["results"][0]
                status = "✅ Доступен" if probe_result.get("status") == "finished" else "❌ Недоступен"
                timings = probe_result.get("timings", {})
                response_time = timings.get("total", 0)
                results.append({
                    "country": loc["country"],
                    "status": status,
                    "response_time": response_time,
                    "error": probe_result.get("error"),
                })
            else:
                results.append({
                    "country": loc["country"],
                    "status": "⚠️ Нет данных",
                    "response_time": 0,
                    "error": "Пустой ответ",
                })
        except Exception as e:
            logger.error(f"Ошибка при проверке {loc['country']}: {e}")
            results.append({
                "country": loc["country"],
                "status": "⚠️ Ошибка",
                "response_time": 0,
                "error": str(e)[:50],
            })
    return results

def create_status_chart(results, domain, is_rkn_blocked=False):
    countries = []
    status_colors = []
    response_times = []
    country_names = {loc["country"]: loc["name"] for loc in LOCATIONS}
    for r in results:
        country = country_names.get(r["country"], r["country"])
        countries.append(country)
        response_times.append(r["response_time"] / 1000)
        if "✅" in r["status"]:
            status_colors.append("#2ecc71")
        elif "❌" in r["status"]:
            status_colors.append("#e74c3c")
        else:
            status_colors.append("#f39c12")
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
    fig.suptitle(f"🌐 Доступность сайта {domain}", fontsize=16, fontweight='bold')
    
    ax1.bar(countries, [1] * len(countries), color=status_colors, alpha=0.8, edgecolor='black', linewidth=1)
    ax1.set_ylim(0, 1.5)
    ax1.set_ylabel("Статус", fontsize=12)
    ax1.set_title("🟢 доступен  🔴 недоступен  🟠 ошибка проверки", fontsize=11)
    ax1.tick_params(axis="x", rotation=45)
    ax1.set_yticks([])
    
    bars = ax2.bar(countries, response_times, color="#3498db", alpha=0.8, edgecolor='black', linewidth=1)
    ax2.set_ylabel("Время отклика (сек)", fontsize=12)
    ax2.set_title("⏱️ Время загрузки (только для доступных сайтов)", fontsize=11)
    ax2.tick_params(axis="x", rotation=45)
    
    for bar, t in zip(bars, response_times):
        if t > 0:
            ax2.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.05,
                f"{t:.2f}с",
                ha="center", va="bottom", fontsize=10, fontweight='bold'
            )
    
    if is_rkn_blocked:
        fig.text(0.5, 0.01, "⚠️ Данный сайт находится в реестре заблокированных РКН", 
                 ha="center", fontsize=12, color='red', fontweight='bold')
    
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=120, bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)
    return buf

def analyze_blocking(results):
    ru_result = None
    other_results = []
    for r in results:
        if r["country"] == "RU":
            ru_result = r
        else:
            other_results.append(r)
    if not ru_result:
        return "❌ Не удалось получить данные по России"
    ru_available = "✅" in ru_result["status"]
    other_available = any("✅" in r["status"] for r in other_results)
    if not ru_available and other_available:
        working = [r["country"] for r in other_results if "✅" in r["status"]]
        country_names = {loc["country"]: loc["name"] for loc in LOCATIONS}
        working_names = [country_names.get(c, c) for c in working]
        return (
            f"⚠️ **ВЕРОЯТНАЯ БЛОКИРОВКА В РОССИИ**\n"
            f"Сайт доступен в: {', '.join(working_names)}"
        )
    elif not ru_available and not other_available:
        return "🌍 **ГЛОБАЛЬНАЯ ПРОБЛЕМА**\nСайт недоступен во всех проверенных странах"
    elif ru_available and not other_available:
        return (
            "⚠️ **СТРАННАЯ СИТУАЦИЯ**\n"
            "Сайт работает в России, но не работает в других странах"
        )
    else:
        return "✅ **ВСЁ ХОРОШО**\nСайт доступен во всех проверенных регионах"

async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Укажите домен. Например:\n/check example.com\n/check google.ru"
        )
        return
    
    domain = context.args[0].lower().strip()
    domain = domain.replace("https://", "").replace("http://", "").split("/")[0]
    
    status_msg = await update.message.reply_text(
        f"🔍 Проверяю {domain}... Это займёт около 30 секунд"
    )
    
    try:
        results = await check_site_global(domain)
        analysis = analyze_blocking(results)
        rkn_blocked = is_blocked(domain)
        chart_buf = create_status_chart(results, domain, rkn_blocked)
        
        country_names = {loc["country"]: loc["name"] for loc in LOCATIONS}
        text = f"📊 **Результаты проверки {domain}**\n\n"
        for r in results:
            name = country_names.get(r["country"], r["country"])
            time_str = f"{r['response_time']/1000:.2f}с" if r["response_time"] > 0 else "—"
            text += f"{name}: {r['status']} ({time_str})\n"
        text += f"\n{analysis}"
        if rkn_blocked:
            text += "\n\n⚠️ **Этот сайт находится в реестре заблокированных РКН**"
        text += f"\n\n🕒 Проверка: {datetime.now().strftime('%H:%M:%S')}"
        
        await status_msg.delete()
        await update.message.reply_photo(
            photo=chart_buf,
            caption=text,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.exception("Ошибка в check_command")
        await status_msg.edit_text(f"❌ Ошибка при проверке: {str(e)}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    username = user.username
    
    # Приветствие для друга
    if username and username.lower() == FRIEND_USERNAME.lower():
        if user.id not in friend_greeted:
            friend_greeted.add(user.id)
            await update.message.reply_text(FRIEND_GREETING)
            return
    
    await update.message.reply_text(
        "👋 Привет! Я бот для проверки доступности сайтов.\n\n"
        "/check <домен> — проверить доступность сайта по всему миру\n"
        "/admin — админ-меню (для создателя)"
    )

# ---------- Админские команды ----------
async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user.username or user.username.lower() != CREATOR_USERNAME.lower():
        await update.message.reply_text("У вас нет прав администратора.")
        return
    
    text = (
        "🔧 **Админ-меню**\n\n"
        "Доступные команды:\n"
        "/blocklist — показать список заблокированных сервисов\n"
        "/blockadd <домен> — добавить домен в список РКН\n"
        "/blockdel <домен> — удалить домен из списка"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def blocklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user.username or user.username.lower() != CREATOR_USERNAME.lower():
        await update.message.reply_text("У вас нет прав администратора.")
        return
    
    blocked = load_blocked()
    if not blocked:
        await update.message.reply_text("Список заблокированных сервисов пуст.")
    else:
        text = "🚫 **Список заблокированных сервисов (РКН):**\n\n" + "\n".join(f"• {d}" for d in blocked)
        await update.message.reply_text(text, parse_mode="Markdown")

async def blockadd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user.username or user.username.lower() != CREATOR_USERNAME.lower():
        await update.message.reply_text("У вас нет прав администратора.")
        return
    
    if not context.args:
        await update.message.reply_text("Укажите домен. Пример: /blockadd telegram.org")
        return
    
    domain = context.args[0].lower().strip()
    blocked = load_blocked()
    if domain not in blocked:
        blocked.append(domain)
        save_blocked(blocked)
        await update.message.reply_text(f"✅ Домен {domain} добавлен в список заблокированных.")
    else:
        await update.message.reply_text(f"ℹ️ Домен {domain} уже есть в списке.")

async def blockdel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user.username or user.username.lower() != CREATOR_USERNAME.lower():
        await update.message.reply_text("У вас нет прав администратора.")
        return
    
    if not context.args:
        await update.message.reply_text("Укажите домен. Пример: /blockdel telegram.org")
        return
    
    domain = context.args[0].lower().strip()
    blocked = load_blocked()
    if domain in blocked:
        blocked.remove(domain)
        save_blocked(blocked)
        await update.message.reply_text(f"✅ Домен {domain} удалён из списка заблокированных.")
    else:
        await update.message.reply_text(f"❌ Домен {domain} не найден в списке.")

# ---------- Запуск бота ----------
def run_bot():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("check", check_command))
    app.add_handler(CommandHandler("admin", admin_menu))
    app.add_handler(CommandHandler("blocklist", blocklist))
    app.add_handler(CommandHandler("blockadd", blockadd))
    app.add_handler(CommandHandler("blockdel", blockdel))
    
    logger.info("🤖 Бот запущен и слушает команды...")
    app.run_polling()