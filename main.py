#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import logging
import threading
import time
from flask import Flask, jsonify

# Импортируем функцию запуска бота из второго файла
from telegram_bot import run_bot

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Flask-приложение для health check
app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({"status": "alive", "message": "Bot is running"})

@app.route('/health')
def health():
    return jsonify({"status": "ok"})

def run_flask():
    """Запуск Flask-сервера на порту, который задаёт Render"""
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

if __name__ == "__main__":
    # Запускаем Flask в фоновом потоке
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # Даём Flask время запуститься (чтобы Render успел получить ответ при проверке)
    time.sleep(2)

    # Запускаем бота в главном потоке
    logger.info("🚀 Запуск Telegram бота...")
    run_bot()