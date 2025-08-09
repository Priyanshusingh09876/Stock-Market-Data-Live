#!/bin/bash

# Complete Setup Script for Market Data Pipeline
# This script creates all necessary files and folders

echo "🚀 Starting Market Data Pipeline Setup..."
echo "========================================"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker Desktop first!"
    exit 1
fi

echo "✅ Docker is running"

# Create all directories
echo "📁 Creating project structure..."
mkdir -p services/api-gateway/{src,tests}
mkdir -p services/market-feed-generator/{src,tests}
mkdir -p database
mkdir -p .vscode

# ==========================================
# Create Docker Compose file
# ==========================================
echo "🐳 Creating docker-compose.yml..."
cat > docker-compose.yml << 'DOCKEREOF'
version: '3.8'

services:
  # Redis for pub/sub messaging
  redis:
    image: redis:7-alpine
    container_name: market-redis
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
    networks:
      - market-network

  # PostgreSQL with TimescaleDB for time-series data
  timescaledb:
    image: timescale/timescaledb:latest-pg15
    container_name: market-db
    environment:
      POSTGRES_DB: marketdata
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres123
    ports:
      - "5432:5432"
    volumes:
      - ./database/init.sql:/docker-entrypoint-initdb.d/init.sql
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - market-network

  # API Gateway - FastAPI application
  api-gateway:
    build: ./services/api-gateway
    container_name: market-api
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://postgres:postgres123@timescaledb:5432/marketdata
      REDIS_URL: redis://redis:6379
    depends_on:
      redis:
        condition: service_healthy
      timescaledb:
        condition: service_healthy
    volumes:
      - ./services/api-gateway:/app
    networks:
      - market-network
    restart: unless-stopped

  # Market Data Generator - Simulates real-time market data
  market-generator:
    build: ./services/market-feed-generator
    container_name: market-generator
    environment:
      REDIS_URL: redis://redis:6379
    depends_on:
      redis:
        condition: service_healthy
    volumes:
      - ./services/market-feed-generator:/app
    networks:
      - market-network
    restart: unless-stopped

networks:
  market-network:
    driver: bridge

volumes:
  postgres_data:
DOCKEREOF

# ==========================================
# Create API Gateway Service
# ==========================================
echo "🔧 Creating API Gateway service..."

# API Gateway Dockerfile
cat > services/api-gateway/Dockerfile << 'DOCKEREOF'
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Run the application
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
DOCKEREOF

# API Gateway requirements.txt
cat > services/api-gateway/requirements.txt << 'REQEOF'
fastapi==0.109.0
uvicorn[standard]==0.27.0
asyncpg==0.29.0
redis==5.0.1
websockets==12.0
pydantic==2.5.3
python-multipart==0.0.6
httpx==0.26.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
REQEOF

# API Gateway main application
cat > services/api-gateway/src/main.py << 'PYEOF'
from fastapi import FastAPI, WebSocket, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import asyncpg
import redis.asyncio as redis
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import asyncio
import random

app = FastAPI(
    title="Market Data Pipeline API",
    description="Real-time market data streaming service",
    version="1.0.0"
)

# Enable CORS for web clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global connections
redis_client = None
db_pool = None

