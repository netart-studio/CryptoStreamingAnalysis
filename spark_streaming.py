import os
import warnings
from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, avg, window, to_timestamp, max, min, first, last
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, LongType, TimestampType
from clickhouse_driver import Client

# Отключаем предупреждения о устаревших функциях
warnings.filterwarnings('ignore', category=DeprecationWarning)

def ensure_clickhouse_table(spark):
    """
    Creates table in ClickHouse through clickhouse-driver
    """
    # Get connection parameters from environment variables
    host = os.getenv('CLICKHOUSE_HOST', 'clickhouse')
    port = int(os.getenv('CLICKHOUSE_PORT', '9000'))
    user = os.getenv('CLICKHOUSE_USER', 'default')
    password = os.getenv('CLICKHOUSE_PASSWORD', '')
    database = os.getenv('CLICKHOUSE_DATABASE', 'crypto')
    
    # Create ClickHouse client
    client = Client(host=host, port=port, user=user, password=password, database=database)
    
    # Create table if not exists
    create_query = """
    CREATE TABLE IF NOT EXISTS crypto.trade_aggregates (
        window_start DateTime64(3),
        window_end DateTime64(3),
        symbol String,
        avg_price Float64,
        max_price Float64,
        min_price Float64,
        first_price Float64,
        last_price Float64
    ) ENGINE = MergeTree()
    ORDER BY (symbol, window_start)
    """
    
    try:
        client.execute(create_query)
        print("Table created successfully or already exists")
    except Exception as e:
        print(f"Error creating table: {str(e)}")

# Инициализация Spark с настройками для Python 3.12
spark = SparkSession.builder \
    .appName("BinanceStreaming") \
    .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0") \
    .config("spark.python.worker.reuse", "true") \
    .config("spark.sql.execution.arrow.pyspark.enabled", "true") \
    .getOrCreate()

# Проверяем и создаем таблицу
ensure_clickhouse_table(spark)

# Схема данных Kafka
schema = StructType([
    StructField("symbol", StringType(), True),
    StructField("price", DoubleType(), True),
    StructField("quantity", DoubleType(), True),
    StructField("trade_time", LongType(), True)
])

# Чтение данных из Kafka
df = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "kafka:29092") \
    .option("subscribe", "binance_trades") \
    .option("startingOffsets", "latest") \
    .option("failOnDataLoss", "false") \
    .option("maxOffsetsPerTrigger", "1000") \
    .option("kafka.group.id", "spark-streaming-group") \
    .load()

# Добавляем логирование для отладки
print("Kafka schema:", df.printSchema())

# Преобразование данных
parsed_df = df.select(
    from_json(col("value").cast("string"), schema).alias("data")
).select(
    col("data.symbol"),
    col("data.price"),
    col("data.quantity"),
    to_timestamp(col("data.trade_time") / 1000).alias("trade_time")  # Convert milliseconds to seconds
)

# Добавляем логирование для отладки
print("Parsed schema:", parsed_df.printSchema())

# Агрегация по временному окну (10 секунд)
windowed_df = parsed_df \
    .withWatermark("trade_time", "10 seconds") \
    .groupBy(
        window(col("trade_time"), "10 seconds"),
        col("symbol")
    ) \
    .agg(
        avg("price").alias("price"),
        max("price").alias("max_price"),
        min("price").alias("min_price"),
        first("price").alias("first_price"),
        last("price").alias("last_price")
    )

# Добавляем логирование для отладки
print("Windowed schema:", windowed_df.printSchema())

# Запись данных в ClickHouse
def write_to_clickhouse(batch_df, batch_id):
    # Get connection parameters from environment variables
    host = os.getenv('CLICKHOUSE_HOST', 'clickhouse')
    port = int(os.getenv('CLICKHOUSE_PORT', '9000'))
    user = os.getenv('CLICKHOUSE_USER', 'default')
    password = os.getenv('CLICKHOUSE_PASSWORD', '')
    database = os.getenv('CLICKHOUSE_DATABASE', 'crypto')
    
    # Create ClickHouse client
    client = Client(host=host, port=port, user=user, password=password, database=database)
    
    # Convert Spark DataFrame to Pandas DataFrame
    pandas_df = batch_df.toPandas()
    
    if len(pandas_df) > 0:
        print(f"Processing batch {batch_id} with {len(pandas_df)} rows")
        print("Sample data:", pandas_df.head())
        
        # Format data for batch insertion
        data = []
        for _, row in pandas_df.iterrows():
            window_start = row['window']['start']
            window_end = row['window']['end']
            symbol = row['symbol']
            avg_price = row['price']  # This is the avg price from our aggregation
            max_price = row['max_price']
            min_price = row['min_price']
            first_price = row['first_price']
            last_price = row['last_price']
            data.append((window_start, window_end, symbol, avg_price, max_price, min_price, first_price, last_price))
        
        # Insert data into ClickHouse
        try:
            client.execute(
                """
                INSERT INTO crypto.trade_aggregates 
                (window_start, window_end, symbol, avg_price, max_price, min_price, first_price, last_price) 
                VALUES
                """,
                data
            )
            print(f"Successfully wrote batch {batch_id} to ClickHouse")
        except Exception as e:
            print(f"Error writing batch {batch_id} to ClickHouse: {str(e)}")
    else:
        print(f"Batch {batch_id} is empty")

# Запуск стриминга
query = windowed_df.writeStream \
    .foreachBatch(write_to_clickhouse) \
    .outputMode("update") \
    .trigger(processingTime="10 seconds") \
    .option("checkpointLocation", "/tmp/checkpoint") \
    .start()

# Добавляем обработку ошибок
try:
    query.awaitTermination()
except KeyboardInterrupt:
    print("Получен сигнал прерывания, завершаем работу...")
    query.stop()
except Exception as e:
    print(f"Ошибка при выполнении стриминга: {str(e)}")
    query.stop()
    raise