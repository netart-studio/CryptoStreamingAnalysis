from dash import Dash, dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objs as go
from clickhouse_driver import Client
import pandas as pd
import os
import time
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ClickHouse Config
CLICKHOUSE_HOST = os.getenv('CLICKHOUSE_HOST', 'clickhouse')
CLICKHOUSE_PORT = int(os.getenv('CLICKHOUSE_PORT', '9000'))
CLICKHOUSE_DB = os.getenv('CLICKHOUSE_DATABASE', 'crypto')
CLICKHOUSE_USER = os.getenv('CLICKHOUSE_USER', 'default')
CLICKHOUSE_PASSWORD = os.getenv('CLICKHOUSE_PASSWORD', '')

# Initialize ClickHouse client
client = Client(
    host=CLICKHOUSE_HOST,
    port=CLICKHOUSE_PORT,
    database=CLICKHOUSE_DB,
    user=CLICKHOUSE_USER,
    password=CLICKHOUSE_PASSWORD
)

# Test connection
try:
    result = client.execute('SELECT 1')
    logger.info(f"ClickHouse connection test successful: {result}")
except Exception as e:
    logger.error(f"ClickHouse connection error: {str(e)}")
    raise

# Dash App
app = Dash(__name__)

app.layout = html.Div([
    html.H1("Binance BTC/USDT Realtime Price"),
    html.Div(id='debug-info', style={'margin': '20px'}),
    dcc.Graph(id='live-graph'),
    dcc.Interval(id='interval', interval=1000, n_intervals=0)
])

@app.callback(
    [Output('live-graph', 'figure'),
     Output('debug-info', 'children')],
    [Input('interval', 'n_intervals')]
)
def update_graph(n):
    debug_info = []
    start_time = time.time()
    
    try:
        # Get data
        query = "SELECT window_start, price FROM binance_trades WHERE symbol = 'BTCUSDT' ORDER BY window_start DESC LIMIT 100"
        debug_info.append(f"Executing query: {query}")
        
        data = client.execute(query)
        query_time = time.time() - start_time
        debug_info.append(f"Query executed in {query_time:.2f}s, got {len(data)} rows")
        
        if not data:
            debug_info.append("No data returned from query")
            return go.Figure(), html.Pre('\n'.join(debug_info))
        
        # Create DataFrame
        df = pd.DataFrame(data, columns=['time', 'price'])
        df = df.sort_values('time')
        debug_info.append(f"Created DataFrame with {len(df)} rows")
        
        # Create figure
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df['time'],
            y=df['price'],
            name='BTC/USDT Price',
            mode='lines',
            line=dict(color='blue')
        ))
        
        fig.update_layout(
            title='BTC/USDT Real-time Price',
            xaxis_title='Time',
            yaxis_title='Price (USDT)',
            hovermode='x unified',
            template='plotly_dark'
        )
        
        total_time = time.time() - start_time
        debug_info.append(f"Graph updated in {total_time:.2f}s")
        return fig, html.Pre('\n'.join(debug_info))
        
    except Exception as e:
        logger.error(f"Error updating graph: {str(e)}")
        debug_info.append(f"Error: {str(e)}")
        return go.Figure(), html.Pre('\n'.join(debug_info))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8050, debug=True)