# HTML page for testing WebSocket
html = """
<!DOCTYPE html>
<html>
<head>
    <title>Market Data Stream</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #1a1a1a; color: #fff; }
        h1 { color: #4CAF50; }
        #messages { 
            background: #2a2a2a; 
            padding: 10px; 
            height: 400px; 
            overflow-y: auto; 
            border: 1px solid #4CAF50;
            border-radius: 5px;
            margin: 20px 0;
        }
        .message { padding: 5px; margin: 5px 0; background: #3a3a3a; border-radius: 3px; }
        .controls { margin: 20px 0; }
        button { 
            background: #4CAF50; 
            color: white; 
            padding: 10px 20px; 
            border: none; 
            border-radius: 5px; 
            cursor: pointer;
            margin-right: 10px;
        }
        button:hover { background: #45a049; }
        select { 
            padding: 10px; 
            border-radius: 5px;
            background: #2a2a2a;
            color: white;
            border: 1px solid #4CAF50;
        }
    </style>
</head>
<body>
    <h1>🚀 Market Data Live Stream</h1>
    <div class="controls">
        <select id="symbol">
            <option value="AAPL">Apple (AAPL)</option>
            <option value="GOOGL">Google (GOOGL)</option>
            <option value="MSFT">Microsoft (MSFT)</option>
            <option value="AMZN">Amazon (AMZN)</option>
            <option value="TSLA">Tesla (TSLA)</option>
        </select>
        <button onclick="connect()">Connect</button>
        <button onclick="disconnect()">Disconnect</button>
        <button onclick="clearMessages()">Clear</button>
    </div>
    <div id="messages"></div>
    <script>
        let ws = null;
        
        function connect() {
            const symbol = document.getElementById('symbol').value;
            ws = new WebSocket(`ws://localhost:8000/ws/${symbol}`);
            
            ws.onopen = function(event) {
                addMessage('🟢 Connected to ' + symbol);
            };
            
            ws.onmessage = function(event) {
                const data = JSON.parse(event.data);
                const time = new Date().toLocaleTimeString();
                if (data.type === 'quote') {
                    addMessage(`📊 [${time}] Quote: Bid: $${data.bid_price} Ask: $${data.ask_price}`);
                } else if (data.type === 'trade') {
                    const color = data.side === 'BUY' ? '🟢' : '🔴';
                    addMessage(`${color} [${time}] Trade: ${data.side} ${data.volume} @ $${data.price}`);
                }
            };
            
            ws.onclose = function(event) {
                addMessage('🔴 Disconnected');
            };
        }
        
        function disconnect() {
            if (ws) {
                ws.close();
            }
        }
        
        function clearMessages() {
            document.getElementById('messages').innerHTML = '';
        }
        
        function addMessage(message) {
            const messages = document.getElementById('messages');
            messages.innerHTML += '<div class="message">' + message + '</div>';
            messages.scrollTop = messages.scrollHeight;
        }
    </script>
</body>
</html>
"""

