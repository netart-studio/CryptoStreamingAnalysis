import os
from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, avg, window, to_timestamp
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, LongType, TimestampType
from clickhouse_driver import Client

def ensure_clickhouse_table(spark):
    """
    Создает таблицу в ClickHouse через clickhouse-driver
    """
    # Получение параметров подключения из переменных окружения
    clickhouse_host = os.getenv("CLICKHOUSE_HOST", "clickhouse")
    clickhouse_port = os.getenv("CLICKHOUSE_PORT", "9000")
    clickhouse_database = os.getenv("CLICKHOUSE_DATABASE", "crypto")
    clickhouse_user = os.getenv("CLICKHOUSE_USER", "default")
    clickhouse_password = os.getenv("CLICKHOUSE_PASSWORD", "")

    create_query = """
    CREATE TABLE IF NOT EXISTS crypto.binance_trades (
        window_start DateTime,
        symbol String,
        price Float64,
        trade_time DateTime
    ) ENGINE = MergeTree()
    ORDER BY (window_start, symbol)
    """
    
    try:
        client = Client(
            host=clickhouse_host,
            port=int(clickhouse_port),
            database=clickhouse_database,
            user=clickhouse_user,
            password=clickhouse_password
        )
        client.execute(create_query)
        print("Таблица успешно создана или уже существует")
    except Exception as e:
        print(f"Ошибка при создании таблицы: {str(e)}")

# Инициализация Spark
spark = SparkSession.builder \
    .appName("BinanceStreaming") \
    .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0") \
    .getOrCreate()

# Проверяем и создаем таблицу
ensure_clickhouse_table(spark)

# Схема данных Kafka
schema = StructType([
    StructField("symbol", StringType(), True),
    StructField("price", DoubleType(), True),
    StructField("trade_time", LongType(), True)
])

# Чтение данных из Kafka
df = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "kafka:29092") \
    .option("subscribe", "binance_trades") \
    .option("startingOffsets", "earliest") \
    .load()

# Преобразование данных
parsed_df = df.select(
    from_json(col("value").cast("string"), schema).alias("data")
).select(
    col("data.symbol"),
    col("data.price"),
    to_timestamp(col("data.trade_time") / 1000).alias("trade_time")  # Convert milliseconds to seconds
)

# Агрегация по временному окну (10 секунд)
windowed_df = parsed_df \
    .withWatermark("trade_time", "10 seconds") \
    .groupBy(
        window(col("trade_time"), "10 seconds"),
        col("symbol")
    ) \
    .agg(
        avg("price").alias("price")
    )

# Запись данных в ClickHouse
def write_to_clickhouse(df, epoch_id):
    # Получение параметров подключения из переменных окружения
    clickhouse_host = os.getenv("CLICKHOUSE_HOST", "clickhouse")
    clickhouse_port = os.getenv("CLICKHOUSE_PORT", "9000")
    clickhouse_database = os.getenv("CLICKHOUSE_DATABASE", "crypto")
    clickhouse_user = os.getenv("CLICKHOUSE_USER", "default")
    clickhouse_password = os.getenv("CLICKHOUSE_PASSWORD", "")

    client = Client(
        host=clickhouse_host,
        port=int(clickhouse_port),
        database=clickhouse_database,
        user=clickhouse_user,
        password=clickhouse_password
    )
    
    # Запись данных
    if df.count() > 0:
        pdf = df.toPandas()
        data = [
            (row.window.start, row.symbol, row.price, row.window.start)
            for _, row in pdf.iterrows()
        ]
        client.execute(
            "INSERT INTO crypto.binance_trades (window_start, symbol, price, trade_time) VALUES",
            data
        )

# Запуск стриминга
query = windowed_df.writeStream \
    .foreachBatch(write_to_clickhouse) \
    .outputMode("update") \
    .start()

query.awaitTermination()