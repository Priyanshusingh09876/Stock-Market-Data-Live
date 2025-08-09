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
