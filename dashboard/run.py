"""
Run the Astro Trading Dashboard

Usage:
    python run.py [--port 5000] [--debug]
"""
import argparse
import webbrowser
import threading
import time
from app import app


def open_browser(port):
    """Open browser after short delay."""
    time.sleep(1.5)
    webbrowser.open(f'http://localhost:{port}')


def main():
    parser = argparse.ArgumentParser(description='Astro Trading Dashboard')
    parser.add_argument('--port', type=int, default=5000, help='Port to run on')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--no-browser', action='store_true', help='Don\'t open browser automatically')

    args = parser.parse_args()

    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║      ☀️  ASTRO SOLAR TRADING DASHBOARD                    ║
    ║                                                           ║
    ║      DA + Intraday Automation Interface                   ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
    """)

    print(f"    Starting server on http://localhost:{args.port}")
    print(f"    Press Ctrl+C to stop\n")

    if not args.no_browser:
        threading.Thread(target=open_browser, args=(args.port,), daemon=True).start()

    app.run(
        host='0.0.0.0',
        port=args.port,
        debug=args.debug,
        use_reloader=args.debug
    )


if __name__ == '__main__':
    main()
