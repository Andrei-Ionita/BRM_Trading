"""
Astro Solar Trading Dashboard
Clean, modern web interface for DA + Intraday automation monitoring.
"""
import json
import os
import sys
import threading
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from collections import deque
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from imbalance_manager import (
    load_position,
    get_today_date,
    get_tomorrow_date,
    get_current_cet_interval,
    get_remaining_intervals,
    mwh_to_mw,
    interval_to_datetime,
    POSITION_FILE,
    TZ_CET
)

app = Flask(__name__)
CORS(app)

# Store for real-time data
dashboard_state = {
    "da_status": "idle",  # idle, running, completed, error
    "intraday_status": "idle",
    "forecast_status": "idle",
    "last_da_run": None,
    "last_intraday_run": None,
    "da_output": "",
    "intraday_output": "",
    "orders_today": [],
    "trades_today": [],
    "alerts": []
}

# Log storage (keep last 500 lines)
log_buffer = deque(maxlen=500)


def add_log(message: str, level: str = "INFO"):
    """Add a log entry."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_buffer.append({
        "timestamp": timestamp,
        "level": level,
        "message": message
    })


def get_forecast_data(delivery_date: str) -> dict:
    """Load forecast data for a given date."""
    # Look in BRM_Trading_Bot/Astro/ (same directory as the app)
    results_path = Path(__file__).parent.parent / "Astro" / "Results_Production_Astro_xgb_15min.xlsx"

    if not results_path.exists():
        return {"intervals": [], "values": [], "total_mwh": 0, "error": "Forecast file not found"}

    try:
        import pandas as pd
        df = pd.read_excel(results_path)
        df["Data"] = pd.to_datetime(df["Data"])

        target_date = datetime.strptime(delivery_date, "%Y-%m-%d")
        df_date = df[df["Data"].dt.date == target_date.date()]

        if df_date.empty:
            return {"intervals": [], "values": [], "total_mwh": 0, "error": f"No forecast data for {delivery_date}"}

        intervals = df_date["Interval"].tolist()
        values = df_date["Prediction"].tolist()

        # Convert to MW for display
        values_mw = [mwh_to_mw(v) for v in values]

        return {
            "intervals": intervals,
            "values": values,
            "values_mw": values_mw,
            "total_mwh": round(sum(values), 2),
            "total_mw": round(sum(values_mw), 2),
            "peak_mw": round(max(values_mw) if values_mw else 0, 1),
            "peak_interval": intervals[values_mw.index(max(values_mw))] if values_mw else 0,
            "count": len(intervals)
        }
    except Exception as e:
        return {"error": str(e), "intervals": [], "values": [], "total_mwh": 0}


def get_position_summary(delivery_date: str) -> dict:
    """Get position summary for dashboard."""
    position = load_position(delivery_date)

    if not position:
        return {
            "exists": False,
            "delivery_date": delivery_date,
            "total_da_sold": 0,
            "total_idm_sold": 0,
            "total_idm_bought": 0,
            "total_contracted": 0,
            "intervals_with_position": 0,
            "net_idm": 0
        }

    intervals = position.get("intervals", {})

    total_da = sum(v.get("da_sold", 0) for v in intervals.values())
    total_idm_sold = sum(v.get("idm_sold", 0) for v in intervals.values())
    total_idm_bought = sum(v.get("idm_bought", 0) for v in intervals.values())
    total_contracted = sum(v.get("contracted", 0) for v in intervals.values())

    intervals_with_pos = sum(1 for v in intervals.values() if v.get("contracted", 0) > 0)

    return {
        "exists": True,
        "delivery_date": delivery_date,
        "last_updated": position.get("last_updated", ""),
        "total_da_sold": round(total_da, 2),
        "total_idm_sold": round(total_idm_sold, 2),
        "total_idm_bought": round(total_idm_bought, 2),
        "total_contracted": round(total_contracted, 2),
        "intervals_with_position": intervals_with_pos,
        "net_idm": round(total_idm_sold - total_idm_bought, 2)
    }


def get_interval_details(delivery_date: str) -> list:
    """Get detailed interval data for table view."""
    position = load_position(delivery_date)
    current_interval = get_current_cet_interval()

    # Build latest forecast lookup - prefer database history
    forecast_lookup = {}

    # Try to get latest forecast from database history first
    try:
        from database import get_latest_forecast_from_history
        latest = get_latest_forecast_from_history(delivery_date)
        if latest and latest.get("forecast_data"):
            for interval_str, value in latest["forecast_data"].items():
                forecast_lookup[int(interval_str)] = round(float(value), 2)
    except Exception:
        pass

    # Fall back to XGBoost file if no database forecast
    if not forecast_lookup:
        forecast = get_forecast_data(delivery_date)
        if forecast.get("intervals"):
            for idx, interval_num in enumerate(forecast["intervals"]):
                forecast_lookup[interval_num] = round(forecast["values_mw"][idx], 2)

    details = []

    for i in range(1, 97):
        interval_data = {
            "interval": i,
            "time": f"{(i-1)//4:02d}:{((i-1)%4)*15:02d}",
            "status": "completed" if i < current_interval else ("active" if i == current_interval else "pending"),
            "da_sold": 0,
            "da_forecast": 0,  # Forecast used at DA time
            "idm_sold": 0,
            "idm_bought": 0,
            "contracted": 0,
            "forecast_mw": 0,  # Latest forecast
            "imbalance": 0
        }

        if position and str(i) in position.get("intervals", {}):
            pos_interval = position["intervals"][str(i)]
            interval_data.update({
                "da_sold": pos_interval.get("da_sold", 0),
                "da_forecast": pos_interval.get("da_forecast", pos_interval.get("da_sold", 0)),  # Fallback to da_sold if not set
                "idm_sold": pos_interval.get("idm_sold", 0),
                "idm_bought": pos_interval.get("idm_bought", 0),
                "contracted": pos_interval.get("contracted", 0)
            })

        # Get latest forecast value for this interval
        interval_data["forecast_mw"] = forecast_lookup.get(i, 0)

        # Calculate imbalance (contracted vs latest forecast)
        interval_data["imbalance"] = round(
            interval_data["contracted"] - interval_data["forecast_mw"], 2
        )

        details.append(interval_data)

    return details


# ==================== Routes ====================

@app.route("/")
def index():
    """Main dashboard page."""
    return render_template("index.html")


@app.route("/api/status")
def api_status():
    """Get current system status."""
    today = get_today_date()
    tomorrow = get_tomorrow_date()
    current_interval = get_current_cet_interval()
    now_cet = datetime.now(TZ_CET)

    return jsonify({
        "current_time": now_cet.strftime("%Y-%m-%d %H:%M:%S CET"),
        "today": today,
        "tomorrow": tomorrow,
        "current_interval": current_interval,
        "current_interval_time": f"{(current_interval-1)//4:02d}:{((current_interval-1)%4)*15:02d}",
        "remaining_intervals": len(get_remaining_intervals(current_interval)),
        "da_status": dashboard_state["da_status"],
        "intraday_status": dashboard_state["intraday_status"],
        "last_da_run": dashboard_state["last_da_run"],
        "last_intraday_run": dashboard_state["last_intraday_run"],
        "position_file_exists": POSITION_FILE.exists()
    })


@app.route("/api/position/<date>")
def api_position(date):
    """Get position data for a specific date."""
    return jsonify(get_position_summary(date))


@app.route("/api/forecast/<date>")
def api_forecast(date):
    """Get forecast data for a specific date."""
    return jsonify(get_forecast_data(date))


@app.route("/api/intervals/<date>")
def api_intervals(date):
    """Get detailed interval data."""
    return jsonify(get_interval_details(date))


@app.route("/api/chart/<date>")
def api_chart(date):
    """Get chart data for visualization."""
    position = load_position(date)

    labels = [f"{(i-1)//4:02d}:{((i-1)%4)*15:02d}" for i in range(1, 97)]

    # Build latest forecast lookup - prefer database history
    forecast_lookup = {}

    # Try to get latest forecast from database history first
    try:
        from database import get_latest_forecast_from_history
        latest = get_latest_forecast_from_history(date)
        if latest and latest.get("forecast_data"):
            for interval_str, value in latest["forecast_data"].items():
                forecast_lookup[int(interval_str)] = round(float(value), 2)
    except Exception:
        pass

    # Fall back to XGBoost file if no database forecast
    if not forecast_lookup:
        forecast = get_forecast_data(date)
        if forecast.get("intervals"):
            for idx, interval_num in enumerate(forecast["intervals"]):
                forecast_lookup[interval_num] = round(forecast["values_mw"][idx], 2)

    contracted = []
    da_sold = []
    forecast_mw = []

    for i in range(1, 97):
        if position and str(i) in position.get("intervals", {}):
            contracted.append(position["intervals"][str(i)].get("contracted", 0))
            da_sold.append(position["intervals"][str(i)].get("da_sold", 0))
        else:
            contracted.append(0)
            da_sold.append(0)

        forecast_mw.append(forecast_lookup.get(i, 0))

    return jsonify({
        "labels": labels,
        "datasets": {
            "contracted": contracted,
            "da_sold": da_sold,
            "forecast": forecast_mw
        }
    })


@app.route("/api/logs")
def api_logs():
    """Get recent logs."""
    return jsonify(list(log_buffer))


@app.route("/api/logs/clear", methods=["POST"])
def api_clear_logs():
    """Clear logs."""
    log_buffer.clear()
    return jsonify({"status": "cleared"})


@app.route("/api/output/<task_type>")
def api_output(task_type):
    """Get output from last run."""
    if task_type == "da":
        return jsonify({"output": dashboard_state.get("da_output", ""), "status": dashboard_state["da_status"]})
    elif task_type == "intraday":
        return jsonify({"output": dashboard_state.get("intraday_output", ""), "status": dashboard_state["intraday_status"]})
    return jsonify({"error": "Unknown task type"})


@app.route("/api/run/da", methods=["POST"])
def api_run_da():
    """Trigger DA automation run."""
    data = request.json or {}
    dry_run = data.get("dry_run", True)
    date = data.get("date", get_tomorrow_date())

    dashboard_state["da_status"] = "running"
    dashboard_state["da_output"] = ""
    add_log(f"Starting DA automation (dry_run={dry_run}, date={date})", "INFO")

    def run_da():
        try:
            cmd = [sys.executable, str(Path(__file__).parent.parent / "day_ahead_automation.py")]
            if dry_run:
                cmd.append("--dry-run")
            cmd.extend(["--date", date])

            add_log(f"Running command: {' '.join(cmd)}", "DEBUG")

            # Run with real-time output capture
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            output_lines = []
            for line in iter(process.stdout.readline, ''):
                line = line.strip()
                if line:
                    output_lines.append(line)
                    add_log(line, "INFO")
                    dashboard_state["da_output"] = "\n".join(output_lines[-100:])

            process.wait()

            if process.returncode == 0:
                dashboard_state["da_status"] = "completed"
                add_log("DA automation completed successfully", "SUCCESS")
            else:
                dashboard_state["da_status"] = "error"
                add_log(f"DA automation failed with code {process.returncode}", "ERROR")

            dashboard_state["last_da_run"] = datetime.now().isoformat()

        except Exception as e:
            dashboard_state["da_status"] = "error"
            dashboard_state["da_output"] = str(e)
            add_log(f"DA automation error: {e}", "ERROR")

    thread = threading.Thread(target=run_da)
    thread.start()

    return jsonify({"status": "started", "dry_run": dry_run, "date": date})


@app.route("/api/run/intraday", methods=["POST"])
def api_run_intraday():
    """Trigger single intraday iteration."""
    data = request.json or {}
    dry_run = data.get("dry_run", True)
    date = data.get("date", get_today_date())

    dashboard_state["intraday_status"] = "running"
    dashboard_state["intraday_output"] = ""
    add_log(f"Starting Intraday automation (dry_run={dry_run}, date={date})", "INFO")

    def run_intraday():
        try:
            cmd = [
                sys.executable,
                str(Path(__file__).parent.parent / "intraday_automation.py"),
                "--single-run"
            ]
            if dry_run:
                cmd.append("--dry-run")
            cmd.extend(["--date", date])

            add_log(f"Running command: {' '.join(cmd)}", "DEBUG")

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )

            output_lines = []
            for line in iter(process.stdout.readline, ''):
                line = line.strip()
                if line:
                    output_lines.append(line)
                    add_log(line, "INFO")
                    dashboard_state["intraday_output"] = "\n".join(output_lines[-100:])

            process.wait()

            if process.returncode == 0:
                dashboard_state["intraday_status"] = "completed"
                add_log("Intraday automation completed successfully", "SUCCESS")
            else:
                dashboard_state["intraday_status"] = "error"
                add_log(f"Intraday automation failed with code {process.returncode}", "ERROR")

            dashboard_state["last_intraday_run"] = datetime.now().isoformat()

        except Exception as e:
            dashboard_state["intraday_status"] = "error"
            dashboard_state["intraday_output"] = str(e)
            add_log(f"Intraday automation error: {e}", "ERROR")

    thread = threading.Thread(target=run_intraday)
    thread.start()

    return jsonify({"status": "started", "dry_run": dry_run, "date": date})


@app.route("/api/run/forecast", methods=["POST"])
def api_run_forecast():
    """Trigger forecast fetch and prediction, save to history database."""
    data = request.json or {}
    date = data.get("date", get_today_date())

    dashboard_state["forecast_status"] = "running"
    add_log(f"Starting forecast fetch for {date}...", "INFO")

    def run_forecast():
        import traceback
        try:
            # Import from BRM_Trading_Bot directory (parent of dashboard)
            bot_dir = Path(__file__).parent.parent
            if str(bot_dir) not in sys.path:
                sys.path.insert(0, str(bot_dir))

            add_log(f"Bot dir: {bot_dir}", "DEBUG")

            add_log("Importing Forecast_functions...", "DEBUG")
            from Forecast_functions import fetching_Astro_data_15min, predicting_exporting_Astro_15min

            add_log("Fetching Solcast data...", "INFO")
            fetching_Astro_data_15min()
            add_log("Solcast data fetched successfully", "SUCCESS")

            add_log("Running XGBoost prediction model...", "INFO")
            predicting_exporting_Astro_15min(0, 24, 0)
            add_log("Prediction model completed successfully", "SUCCESS")

            # Save forecast to database history
            add_log("Saving forecast to database history...", "INFO")
            try:
                import pandas as pd
                from datetime import datetime as dt

                results_path = bot_dir / "Astro" / "Results_Production_Astro_xgb_15min.xlsx"
                df = pd.read_excel(results_path)
                df["Data"] = pd.to_datetime(df["Data"])

                target_date = dt.strptime(date, "%Y-%m-%d")
                df_date = df[df["Data"].dt.date == target_date.date()]

                if not df_date.empty:
                    # Build forecast dict (convert MWh to MW)
                    forecast_mw = {}
                    for _, row in df_date.iterrows():
                        interval = int(row["Interval"])
                        mwh = float(row["Prediction"])
                        forecast_mw[interval] = round(mwh * 4, 2)  # MWh to MW

                    # Save to database
                    from database import save_forecast_to_history
                    if save_forecast_to_history(date, forecast_mw):
                        add_log(f"Forecast saved to history: {len(forecast_mw)} intervals", "SUCCESS")
                    else:
                        add_log("Failed to save forecast to database (DB unavailable?)", "WARNING")
                else:
                    add_log(f"No forecast data for {date} to save", "WARNING")

            except Exception as e:
                add_log(f"Error saving forecast to history: {e}", "WARNING")

            dashboard_state["forecast_status"] = "completed"

        except Exception as e:
            dashboard_state["forecast_status"] = "error"
            error_trace = traceback.format_exc()
            add_log(f"Forecast error: {e}", "ERROR")
            add_log(f"Traceback: {error_trace}", "ERROR")

    thread = threading.Thread(target=run_forecast)
    thread.start()

    return jsonify({"status": "started", "date": date})


@app.route("/api/forecast/status")
def api_forecast_status():
    """Get forecast fetch status."""
    return jsonify({"status": dashboard_state.get("forecast_status", "idle")})


@app.route("/api/position/create", methods=["POST"])
def api_create_position():
    """Create position from forecast for a given date."""
    data = request.json or {}
    date = data.get("date", get_today_date())

    add_log(f"Creating position for {date} from forecast...", "INFO")

    try:
        import pandas as pd
        from datetime import datetime as dt

        # Get forecast file
        results_path = Path(__file__).parent.parent / "Astro" / "Results_Production_Astro_xgb_15min.xlsx"

        if not results_path.exists():
            add_log(f"Forecast file not found: {results_path}", "ERROR")
            return jsonify({"error": "Forecast file not found. Run forecast first."}), 400

        df = pd.read_excel(results_path)
        df["Data"] = pd.to_datetime(df["Data"])

        target_date = dt.strptime(date, "%Y-%m-%d")
        df_date = df[df["Data"].dt.date == target_date.date()]

        if df_date.empty:
            add_log(f"No forecast data for {date}", "ERROR")
            return jsonify({"error": f"No forecast data for {date}"}), 400

        # Create da_sold_dict from forecast (convert MWh to MW)
        da_sold_dict = {}
        for _, row in df_date.iterrows():
            interval = int(row["Interval"])
            mwh = float(row["Prediction"])
            mw = mwh * 4  # MWh to MW for 15-min interval
            da_sold_dict[interval] = round(mw, 1)

        add_log(f"Found {len(da_sold_dict)} forecast intervals", "INFO")

        # Import and create position
        from imbalance_manager import init_position_file
        position = init_position_file(date, da_sold_dict)

        if position:
            total = sum(v.get("contracted", 0) for v in position.get("intervals", {}).values())
            add_log(f"Position created! Total: {total:.2f} MW", "SUCCESS")
            return jsonify({
                "status": "created",
                "date": date,
                "total_contracted_mw": round(total, 2),
                "intervals_with_production": len([v for v in position.get("intervals", {}).values() if v.get("contracted", 0) > 0])
            })
        else:
            add_log("Failed to create position", "ERROR")
            return jsonify({"error": "Failed to create position"}), 500

    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        add_log(f"Error creating position: {e}", "ERROR")
        add_log(f"Traceback: {error_trace}", "ERROR")
        return jsonify({"error": str(e)}), 500


@app.route("/api/da/activity/<date>")
def api_da_activity(date):
    """Get DA trading activity for a date."""
    position = load_position(date)

    if not position:
        return jsonify({"orders": [], "summary": {"total_sold": 0, "interval_count": 0}})

    intervals = position.get("intervals", {})
    orders = []
    total_sold = 0

    for interval_num in range(1, 97):
        interval_data = intervals.get(str(interval_num), {})
        da_sold = interval_data.get("da_sold", 0)

        if da_sold > 0:
            orders.append({
                "interval": interval_num,
                "time": f"{(interval_num-1)//4:02d}:{((interval_num-1)%4)*15:02d}",
                "quantity": round(da_sold, 2),
                "contracted": round(interval_data.get("contracted", 0), 2)
            })
            total_sold += da_sold

    return jsonify({
        "orders": orders,
        "summary": {
            "total_sold": round(total_sold, 2),
            "interval_count": len(orders)
        },
        "delivery_date": date,
        "last_updated": position.get("last_updated", "")
    })


@app.route("/api/idm/activity/<date>")
def api_idm_activity(date):
    """Get IDM trading activity for a date."""
    position = load_position(date)

    if not position:
        return jsonify({"trades": [], "summary": {"total_sold": 0, "total_bought": 0}})

    intervals = position.get("intervals", {})
    trades = []
    total_sold = 0
    total_bought = 0

    # Build forecast lookup - prefer latest forecast from database history
    forecast_lookup = {}

    # Try to get latest forecast from database history first
    try:
        from database import get_latest_forecast_from_history
        latest = get_latest_forecast_from_history(date)
        if latest and latest.get("forecast_data"):
            for interval_str, value in latest["forecast_data"].items():
                forecast_lookup[int(interval_str)] = round(float(value), 2)
    except Exception:
        pass

    # Fall back to XGBoost file if no database forecast
    if not forecast_lookup:
        forecast = get_forecast_data(date)
        if forecast.get("intervals"):
            for idx, interval_num in enumerate(forecast["intervals"]):
                forecast_lookup[interval_num] = round(forecast["values_mw"][idx], 2)

    for interval_num in range(1, 97):
        interval_data = intervals.get(str(interval_num), {})
        idm_sold = interval_data.get("idm_sold", 0)
        idm_bought = interval_data.get("idm_bought", 0)
        forecast_mw = forecast_lookup.get(interval_num, 0)

        if idm_sold > 0:
            trades.append({
                "interval": interval_num,
                "time": f"{(interval_num-1)//4:02d}:{((interval_num-1)%4)*15:02d}",
                "side": "SELL",
                "quantity": round(idm_sold, 2),
                "forecast_mw": forecast_mw,
                "contracted": round(interval_data.get("contracted", 0), 2)
            })
            total_sold += idm_sold

        if idm_bought > 0:
            trades.append({
                "interval": interval_num,
                "time": f"{(interval_num-1)//4:02d}:{((interval_num-1)%4)*15:02d}",
                "side": "BUY",
                "quantity": round(idm_bought, 2),
                "forecast_mw": forecast_mw,
                "contracted": round(interval_data.get("contracted", 0), 2)
            })
            total_bought += idm_bought

    return jsonify({
        "trades": trades,
        "summary": {
            "total_sold": round(total_sold, 2),
            "total_bought": round(total_bought, 2),
            "net": round(total_sold - total_bought, 2),
            "trade_count": len(trades)
        },
        "last_updated": position.get("last_updated", "")
    })


@app.route("/api/forecast/debug/<date>")
def api_forecast_debug(date):
    """Debug endpoint to check forecast sources and database status."""
    result = {
        "date": date,
        "database_available": False,
        "database_forecast": None,
        "database_refreshed_at": None,
        "xgboost_forecast": None,
        "position_da_forecast": None,
        "sample_intervals": {}
    }

    # Check database availability and get latest forecast
    try:
        from database import is_database_available, get_latest_forecast_from_history
        result["database_available"] = is_database_available()

        if result["database_available"]:
            latest = get_latest_forecast_from_history(date)
            if latest:
                result["database_forecast"] = f"{len(latest.get('forecast_data', {}))} intervals"
                result["database_refreshed_at"] = latest.get("refreshed_at")
                # Sample a few intervals
                forecast_data = latest.get("forecast_data", {})
                for interval in ["50", "55", "60", "65"]:
                    if interval in forecast_data:
                        result["sample_intervals"][f"db_interval_{interval}"] = forecast_data[interval]
    except Exception as e:
        result["database_error"] = str(e)

    # Check XGBoost file
    try:
        forecast = get_forecast_data(date)
        if forecast.get("intervals"):
            result["xgboost_forecast"] = f"{len(forecast['intervals'])} intervals"
            # Sample intervals
            for i, interval_num in enumerate(forecast["intervals"]):
                if interval_num in [50, 55, 60, 65]:
                    result["sample_intervals"][f"xgb_interval_{interval_num}"] = round(forecast["values_mw"][i], 2)
    except Exception as e:
        result["xgboost_error"] = str(e)

    # Check position file for DA forecast
    try:
        position = load_position(date)
        if position:
            result["position_da_forecast"] = "available"
            for interval in ["50", "55", "60", "65"]:
                if interval in position.get("intervals", {}):
                    da_forecast = position["intervals"][interval].get("da_forecast", 0)
                    result["sample_intervals"][f"da_interval_{interval}"] = da_forecast
    except Exception as e:
        result["position_error"] = str(e)

    return jsonify(result)


@app.route("/api/alerts")
def api_alerts():
    """Get recent alerts."""
    return jsonify(dashboard_state.get("alerts", [])[-20:])


@app.route("/api/alerts/clear", methods=["POST"])
def api_clear_alerts():
    """Clear all alerts."""
    dashboard_state["alerts"] = []
    return jsonify({"status": "cleared"})


if __name__ == "__main__":
    # Ensure directories exist
    templates_dir = Path(__file__).parent / "templates"
    templates_dir.mkdir(exist_ok=True)

    static_dir = Path(__file__).parent / "static"
    static_dir.mkdir(exist_ok=True)

    add_log("Dashboard server starting...", "INFO")

    print("Starting Astro Trading Dashboard...")
    print("Open http://localhost:5000 in your browser")

    app.run(debug=True, host="0.0.0.0", port=5000)