@app.on_event("startup")
async def startup_event():
    global redis_client, db_pool
    print("🚀 Starting API Gateway...")
    
    # Connect to Redis
    redis_client = await redis.from_url("redis://redis:6379")
    print("✅ Connected to Redis")
    
    # Connect to PostgreSQL
    db_pool = await asyncpg.create_pool(
        "postgresql://postgres:postgres123@timescaledb:5432/marketdata",
        min_size=5,
        max_size=20
    )
    print("✅ Connected to PostgreSQL")
    
    # Initialize database tables
    async with db_pool.acquire() as conn:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id SERIAL PRIMARY KEY,
                time TIMESTAMPTZ DEFAULT NOW(),
                symbol TEXT NOT NULL,
                price DOUBLE PRECISION,
                volume BIGINT,
                side TEXT
            );
            
            CREATE TABLE IF NOT EXISTS quotes (
                id SERIAL PRIMARY KEY,
                time TIMESTAMPTZ DEFAULT NOW(),
                symbol TEXT NOT NULL,
                bid_price DOUBLE PRECISION,
                ask_price DOUBLE PRECISION,
                bid_size BIGINT,
                ask_size BIGINT
            );
            
            CREATE INDEX IF NOT EXISTS idx_trades_symbol_time ON trades(symbol, time DESC);
            CREATE INDEX IF NOT EXISTS idx_quotes_symbol_time ON quotes(symbol, time DESC);
        ''')
    print("✅ Database tables initialized")

@app.on_event("shutdown")
async def shutdown_event():
    if redis_client:
        await redis_client.close()
    if db_pool:
        await db_pool.close()

@app.get("/", response_class=HTMLResponse)
async def root():
    return html

@app.get("/api")
async def api_info():
    return {
        "message": "Market Data Pipeline API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "quotes": "/api/quotes/{symbol}",
            "trades": "/api/trades/{symbol}",
            "symbols": "/api/symbols",
            "stats": "/api/stats/{symbol}",
            "websocket": "/ws/{symbol}",
            "test_ui": "/"
        },
        "symbols": ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA"]
    }

@app.get("/health")
async def health_check():
    try:
        # Check Redis
        await redis_client.ping()
        # Check Database
        async with db_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "services": {
                "redis": "connected",
                "database": "connected"
            }
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")

@app.get("/api/quotes/{symbol}")
async def get_quotes(
    symbol: str,
    limit: int = Query(100, le=1000)
):
    """Get recent quotes for a symbol"""
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM quotes 
            WHERE symbol = $1 
            ORDER BY time DESC 
            LIMIT $2
            """,
            symbol.upper(), limit
        )
        return [dict(row) for row in rows]

@app.get("/api/trades/{symbol}")
async def get_trades(
    symbol: str,
    limit: int = Query(100, le=1000)
):
    """Get recent trades for a symbol"""
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM trades 
            WHERE symbol = $1 
            ORDER BY time DESC 
            LIMIT $2
            """,
            symbol.upper(), limit
        )
        return [dict(row) for row in rows]

@app.get("/api/symbols")
async def get_symbols():
    """Get list of available symbols with their latest prices"""
    async with db_pool.acquire() as conn:
        rows = await conn.fetch("""
            WITH latest_trades AS (
                SELECT DISTINCT ON (symbol) 
                    symbol, price, time
                FROM trades
                ORDER BY symbol, time DESC
            )
            SELECT * FROM latest_trades
            ORDER BY symbol
        """)
        return [dict(row) for row in rows]

@app.get("/api/stats/{symbol}")
async def get_stats(symbol: str):
    """Get statistics for a symbol"""
    async with db_pool.acquire() as conn:
        stats = await conn.fetchrow("""
            SELECT 
                COUNT(*) as total_trades,
                AVG(price) as avg_price,
                MIN(price) as min_price,
                MAX(price) as max_price,
                SUM(volume) as total_volume,
                MAX(time) as last_trade_time
            FROM trades
            WHERE symbol = $1
            AND time > NOW() - INTERVAL '1 hour'
        """, symbol.upper())
        
        return dict(stats) if stats else {}

@app.websocket("/ws/{symbol}")
async def websocket_endpoint(websocket: WebSocket, symbol: str):
    """WebSocket endpoint for real-time market data streaming"""
    await websocket.accept()
    print(f"WebSocket connected for {symbol}")
    
    # Subscribe to Redis channel
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(f"market:{symbol}")
    
    try:
        while True:
            # Get message from Redis
            message = await pubsub.get_message(ignore_subscribe_messages=True)
            if message and message['data']:
                data = message['data'].decode('utf-8')
                await websocket.send_text(data)
                
                # Also save to database
                parsed_data = json.loads(data)
                async with db_pool.acquire() as conn:
                    if parsed_data['type'] == 'trade':
                        await conn.execute(
                            """
                            INSERT INTO trades (symbol, price, volume, side, time)
                            VALUES ($1, $2, $3, $4, $5)
                            """,
                            symbol, parsed_data['price'], parsed_data['volume'],
                            parsed_data['side'], datetime.fromisoformat(parsed_data['timestamp'])
                        )
                    elif parsed_data['type'] == 'quote':
                        await conn.execute(
                            """
                            INSERT INTO quotes (symbol, bid_price, ask_price, bid_size, ask_size, time)
                            VALUES ($1, $2, $3, $4, $5, $6)
                            """,
                            symbol, parsed_data['bid_price'], parsed_data['ask_price'],
                            parsed_data['bid_size'], parsed_data['ask_size'],
                            datetime.fromisoformat(parsed_data['timestamp'])
                        )
            
            await asyncio.sleep(0.01)
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        await pubsub.unsubscribe(f"market:{symbol}")
        await websocket.close()
PYEOF

# ==========================================
# Create Market Feed Generator Service
# ==========================================
echo "📈 Creating Market Feed Generator service..."

# Market Generator Dockerfile
cat > services/market-feed-generator/Dockerfile << 'DOCKEREOF'
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Run the application
CMD ["python", "src/main.py"]
DOCKEREOF

# Market Generator requirements.txt
cat > services/market-feed-generator/requirements.txt << 'REQEOF'
redis==5.0.1
pydantic==2.5.3
REQEOF

# Market Generator main application
cat > services/market-feed-generator/src/main.py << 'PYEOF'
import asyncio
import random
import json
from datetime import datetime
import redis.asyncio as redis
import signal
import sys

class MarketDataGenerator:
    def __init__(self):
        self.redis_client = None
        self.running = True
        self.symbols = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA"]
        
        # Starting prices for each symbol
        self.base_prices = {
            "AAPL": 175.0,
            "GOOGL": 140.0,
            "MSFT": 380.0,
            "AMZN": 170.0,
            "TSLA": 240.0
        }
        
        # Volatility for each symbol (affects price movement)
        self.volatility = {
            "AAPL": 0.002,
            "GOOGL": 0.003,
            "MSFT": 0.002,
            "AMZN": 0.003,
            "TSLA": 0.005  # Tesla is more volatile
        }
        
    async def connect(self):
        """Connect to Redis"""
        try:
            self.redis_client = await redis.from_url("redis://redis:6379")
            await self.redis_client.ping()
            print("✅ Connected to Redis")
        except Exception as e:
            print(f"❌ Failed to connect to Redis: {e}")
            await asyncio.sleep(5)
            await self.connect()
    
    def generate_quote(self, symbol):
        """Generate a realistic quote"""
        base_price = self.base_prices[symbol]
        
        # Create bid-ask spread
        spread_percentage = random.uniform(0.0001, 0.0005)  # 0.01% to 0.05% spread
        mid_price = base_price
        half_spread = mid_price * spread_percentage / 2
        
        bid_price = round(mid_price - half_spread, 2)
        ask_price = round(mid_price + half_spread, 2)
        
        # Generate realistic sizes
        bid_size = random.randint(1, 50) * 100
        ask_size = random.randint(1, 50) * 100
        
        return {
            "type": "quote",
            "symbol": symbol,
            "bid_price": bid_price,
            "ask_price": ask_price,
            "bid_size": bid_size,
            "ask_size": ask_size,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def generate_trade(self, symbol):
        """Generate a realistic trade"""
        base_price = self.base_prices[symbol]
        
        # Trade happens near the current price
        price_change = random.uniform(-0.001, 0.001)
        trade_price = round(base_price * (1 + price_change), 2)
        
        # Volume follows a power law distribution (most trades are small)
        volume = int(random.paretovariate(1.5) * 100) * 100
        volume = min(volume, 10000)  # Cap at 10,000 shares
        
        # Determine side based on price movement
        side = "BUY" if random.random() > 0.5 else "SELL"
        
        return {
            "type": "trade",
            "symbol": symbol,
            "price": trade_price,
            "volume": volume,
            "side": side,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def update_price(self, symbol):
        """Update base price with random walk"""
        volatility = self.volatility[symbol]
        change = random.gauss(0, volatility)
        
        # Add slight upward bias for bull market simulation
        bias = 0.0001
        change += bias
        
        # Update price
        self.base_prices[symbol] *= (1 + change)
        
        # Add occasional jumps (news events)
        if random.random() < 0.001:  # 0.1% chance of jump
            jump = random.uniform(-0.02, 0.02)  # ±2% jump
            self.base_prices[symbol] *= (1 + jump)
            print(f"📰 News event! {symbol} jumped {jump*100:.2f}%")
    
    async def generate_market_data(self):
        """Main loop to generate market data"""
        print("📊 Starting market data generation...")
        print(f"📈 Generating data for: {', '.join(self.symbols)}")
        
        while self.running:
            try:
                # Generate data for each symbol
                for symbol in self.symbols:
                    # Always generate quotes
                    quote = self.generate_quote(symbol)
                    await self.redis_client.publish(
                        f"market:{symbol}",
                        json.dumps(quote)
                    )
                    
                    # Generate trades with varying probability
                    # More trades during "market hours"
                    trade_probability = 0.7
                    if random.random() < trade_probability:
                        trade = self.generate_trade(symbol)
                        await self.redis_client.publish(
                            f"market:{symbol}",
                            json.dumps(trade)
                        )
                        
                        # Update base price after trade
                        self.base_prices[symbol] = trade['price']
                    
                    # Random walk the price
                    self.update_price(symbol)
                
                # Variable sleep to simulate market activity
                await asyncio.sleep(random.uniform(0.1, 1.0))
                
            except Exception as e:
                print(f"❌ Error generating data: {e}")
                await asyncio.sleep(1)
    
    def signal_handler(self, sig, frame):
        """Handle shutdown gracefully"""
        print("\n🛑 Shutting down market data generator...")
        self.running = False
        sys.exit(0)
    
    async def run(self):
        """Run the market data generator"""
        # Setup signal handler for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        # Connect to Redis
        await self.connect()
        
        # Start generating market data
        await self.generate_market_data()

async def main():
    generator = MarketDataGenerator()
    await generator.run()

if __name__ == "__main__":
    print("🚀 Market Data Generator Starting...")
    asyncio.run(main())
PYEOF

# ==========================================
# Create Database Initialization Script
# ==========================================
echo "💾 Creating database initialization script..."
cat > database/init.sql << 'SQLEOF'
-- Market Data Pipeline Database Initialization

-- Enable TimescaleDB extension (if available)
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- Create tables for market data
CREATE TABLE IF NOT EXISTS trades (
    id SERIAL PRIMARY KEY,
    time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    symbol TEXT NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    volume BIGINT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('BUY', 'SELL'))
);

CREATE TABLE IF NOT EXISTS quotes (
    id SERIAL PRIMARY KEY,
    time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    symbol TEXT NOT NULL,
    bid_price DOUBLE PRECISION NOT NULL,
    ask_price DOUBLE PRECISION NOT NULL,
    bid_size BIGINT NOT NULL,
    ask_size BIGINT NOT NULL
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_trades_symbol_time ON trades(symbol, time DESC);
CREATE INDEX IF NOT EXISTS idx_quotes_symbol_time ON quotes(symbol, time DESC);
CREATE INDEX IF NOT EXISTS idx_trades_time ON trades(time DESC);
CREATE INDEX IF NOT EXISTS idx_quotes_time ON quotes(time DESC);

-- Create hypertables if TimescaleDB is available
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
        PERFORM create_hypertable('trades', 'time', if_not_exists => TRUE);
        PERFORM create_hypertable('quotes', 'time', if_not_exists => TRUE);
    END IF;
END$$;

-- Insert some sample data for testing
INSERT INTO trades (symbol, price, volume, side) VALUES
    ('AAPL', 175.50, 100, 'BUY'),
    ('GOOGL', 140.25, 200, 'SELL'),
    ('MSFT', 380.00, 150, 'BUY')
ON CONFLICT DO NOTHING;

INSERT INTO quotes (symbol, bid_price, ask_price, bid_size, ask_size) VALUES
    ('AAPL', 175.45, 175.55, 500, 600),
    ('GOOGL', 140.20, 140.30, 300, 400),
    ('MSFT', 379.95, 380.05, 200, 250)
ON CONFLICT DO NOTHING;

-- Create a view for latest prices
CREATE OR REPLACE VIEW latest_prices AS
SELECT DISTINCT ON (symbol)
    symbol,
    price as last_price,
    volume as last_volume,
    side as last_side,
    time as last_trade_time
FROM trades
ORDER BY symbol, time DESC;

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO postgres;
SQLEOF

# ==========================================
# Create VS Code Configuration
# ==========================================
echo "⚙️ Creating VS Code configuration..."

# VS Code launch.json for debugging
cat > .vscode/launch.json << 'VSCODEEOF'
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Start All Services",
            "type": "node",
            "request": "launch",
            "runtimeExecutable": "docker-compose",
            "runtimeArgs": ["up"],
            "console": "integratedTerminal",
            "internalConsoleOptions": "neverOpen"
        },
        {
            "name": "Stop All Services",
            "type": "node",
            "request": "launch",
            "runtimeExecutable": "docker-compose",
            "runtimeArgs": ["down"],
            "console": "integratedTerminal"
        }
    ]
}
VSCODEEOF

# VS Code tasks.json for quick commands
cat > .vscode/tasks.json << 'VSCODEEOF'
{
    "version": "2.0.0",
    "tasks": [
        {
            "label": "Start Services",
            "type": "shell",
            "command": "docker-compose up -d",
            "problemMatcher": [],
            "group": {
                "kind": "build",
                "isDefault": true
            }
        },
        {
            "label": "Stop Services",
            "type": "shell",
            "command": "docker-compose down",
            "problemMatcher": []
        },
        {
            "label": "View Logs",
            "type": "shell",
            "command": "docker-compose logs -f",
            "problemMatcher": []
        },
        {
            "label": "Restart Services",
            "type": "shell",
            "command": "docker-compose restart",
            "problemMatcher": []
        },
        {
            "label": "Build Services",
            "type": "shell",
            "command": "docker-compose build --no-cache",
            "problemMatcher": []
        },
        {
            "label": "Check Health",
            "type": "shell",
            "command": "curl http://localhost:8000/health",
            "problemMatcher": []
        }
    ]
}
VSCODEEOF

# ==========================================
# Create README
# ==========================================
echo "📚 Creating README..."
cat > README.md << 'READMEEOF'
# 🚀 Market Data Pipeline

Real-time market data pipeline simulator with WebSocket streaming, REST API, and time-series database.

## 📋 Prerequisites

- Docker Desktop installed and running
- VS Code (recommended)
- Port 8000, 5432, and 6379 available

## 🔧 Quick Start

### 1. Start All Services
```bash
docker-compose up -d
```

### 2. Check Health
```bash
curl http://localhost:8000/health
```

### 3. View the Dashboard
Open your browser to: http://localhost:8000

## 🌐 Available Endpoints

### Web Interface
- **Dashboard**: http://localhost:8000
- **API Info**: http://localhost:8000/api

### REST API
- `GET /health` - Service health check
- `GET /api/quotes/{symbol}` - Get recent quotes
- `GET /api/trades/{symbol}` - Get recent trades
- `GET /api/symbols` - List all symbols
- `GET /api/stats/{symbol}` - Get statistics

### WebSocket
- `ws://localhost:8000/ws/{symbol}` - Real-time market data stream

## 📊 Available Symbols
- AAPL (Apple)
- GOOGL (Google)
- MSFT (Microsoft)
- AMZN (Amazon)
- TSLA (Tesla)

## 🛠️ VS Code Integration

### Using Tasks (Recommended)
1. Press `Ctrl+Shift+P` to open Command Palette
2. Type "Tasks: Run Task"
3. Select from available tasks:
   - Start Services
   - Stop Services
   - View Logs
   - Restart Services
   - Check Health

### Using Terminal
```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# View logs
docker-compose logs -f

# Restart a service
docker-compose restart api-gateway
```

## 🔍 Monitoring

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f api-gateway
docker-compose logs -f market-generator
```

### Check Status
```bash
# See running containers
docker ps

# Check service health
curl http://localhost:8000/health
```

## 🧪 Testing the API

### Using curl
```bash
# Get quotes for Apple
curl http://localhost:8000/api/quotes/AAPL

# Get trades for Tesla
curl http://localhost:8000/api/trades/TSLA

# Get statistics
curl http://localhost:8000/api/stats/MSFT
```

### Using the Web Interface
1. Open http://localhost:8000
2. Select a symbol from dropdown
3. Click "Connect" to start streaming
4. Watch real-time data flow

## 🐳 Docker Commands

```bash
# Build images
docker-compose build

# Start in background
docker-compose up -d

# Stop and remove containers
docker-compose down

# Stop and remove everything (including volumes)
docker-compose down -v

# View resource usage
docker stats
```

## 🔧 Troubleshooting

### Port Already in Use
```bash
# Find process using port 8000
lsof -i :8000  # Mac/Linux
netstat -ano | findstr :8000  # Windows

# Change port in docker-compose.yml if needed
```

### Docker Not Running
- Make sure Docker Desktop is started
- Check Docker icon in system tray
- Run: `docker info` to verify

### Services Not Starting
```bash
# Check logs for errors
docker-compose logs api-gateway
docker-compose logs market-generator

# Rebuild services
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Database Connection Issues
```bash
# Check if database is running
docker-compose ps timescaledb

# Check database logs
docker-compose logs timescaledb

# Connect to database manually
docker exec -it market-db psql -U postgres -d marketdata
```

## 📁 Project Structure

```
market-data-pipeline/
├── services/
│   ├── api-gateway/          # FastAPI REST & WebSocket server
│   │   ├── src/
│   │   │   └── main.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   └── market-feed-generator/ # Market data simulator
│       ├── src/
│       │   └── main.py
│       ├── Dockerfile
│       └── requirements.txt
├── database/
│   └── init.sql              # Database initialization
├── .vscode/
│   ├── launch.json           # Debug configurations
│   └── tasks.json            # VS Code tasks
├── docker-compose.yml        # Service orchestration
└── README.md                 # This file
```

## 🚦 Service Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│  Market Feed    │────▶│    Redis     │────▶│   API Gateway   │
│   Generator     │     │   Pub/Sub    │     │    (FastAPI)    │
└─────────────────┘     └──────────────┘     └─────────────────┘
                               │                      │
                               ▼                      ▼
                        ┌──────────────┐     ┌─────────────────┐
                        │              │     │   WebSocket     │
                        │  TimescaleDB │     │    Clients      │
                        │  (PostgreSQL) │     └─────────────────┘
                        └──────────────┘
```

## 💡 Tips

1. **Performance**: The generator creates ~5-10 messages/second per symbol
2. **Storage**: Data is persisted in PostgreSQL/TimescaleDB
3. **Scaling**: Add more generator instances by scaling in docker-compose
4. **Monitoring**: Check `/api/stats/{symbol}` for real-time statistics

## 🛑 Cleanup

To completely remove the project:
```bash
# Stop and remove all containers, networks, volumes
docker-compose down -v

# Remove Docker images
docker rmi market-data-pipeline_api-gateway
docker rmi market-data-pipeline_market-generator
```

## 📝 License

MIT License - Feel free to use for learning and development!
READMEEOF

# ==========================================
# Create .env file
# ==========================================
echo "🔐 Creating environment file..."
cat > .env << 'ENVEOF'
# Database Configuration
DATABASE_URL=postgresql://postgres:postgres123@localhost:5432/marketdata
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres123
POSTGRES_DB=marketdata

# Redis Configuration
REDIS_URL=redis://localhost:6379

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000

# Environment
ENVIRONMENT=development
LOG_LEVEL=INFO
ENVEOF

# ==========================================
# Create test file for VS Code REST Client
# ==========================================
echo "🧪 Creating API test file..."
cat > test-api.http << 'HTTPEOF'
### Health Check
GET http://localhost:8000/health

### API Info
GET http://localhost:8000/api

### Get Apple Quotes
GET http://localhost:8000/api/quotes/AAPL

### Get Tesla Trades
GET http://localhost:8000/api/trades/TSLA

### Get All Symbols
GET http://localhost:8000/api/symbols

### Get Microsoft Statistics
GET http://localhost:8000/api/stats/MSFT

### WebSocket Test (open in browser)
# http://localhost:8000
HTTPEOF

# ==========================================
# Final Setup
# ==========================================

echo ""
echo "✅ Project setup complete!"
echo "========================================"
echo ""
echo "📋 Next Steps:"
echo ""
echo "1. Make sure Docker Desktop is running"
echo ""
echo "2. Start all services:"
echo "   docker-compose up -d"
echo ""
echo "3. Wait ~30 seconds for services to initialize"
echo ""
echo "4. Test the API:"
echo "   curl http://localhost:8000/health"
echo ""
echo "5. Open the dashboard:"
echo "   http://localhost:8000"
echo ""
echo "========================================"
echo "🎉 Your Market Data Pipeline is ready to run!"
echo ""
echo "Quick Commands:"
echo "  Start:  docker-compose up -d"
echo "  Stop:   docker-compose down"
echo "  Logs:   docker-compose logs -f"
echo "  Status: docker ps"
echo ""