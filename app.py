# app.py - Single file version
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from datetime import datetime
import uvicorn
import webbrowser
import threading
import time

app = FastAPI(
    title="Athena-X Portfolio Manager",
    description="Autonomous AI Portfolio Manager",
    version="4.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {
        "message": "Athena-X Portfolio Manager",
        "status": "running",
        "version": "4.0.0",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/analyze/{symbol}")
async def analyze(symbol: str):
    return {
        "symbol": symbol,
        "signal": "WAIT",
        "confidence": 65,
        "reason": "Market consolidating - awaiting clear direction",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    return """
    <!DOCTYPE html>
    <html>
    <head><title>Athena-X Dashboard</title>
    <style>
        body { font-family: Arial; background: #0f0f1a; color: #fff; padding: 20px; }
        .container { max-width: 800px; margin: 0 auto; }
        .header h1 { font-size: 28px; }
        .status { color: #00ff88; }
        .card { background: #1a1a2e; padding: 20px; border-radius: 12px; margin: 10px 0; }
        .signal { font-size: 32px; font-weight: bold; }
        .refresh-btn { background: #2a2a4e; border: none; color: #fff; padding: 10px 25px; border-radius: 8px; cursor: pointer; }
        .refresh-btn:hover { background: #3a3a6e; }
    </style>
    </head>
    <body>
    <div class="container">
        <div class="header"><h1>🧠 Athena-X Portfolio Manager <span class="status">🟢 Live</span></h1></div>
        <div class="card"><h2>📊 Signal</h2><div class="signal" id="signal">WAIT</div>
        <div id="reason">Loading...</div><br>
        <button class="refresh-btn" onclick="refresh()">🔄 Refresh</button></div>
        <div class="card"><h3>💰 Capital: ₹5,00,000</h3></div>
    </div>
    <script>
    async function refresh() {
        try {
            const resp = await fetch('/analyze/NIFTY');
            const data = await resp.json();
            document.getElementById('signal').textContent = data.signal;
            document.getElementById('reason').textContent = data.reason;
        } catch(e) { console.log(e); }
    }
    refresh();
    setInterval(refresh, 30000);
    </script>
    </body>
    </html>
    """

if __name__ == "__main__":
    print("="*60)
    print("🧠 Athena-X Portfolio Manager")
    print("="*60)
    print("📡 Server: http://localhost:8000")
    print("📊 Dashboard: http://localhost:8000/dashboard")
    print("="*60)
    
    def open_browser():
        time.sleep(2)
        webbrowser.open("http://localhost:8000/dashboard")
    
    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run(app, host="127.0.0.1", port=8000)