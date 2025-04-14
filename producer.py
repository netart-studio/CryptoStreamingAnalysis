from binance import AsyncClient, BinanceSocketManager
from confluent_kafka import Producer
import asyncio
import json
import logging
import sys
from time import sleep

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Kafka Config
conf = {
    'bootstrap.servers': 'kafka:29092',  # Docker service name
    'queue.buffering.max.messages': 100000,  # Maximum number of messages in the local queue
    'queue.buffering.max.ms': 100,  # Maximum time between flushes
    'batch.num.messages': 1000,  # Maximum number of messages batched in one MessageSet
    'linger.ms': 10  # Wait time for batching
}

producer = Producer(conf)
message_count = 0
BATCH_SIZE = 1000

def delivery_callback(err, msg):
    if err:
        logging.error(f'Message delivery failed: {err}')
    else:
        global message_count
        message_count += 1
        if message_count % BATCH_SIZE == 0:
            logging.info(f'Successfully delivered {message_count} messages')

async def binance_to_kafka(symbol='BTCUSDT'):
    client = None
    try:
        client = await AsyncClient.create()
        bm = BinanceSocketManager(client)
        ts = bm.trade_socket(symbol)
        
        async with ts as tscm:
            batch_count = 0
            while True:
                try:
                    data = await tscm.recv()
                    if not data:
                        logging.warning("Received empty data from Binance")
                        continue
                        
                    # Format data for Kafka
                    message = {
                        'symbol': data.get('s', symbol),
                        'price': float(data.get('p', 0)),
                        'quantity': float(data.get('q', 0)),
                        'trade_time': data.get('T', 0)
                    }
                    
                    # Validate data
                    if message['price'] <= 0 or message['quantity'] <= 0:
                        logging.warning(f"Invalid data received: {data}")
                        continue
                        
                    # Send to Kafka with delivery callback
                    producer.produce(
                        topic='binance_trades',
                        value=json.dumps(message).encode('utf-8'),
                        callback=delivery_callback
                    )
                    
                    batch_count += 1
                    if batch_count >= BATCH_SIZE:
                        producer.flush()
                        batch_count = 0
                        await asyncio.sleep(0.1)  # Add small delay for backpressure
                    
                except Exception as e:
                    logging.error(f"Error processing message: {str(e)}")
                    logging.error(f"Raw data: {data}")
                    await asyncio.sleep(1)  # Add delay on error
                    continue
                    
    except Exception as e:
        logging.error(f"Error in binance_to_kafka: {str(e)}")
    finally:
        if client:
            await client.close_connection()

if __name__ == "__main__":
    try:
        asyncio.run(binance_to_kafka())
    except KeyboardInterrupt:
        logging.info("Producer stopped by user")
        producer.flush()  # Flush any remaining messages
    except Exception as e:
        logging.error(f"Fatal error: {str(e)}")
        producer.flush()  # Flush any remaining messages