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
