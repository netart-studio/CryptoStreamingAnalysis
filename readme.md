# CryptoStreamingAnalysis

Проект для анализа потоковых данных криптовалют с использованием Apache Spark, Kafka и ClickHouse.

## Описание

Проект представляет собой систему для сбора, обработки и визуализации данных о торговле криптовалютами в реальном времени. Система состоит из нескольких компонентов:

1. **Producer** - собирает данные о сделках с Binance через WebSocket
2. **Kafka** - промежуточное хранилище для потоковых данных
3. **Spark Streaming** - обработка и агрегация данных
4. **ClickHouse** - хранение обработанных данных
5. **Dash App** - веб-интерфейс для визуализации

## Требования

- Docker 20.10+
- Docker Compose 2.0+
- 8GB RAM (минимум)
- 20GB свободного места на диске

## Версии ПО

- Python 3.9+
- Apache Spark 3.5.0
- Kafka 7.4.0
- ClickHouse latest
- Dash 2.14.2
- Plotly 5.18.0
- Pandas 2.0.3

## Архитектура

```
[Binance API] -> [Producer] -> [Kafka] -> [Spark Streaming] -> [ClickHouse] -> [Dash App]
```

### Компоненты

1. **Producer (producer.py)**
   - Подключается к Binance WebSocket API
   - Собирает данные о сделках BTC/USDT
   - Отправляет данные в Kafka

2. **Kafka**
   - Топик: binance_trades
   - Хранит сырые данные о сделках
   - Обеспечивает буферизацию данных

3. **Spark Streaming (spark_streaming.py)**
   - Читает данные из Kafka
   - Агрегирует цены по 10-секундным окнам
   - Сохраняет результаты в ClickHouse

4. **ClickHouse**
   - Таблица: crypto.binance_trades
   - Структура:
     - window_start (DateTime)
     - symbol (String)
     - price (Float64)
     - trade_time (DateTime)

5. **Dash App (dash_app.py)**
   - Веб-интерфейс на порту 8050
   - Отображает график цен в реальном времени
   - Обновляется каждую секунду

## Запуск проекта

1. Клонируйте репозиторий:
```bash
git clone <repository-url>
cd CryptoStreamingAnalysis
```

2. Создайте файл .env (опционально):
```bash
cp .env.example .env
# Отредактируйте .env при необходимости
```

3. Запустите проект:
```bash
sudo docker-compose up --build
```

4. Проверьте работу компонентов:
- Spark UI: http://localhost:8080
- Dash App: http://localhost:8050

## Настройка

### Память

В docker-compose.yml настроены следующие лимиты памяти:
- Spark Master: 1GB
- Spark Worker: 2GB
- Spark Streaming App: 2GB
- Dash App: 512MB
- Binance Producer: 512MB

При необходимости эти значения можно изменить в docker-compose.yml.

### ClickHouse

База данных создается автоматически при первом запуске. Основные параметры:
- База данных: crypto
- Пользователь: default
- Порт: 9000 (клиент), 8123 (HTTP)

### Kafka

Настроена для работы в Docker-сети:
- Внутренний порт: 29092
- Внешний порт: 9092
- Топик: binance_trades

## Мониторинг

1. **Spark UI**
   - Доступен по адресу http://localhost:8080
   - Показывает статус задач и использование ресурсов

2. **Dash App**
   - Отображает отладочную информацию
   - Показывает время выполнения запросов
   - Выводит количество полученных строк

## Устранение неполадок

1. **Проверка подключения к ClickHouse**
```bash
sudo docker-compose exec clickhouse clickhouse-client
```

2. **Проверка данных в Kafka**
```bash
sudo docker-compose exec kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic binance_trades --from-beginning
```

3. **Просмотр логов**
```bash
sudo docker-compose logs -f [service-name]
```

## Безопасность

1. Все чувствительные данные (API ключи, пароли) должны храниться в переменных окружения
2. Файл .env добавлен в .gitignore
3. Рекомендуется использовать HTTPS для внешних соединений
4. Регулярно обновляйте зависимости для исправления уязвимостей

## Разработка

1. Установите зависимости:
```bash
pip install -r requirements.txt
```

2. Для разработки Spark приложений:
```bash
pip install -r requirements-spark.txt
```

3. Тестирование:
```bash
# Добавьте тесты в директорию tests/
python -m pytest tests/
```

## Лицензия

Apache License 2.0