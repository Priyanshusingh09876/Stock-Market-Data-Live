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
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Market Data Pipeline - Terminal Interface</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        @font-face {
            font-family: 'Terminal';
            src: local('Courier New'), local('monospace');
        }

        body {
            font-family: 'Courier New', 'Terminal', monospace;
            background: #0a0a0a;
            color: #00ff41;
            min-height: 100vh;
            overflow-x: hidden;
            position: relative;
        }

        /* Matrix Rain Background */
        .matrix-rain {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
            z-index: 0;
            opacity: 0.3;
        }

        /* Scanline Effect */
        body::before {
            content: "";
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: linear-gradient(
                transparent 50%,
                rgba(0, 255, 65, 0.03) 50%
            );
            background-size: 100% 4px;
            pointer-events: none;
            z-index: 2;
            animation: scanline 8s linear infinite;
        }

        @keyframes scanline {
            0% { transform: translateY(0); }
            100% { transform: translateY(10px); }
        }

        /* CRT Screen Effect */
        .crt-effect {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
            z-index: 3;
        }

        .crt-effect::before {
            content: "";
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: radial-gradient(
                ellipse at center,
                transparent 0%,
                rgba(0, 0, 0, 0.4) 100%
            );
        }

        /* Header */
        .header {
            background: linear-gradient(180deg, rgba(0, 0, 0, 0.95) 0%, rgba(0, 20, 0, 0.9) 100%);
            padding: 20px;
            text-align: center;
            border-bottom: 2px solid #00ff41;
            position: relative;
            z-index: 10;
            box-shadow: 0 0 20px rgba(0, 255, 65, 0.5);
        }

        .header h1 {
            color: #00ff41;
            text-shadow: 
                0 0 10px #00ff41,
                0 0 20px #00ff41,
                0 0 30px #00ff41,
                0 0 40px #00ff41;
            font-size: 2.5em;
            margin-bottom: 10px;
            letter-spacing: 3px;
            animation: glow 2s ease-in-out infinite alternate;
        }

        @keyframes glow {
            from { text-shadow: 0 0 10px #00ff41, 0 0 20px #00ff41, 0 0 30px #00ff41; }
            to { text-shadow: 0 0 20px #00ff41, 0 0 30px #00ff41, 0 0 40px #00ff41; }
        }

        .header p {
            color: #00cc33;
            font-size: 0.9em;
            opacity: 0.8;
            letter-spacing: 2px;
        }

        /* Status Bar */
        .status-bar {
            display: flex;
            justify-content: space-around;
            background: rgba(0, 0, 0, 0.8);
            padding: 10px;
            border-bottom: 1px solid #00ff41;
            position: relative;
            z-index: 10;
        }

        .status-item {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 5px 15px;
            background: rgba(0, 255, 65, 0.05);
            border: 1px solid rgba(0, 255, 65, 0.2);
            border-radius: 3px;
        }

        .status-indicator {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: #00ff41;
            box-shadow: 0 0 10px #00ff41;
            animation: pulse 2s infinite;
        }

        .status-indicator.offline {
            background: #ff3333;
            box-shadow: 0 0 10px #ff3333;
            animation: none;
        }

        .status-indicator.warning {
            background: #ffaa00;
            box-shadow: 0 0 10px #ffaa00;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.5; transform: scale(0.8); }
        }

        /* Control Panel */
        .control-panel {
            background: rgba(0, 0, 0, 0.9);
            border: 1px solid #00ff41;
            padding: 15px;
            margin: 20px;
            display: flex;
            gap: 15px;
            align-items: center;
            position: relative;
            z-index: 10;
            box-shadow: 
                0 0 20px rgba(0, 255, 65, 0.3),
                inset 0 0 20px rgba(0, 255, 65, 0.1);
        }

        .control-panel select {
            background: #000;
            color: #00ff41;
            border: 1px solid #00ff41;
            padding: 8px 15px;
            font-family: inherit;
            font-size: 14px;
            cursor: pointer;
            transition: all 0.3s;
        }

        .control-panel select:hover {
            box-shadow: 0 0 10px rgba(0, 255, 65, 0.5);
        }

        .control-btn {
            background: rgba(0, 255, 65, 0.1);
            color: #00ff41;
            border: 1px solid #00ff41;
            padding: 8px 20px;
            font-family: inherit;
            font-size: 14px;
            cursor: pointer;
            transition: all 0.3s;
            text-transform: uppercase;
            letter-spacing: 1px;
            position: relative;
            overflow: hidden;
        }

        .control-btn:hover {
            background: rgba(0, 255, 65, 0.2);
            box-shadow: 0 0 15px rgba(0, 255, 65, 0.6);
            transform: translateY(-2px);
        }

        .control-btn:active {
            transform: translateY(0);
        }

        .control-btn::before {
            content: '';
            position: absolute;
            top: 50%;
            left: 50%;
            width: 0;
            height: 0;
            background: rgba(0, 255, 65, 0.5);
            border-radius: 50%;
            transform: translate(-50%, -50%);
            transition: width 0.6s, height 0.6s;
        }

        .control-btn:active::before {
            width: 300px;
            height: 300px;
        }

        /* Main Container */
        .main-container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            padding: 20px;
            height: calc(100vh - 200px);
            position: relative;
            z-index: 10;
        }

        /* Panels */
        .panel {
            background: rgba(0, 0, 0, 0.85);
            border: 1px solid #00ff41;
            border-radius: 5px;
            padding: 20px;
            overflow: hidden;
            position: relative;
            box-shadow: 
                0 0 30px rgba(0, 255, 65, 0.2),
                inset 0 0 30px rgba(0, 255, 65, 0.05);
        }

        .panel::before {
            content: '';
            position: absolute;
            top: -2px;
            left: -2px;
            right: -2px;
            bottom: -2px;
            background: linear-gradient(45deg, #00ff41, transparent, #00ff41);
            border-radius: 5px;
            opacity: 0;
            z-index: -1;
            animation: borderGlow 3s linear infinite;
        }

        @keyframes borderGlow {
            0%, 100% { opacity: 0; }
            50% { opacity: 0.5; }
        }

        .panel h2 {
            color: #00ff41;
            margin-bottom: 15px;
            text-align: center;
            text-shadow: 0 0 10px #00ff41;
            font-size: 1.3em;
            letter-spacing: 2px;
            padding-bottom: 10px;
            border-bottom: 1px solid rgba(0, 255, 65, 0.3);
        }

        /* Stock List */
        .stock-list {
            height: calc(100% - 50px);
            overflow-y: auto;
            padding-right: 10px;
        }

        .stock-list::-webkit-scrollbar {
            width: 8px;
        }

        .stock-list::-webkit-scrollbar-track {
            background: rgba(0, 255, 65, 0.1);
            border-radius: 4px;
        }

        .stock-list::-webkit-scrollbar-thumb {
            background: #00ff41;
            border-radius: 4px;
        }

        .stock-item {
            display: grid;
            grid-template-columns: 80px 1fr auto auto auto;
            gap: 15px;
            padding: 12px;
            margin-bottom: 8px;
            background: rgba(0, 255, 65, 0.05);
            border: 1px solid rgba(0, 255, 65, 0.2);
            border-radius: 3px;
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }

        .stock-item:hover {
            background: rgba(0, 255, 65, 0.15);
            transform: translateX(5px);
            box-shadow: 0 0 20px rgba(0, 255, 65, 0.3);
        }

        .stock-item::before {
            content: '';
            position: absolute;
            left: 0;
            top: 0;
            height: 100%;
            width: 3px;
            background: #00ff41;
            transform: scaleY(0);
            transition: transform 0.3s;
        }

        .stock-item:hover::before {
            transform: scaleY(1);
        }

        .stock-symbol {
            font-weight: bold;
            font-size: 1.1em;
            color: #00ff41;
            text-shadow: 0 0 5px #00ff41;
        }

        .stock-name {
            color: #00cc33;
            font-size: 0.9em;
            opacity: 0.8;
        }

        .stock-price {
            font-weight: bold;
            color: #00ff41;
            font-size: 1.1em;
        }

        .stock-change {
            font-weight: bold;
            padding: 2px 8px;
            border-radius: 3px;
            font-size: 0.9em;
        }

        .positive {
            color: #00ff00;
            background: rgba(0, 255, 0, 0.1);
            border: 1px solid rgba(0, 255, 0, 0.3);
        }

        .negative {
            color: #ff4444;
            background: rgba(255, 68, 68, 0.1);
            border: 1px solid rgba(255, 68, 68, 0.3);
        }

        /* Console */
        .console {
            height: calc(100% - 50px);
            background: #000;
            font-family: 'Courier New', monospace;
            font-size: 0.85em;
            overflow-y: auto;
            padding: 15px;
            border: 1px solid rgba(0, 255, 65, 0.2);
            border-radius: 3px;
        }

        .console::-webkit-scrollbar {
            width: 8px;
        }

        .console::-webkit-scrollbar-track {
            background: rgba(0, 255, 65, 0.1);
        }

        .console::-webkit-scrollbar-thumb {
            background: #00ff41;
            border-radius: 4px;
        }

        .console-line {
            margin-bottom: 5px;
            opacity: 0;
            animation: fadeIn 0.5s ease-in forwards;
            font-size: 0.9em;
            line-height: 1.4;
        }

        @keyframes fadeIn {
            to { opacity: 1; }
        }

        .timestamp {
            color: #666;
            margin-right: 10px;
        }

        .system-msg {
            color: #00ff41;
        }

        .trade-msg {
            color: #00ccff;
        }

        .quote-msg {
            color: #ffaa00;
        }

        .error-msg {
            color: #ff4444;
        }

        /* Stats Dashboard */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 15px;
            margin: 20px;
            position: relative;
            z-index: 10;
        }

        .stat-card {
            background: rgba(0, 0, 0, 0.9);
            border: 1px solid #00ff41;
            padding: 15px;
            text-align: center;
            position: relative;
            overflow: hidden;
        }

        .stat-card::after {
            content: '';
            position: absolute;
            bottom: 0;
            left: 0;
            width: 100%;
            height: 2px;
            background: linear-gradient(90deg, transparent, #00ff41, transparent);
            animation: slide 3s linear infinite;
        }

        @keyframes slide {
            0% { transform: translateX(-100%); }
            100% { transform: translateX(100%); }
        }

        .stat-value {
            font-size: 1.8em;
            font-weight: bold;
            color: #00ff41;
            text-shadow: 0 0 10px #00ff41;
            margin-bottom: 5px;
        }

        .stat-label {
            font-size: 0.8em;
            color: #00cc33;
            text-transform: uppercase;
            letter-spacing: 1px;
            opacity: 0.8;
        }

        /* Easter Egg */
        .easter-egg {
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: rgba(0, 0, 0, 0.98);
            border: 2px solid #00ff41;
            border-radius: 10px;
            padding: 30px;
            text-align: center;
            z-index: 1000;
            display: none;
            max-width: 500px;
            box-shadow: 0 0 50px rgba(0, 255, 65, 0.5);
            animation: eggAppear 0.5s ease;
        }

        @keyframes eggAppear {
            from {
                opacity: 0;
                transform: translate(-50%, -50%) scale(0.8);
            }
            to {
                opacity: 1;
                transform: translate(-50%, -50%) scale(1);
            }
        }

        .easter-egg h3 {
            color: #00ff41;
            margin-bottom: 15px;
            font-size: 1.5em;
            text-shadow: 0 0 20px #00ff41;
        }

        .easter-egg p {
            color: #00cc33;
            margin-bottom: 10px;
            line-height: 1.5;
        }

        .close-btn {
            background: #00ff41;
            color: black;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            cursor: pointer;
            font-family: inherit;
            margin-top: 15px;
            font-weight: bold;
            text-transform: uppercase;
            transition: all 0.3s;
        }

        .close-btn:hover {
            background: #00cc33;
            transform: scale(1.05);
        }

        /* Secret Menu */
        .secret-menu {
            position: fixed;
            bottom: 10px;
            right: 10px;
            font-size: 0.7em;
            opacity: 0.3;
            cursor: help;
            z-index: 100;
            transition: opacity 0.3s;
        }

        .secret-menu:hover {
            opacity: 0.8;
        }

        /* Glitch Effect */
        .glitch {
            position: relative;
            animation: glitch 2s infinite;
        }

        @keyframes glitch {
            0%, 100% { text-shadow: 0 0 10px #00ff41; }
            25% { text-shadow: -2px 0 #ff0000, 2px 0 #00ffff; }
            50% { text-shadow: 2px 0 #ff00ff, -2px 0 #ffff00; }
            75% { text-shadow: 0 0 10px #00ff41; }
        }

        /* Loading Animation */
        .loading {
            display: inline-block;
            animation: blink 1s infinite;
        }

        @keyframes blink {
            0%, 50% { opacity: 1; }
            51%, 100% { opacity: 0; }
        }

        /* Mobile Responsive */
        @media (max-width: 768px) {
            .main-container {
                grid-template-columns: 1fr;
            }
            
            .stats-grid {
                grid-template-columns: repeat(2, 1fr);
            }
            
            .header h1 {
                font-size: 1.5em;
            }
            
            .control-panel {
                flex-direction: column;
            }
        }
    </style>
</head>
<body>
    <canvas class="matrix-rain" id="matrixCanvas"></canvas>
    <div class="crt-effect"></div>
    
    <div class="header">
        <h1 class="glitch">⟨ MARKET DATA PIPELINE TERMINAL ⟩</h1>
        <p>REAL-TIME EQUITY DATA STREAM  | WEBSOCKET ENABLED</p>
    </div>

    <div class="status-bar">
        <div class="status-item">
            <div class="status-indicator" id="redisStatus"></div>
            <span>REDIS: <span id="redisText">CONNECTING</span></span>
        </div>
        <div class="status-item">
            <div class="status-indicator" id="apiStatus"></div>
            <span>API: <span id="apiText">CHECKING</span></span>
        </div>
        <div class="status-item">
            <div class="status-indicator" id="wsStatus"></div>
            <span>WEBSOCKET: <span id="wsText">OFFLINE</span></span>
        </div>
        <div class="status-item">
            <div class="status-indicator" id="dockerStatus"></div>
            <span>DOCKER: <span id="dockerText">ACTIVE</span></span>
        </div>
    </div>

    <div class="control-panel">
        <select id="symbolSelect">
            <option value="AAPL">⟨ AAPL ⟩ Apple Inc.</option>
            <option value="GOOGL">⟨ GOOGL ⟩ Alphabet Inc.</option>
            <option value="MSFT">⟨ MSFT ⟩ Microsoft Corp.</option>
            <option value="AMZN">⟨ AMZN ⟩ Amazon.com Inc.</option>
            <option value="TSLA">⟨ TSLA ⟩ Tesla Inc.</option>
        </select>
    <button class="control-btn" onclick="connectWebSocket()">[CONNECT ALL]</button>
        <button class="control-btn" onclick="disconnectWebSocket()">[DISCONNECT]</button>
        <button class="control-btn" onclick="clearConsole()">[CLEAR]</button>
        <div style="margin-left: auto; color: #00ff41;">
            STATUS: <span id="connectionStatus" style="color: #ff4444;">OFFLINE</span>
        </div>
    </div>

    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-value" id="totalMessages">0</div>
            <div class="stat-label">Total Messages</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" id="messagesPerSec">0</div>
            <div class="stat-label">Messages/Sec</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" id="totalVolume">0</div>
            <div class="stat-label">Total Volume</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" id="uptime">00:00</div>
            <div class="stat-label">Uptime</div>
        </div>
    </div>

    <div class="main-container">
        <div class="panel">
            <h2>⟨ LIVE MARKET FEED ⟩</h2>
            <div class="stock-list" id="stockList"></div>
        </div>

        <div class="panel">
            <h2>⟨ Market Feed ⟩</h2>
            <div class="console" id="console"></div>
        </div>
    </div>

    <div class="easter-egg" id="easterEgg">
        <h3>🎮 TERMINAL EASTER EGG UNLOCKED! 🎮</h3>
        <p><strong>Achievement Unlocked:</strong> Matrix Trader</p>
        <p>You've discovered the secret developer console!</p>
        <p>Fun Fact: This pipeline processes over 9000 trades per second in production!</p>
        <p><em>"The Matrix has you... and your portfolio" - Morpheus, probably</em></p>
        <p style="margin-top: 20px; font-size: 0.8em; color: #666;">
            Konami Code: ↑ ↑ ↓ ↓ ← → ← → B A
        </p>
        <button class="close-btn" onclick="hideEasterEgg()">CLOSE</button>
    </div>

    <div class="secret-menu" onclick="showEasterEgg()" title="Click for secrets...">
        [SECRET: Try Konami Code] 🥚
    </div>

    <script>
        // WebSocket connection
        let ws = null;
        let messageCount = 0;
        let totalMessages = 0;
        let totalVolume = 0;
        let messagesPerSecond = 0;
        let messageTimestamps = [];
        let startTime = Date.now();
        
        // Stock data storage
        const stockData = {
            'AAPL': { symbol: 'AAPL', name: 'Apple Inc.', price: 0, change: 0, bid: 0, ask: 0 },
            'GOOGL': { symbol: 'GOOGL', name: 'Alphabet Inc.', price: 0, change: 0, bid: 0, ask: 0 },
            'MSFT': { symbol: 'MSFT', name: 'Microsoft Corp.', price: 0, change: 0, bid: 0, ask: 0 },
            'AMZN': { symbol: 'AMZN', name: 'Amazon.com Inc.', price: 0, change: 0, bid: 0, ask: 0 },
            'TSLA': { symbol: 'TSLA', name: 'Tesla Inc.', price: 0, change: 0, bid: 0, ask: 0 }
        };

        // Konami Code Detection
        let konamiCode = [];
        const konamiSequence = ['ArrowUp', 'ArrowUp', 'ArrowDown', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'ArrowLeft', 'ArrowRight', 'KeyB', 'KeyA'];

        // Initialize Matrix Rain Effect
        function initializeMatrix() {
            const canvas = document.getElementById('matrixCanvas');
            const ctx = canvas.getContext('2d');
            
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
            
            const chars = '01アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン$€£¥₿📈📉💹💱';
            const charArray = chars.split('');
            const fontSize = 14;
            const columns = canvas.width / fontSize;
            const drops = Array(Math.floor(columns)).fill(1);
            
            function drawMatrix() {
                ctx.fillStyle = 'rgba(0, 0, 0, 0.05)';
                ctx.fillRect(0, 0, canvas.width, canvas.height);
                
                ctx.fillStyle = '#00ff41';
                ctx.font = fontSize + 'px monospace';
                
                for (let i = 0; i < drops.length; i++) {
                    const text = charArray[Math.floor(Math.random() * charArray.length)];
                    ctx.fillText(text, i * fontSize, drops[i] * fontSize);
                    
                    if (drops[i] * fontSize > canvas.height && Math.random() > 0.975) {
                        drops[i] = 0;
                    }
                    drops[i]++;
                }
            }
            
            setInterval(drawMatrix, 50);
        }

        // Console Logging
        function logConsole(message, type = 'system') {
            const console = document.getElementById('console');
            const timestamp = new Date().toLocaleTimeString();
            const consoleLine = document.createElement('div');
            consoleLine.className = 'console-line';
            
            let typeClass = 'system-msg';
            let prefix = '[SYSTEM]';
            
            switch(type) {
                case 'trade':
                    typeClass = 'trade-msg';
                    prefix = '[TRADE]';
                    break;
                case 'quote':
                    typeClass = 'quote-msg';
                    prefix = '[QUOTE]';
                    break;
                case 'error':
                    typeClass = 'error-msg';
                    prefix = '[ERROR]';
                    break;
                case 'success':
                    typeClass = 'system-msg';
                    prefix = '[SUCCESS]';
                    break;
            }
            
            consoleLine.innerHTML = `<span class="timestamp">[${timestamp}]</span><span class="${typeClass}">${prefix}</span> ${message}`;
            console.appendChild(consoleLine);
            console.scrollTop = console.scrollHeight;
            
            // Keep only last 100 messages
            while (console.children.length > 100) {
                console.removeChild(console.children[0]);
            }
        }

        // WebSocket Connection
    // Replace the old connectWebSocket() function with this:
let websockets = {};  // Store multiple WebSocket connections

function connectWebSocket() {
    const symbols = ['AAPL', 'GOOGL', 'MSFT', 'AMZN', 'TSLA'];
    
    logConsole('Initiating connection to ALL market feeds...', 'system');
    
    symbols.forEach(symbol => {
        if (websockets[symbol] && websockets[symbol].readyState === WebSocket.OPEN) {
            return;
        }
        
        try {
            websockets[symbol] = new WebSocket(`ws://localhost:8000/ws/${symbol}`);
            
            websockets[symbol].onopen = function(event) {
                logConsole(`✓ Connected to ${symbol} feed`, 'success');
            };
            
            websockets[symbol].onmessage = function(event) {
                try {
                    const data = JSON.parse(event.data);
                    processMarketData(data, symbol);
                    totalMessages++;
                    updateStats();
                } catch (e) {
                    logConsole(`Parse error for ${symbol}: ${e.message}`, 'error');
                }
            };
            
            websockets[symbol].onerror = function(error) {
                logConsole(`WebSocket error for ${symbol}`, 'error');
            };
            
            websockets[symbol].onclose = function(event) {
                logConsole(`${symbol} connection closed`, 'system');
            };
            
        } catch (error) {
            logConsole(`Failed to connect ${symbol}: ${error.message}`, 'error');
        }
    });
    
    document.getElementById('connectionStatus').textContent = 'ALL CONNECTED';
    document.getElementById('connectionStatus').style.color = '#00ff41';
}

// Replace disconnectWebSocket() with this:
function disconnectWebSocket() {
    Object.keys(websockets).forEach(symbol => {
        if (websockets[symbol] && websockets[symbol].readyState === WebSocket.OPEN) {
            websockets[symbol].close();
        }
    });
    websockets = {};
    logConsole('Disconnecting from all market feeds...', 'system');
    document.getElementById('connectionStatus').textContent = 'OFFLINE';
    document.getElementById('connectionStatus').style.color = '#ff4444';
}

        function processMarketData(data, symbol) {
            const stock = stockData[symbol];
            
            if (data.type === 'quote') {
                stock.bid = data.bid_price;
                stock.ask = data.ask_price;
                logConsole(
                    `Quote ${symbol}: Bid $${data.bid_price.toFixed(2)} | Ask $${data.ask_price.toFixed(2)} | Spread $${(data.ask_price - data.bid_price).toFixed(2)}`,
                    'quote'
                );
            } else if (data.type === 'trade') {
                const oldPrice = stock.price || data.price;
                stock.price = data.price;
                stock.change = data.price - oldPrice;
                totalVolume += data.volume;
                
                const arrow = data.side === 'BUY' ? '↑' : '↓';
                const color = data.side === 'BUY' ? '🟢' : '🔴';
                logConsole(
                    `${color} Trade ${symbol}: ${data.side} ${data.volume} @ $${data.price.toFixed(2)} ${arrow}`,
                    'trade'
                );
            }
            
            updateStockDisplay();
        }

        function updateStockDisplay() {
            const stockList = document.getElementById('stockList');
            stockList.innerHTML = '';
            
            Object.values(stockData).forEach(stock => {
                const stockElement = document.createElement('div');
                stockElement.className = 'stock-item';
                
                const changeClass = stock.change >= 0 ? 'positive' : 'negative';
                const changeSymbol = stock.change >= 0 ? '+' : '';
                const changePercent = stock.price > 0 ? (stock.change / stock.price * 100).toFixed(2) : '0.00';
                
                stockElement.innerHTML = `
                    <div class="stock-symbol">${stock.symbol}</div>
                    <div class="stock-name">${stock.name}</div>
                    <div class="stock-price">$${stock.price.toFixed(2)}</div>
                    <div class="stock-change ${changeClass}">${changeSymbol}${stock.change.toFixed(2)}</div>
                    <div class="stock-change ${changeClass}">${changeSymbol}${changePercent}%</div>
                `;
                
                stockList.appendChild(stockElement);
            });
        }

        function updateConnectionStatus(connected) {
            const wsStatus = document.getElementById('wsStatus');
            const wsText = document.getElementById('wsText');
            
            if (connected) {
                wsStatus.classList.remove('offline');
                wsText.textContent = 'CONNECTED';
            } else {
                wsStatus.classList.add('offline');
                wsText.textContent = 'OFFLINE';
            }
        }

        function updateStats() {
            // Update message count
            document.getElementById('totalMessages').textContent = totalMessages.toLocaleString();
            
            // Calculate messages per second
            const now = Date.now();
            messageTimestamps.push(now);
            messageTimestamps = messageTimestamps.filter(t => now - t < 1000);
            messagesPerSecond = messageTimestamps.length;
            document.getElementById('messagesPerSec').textContent = messagesPerSecond;
            
            // Update volume
            document.getElementById('totalVolume').textContent = totalVolume.toLocaleString();
            
            // Update uptime
            const uptimeSeconds = Math.floor((now - startTime) / 1000);
            const hours = Math.floor(uptimeSeconds / 3600);
            const minutes = Math.floor((uptimeSeconds % 3600) / 60);
            const seconds = uptimeSeconds % 60;
            document.getElementById('uptime').textContent = 
                `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
        }

        function clearConsole() {
            document.getElementById('console').innerHTML = '';
            logConsole('Console cleared', 'system');
        }

        function showEasterEgg() {
            document.getElementById('easterEgg').style.display = 'block';
            logConsole('🥚 Easter egg activated! Achievement unlocked: Matrix Trader', 'success');
        }

        function hideEasterEgg() {
            document.getElementById('easterEgg').style.display = 'none';
        }

        // Check API Status
        async function checkAPIStatus() {
            try {
                const response = await fetch('http://localhost:8000/health');
                if (response.ok) {
                    document.getElementById('apiStatus').classList.remove('offline');
                    document.getElementById('apiText').textContent = 'ONLINE';
                    document.getElementById('redisStatus').classList.remove('offline');
                    document.getElementById('redisText').textContent = 'CONNECTED';
                    return true;
                }
            } catch (error) {
                document.getElementById('apiStatus').classList.add('offline');
                document.getElementById('apiText').textContent = 'OFFLINE';
                document.getElementById('redisStatus').classList.add('offline');
                document.getElementById('redisText').textContent = 'ERROR';
                logConsole('API health check failed. Make sure services are running.', 'error');
                return false;
            }
        }

        // Konami Code Detection
        document.addEventListener('keydown', (e) => {
            konamiCode.push(e.code);
            if (konamiCode.length > konamiSequence.length) {
                konamiCode.shift();
            }
            
            if (konamiCode.join(',') === konamiSequence.join(',')) {
                showEasterEgg();
                konamiCode = [];
                // Add special effect
                document.body.style.animation = 'glitch 0.5s';
                setTimeout(() => {
                    document.body.style.animation = '';
                }, 500);
            }
        });

        // Initialize on load
        window.addEventListener('load', async () => {
            initializeMatrix();
            logConsole('Market Data Pipeline Terminal  initializing...', 'system');
            logConsole('Checking system components...', 'system');
            
            // Check API status
            const apiOnline = await checkAPIStatus();
            
            if (apiOnline) {
                logConsole('✓ All systems operational', 'success');
                logConsole('Ready to connect to market feed', 'system');
            } else {
                logConsole('⚠ API offline. Run: docker-compose up -d', 'error');
            }
            
            // Initialize stock display
            updateStockDisplay();
            
            // Update stats every second
            setInterval(updateStats, 1000);
            
            // Periodic API health check
            setInterval(checkAPIStatus, 30000);
        });

        // Handle window resize
        window.addEventListener('resize', () => {
            const canvas = document.getElementById('matrixCanvas');
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
        });
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
