"""
Run the BRM Trading Dashboard
"""
import uvicorn
import webbrowser
import threading
import time

def open_browser():
    time.sleep(1.5)
    webbrowser.open("http://localhost:8001")

if __name__ == "__main__":
    print("\n" + "="*60)
    print("  BRM Trading Dashboard")
    print("  Test Environment - Permission Evidence")
    print("="*60)
    print("\n  Starting server at http://localhost:8001")
    print("  Press Ctrl+C to stop\n")

    # Open browser after server starts
    threading.Thread(target=open_browser, daemon=True).start()

    uvicorn.run("app:app", host="0.0.0.0", port=8001, reload=False)
