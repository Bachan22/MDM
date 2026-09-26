"""Deterministic data aggregation engine for Polar-EMS MDM Dashboard.
Handles Weekly, Monthly, Yearly, Range aggregations and previous-period comparisons.
Strictly calculates values from actual uploaded SQLite telemetry records (zero fake data).
"""
from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from ..db import get_conn
from ..schemas.mdm_models import AggregatedPoint, PeriodAggregationResponse


MONTH_NAMES = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
]

FULL_MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]


def _get_station_clause(station: Optional[str]) -> Tuple[str, List[Any]]:
    if station and station.lower() not in ("all", "all stations", ""):
        return " AND station = ?", [station]
    return "", []


def _parse_anchor_date(anchor_date_str: Optional[str], conn) -> date:
    """Parses anchor date string or defaults to latest recorded date in SQLite."""
    if anchor_date_str:
        try:
            return datetime.strptime(anchor_date_str[:10], "%Y-%m-%d").date()
        except Exception:
            pass

    # Find latest date in dataset
    row = conn.execute("SELECT MAX(timestamp) as max_ts FROM mdm_records").fetchone()
    if row and row["max_ts"]:
        try:
            return datetime.strptime(str(row["max_ts"])[:10], "%Y-%m-%d").date()
        except Exception:
            pass

    return date.today()


def _get_available_calendar_dates(conn, station: Optional[str]) -> List[str]:
    """Returns list of distinct YYYY-MM-DD dates with available telemetry."""
    st_clause, st_params = _get_station_clause(station)
    sql = f"""
        SELECT DISTINCT substr(timestamp, 1, 10) as dt
        FROM mdm_records
        WHERE timestamp IS NOT NULL AND energy_consumption IS NOT NULL {st_clause}
        ORDER BY dt ASC
    """
    rows = conn.execute(sql, tuple(st_params)).fetchall()
    return [r["dt"] for r in rows if r["dt"] and len(r["dt"]) == 10]


def aggregate_mdm_period(
    station: Optional[str] = None,
    period: str = "monthly",
    anchor_date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> PeriodAggregationResponse:
    """
    Performs deterministic aggregation across the uploaded dataset.
    Supported periods: 'weekly', 'monthly', 'yearly', 'range' (or 'daily').
    """
    conn = get_conn()
    available_dates = _get_available_calendar_dates(conn, station)

    if not available_dates:
        # Check if there are any records without energy_consumption
        cnt_row = conn.execute("SELECT COUNT(*) as c FROM mdm_records").fetchone()
        total_recs = cnt_row["c"] if cnt_row else 0
        return PeriodAggregationResponse(
            has_data=False,
            period=period,
            period_label="No Dataset",
            anchor_date=anchor_date or date.today().isoformat(),
            current_total=0.0,
            previous_total=None,
            trend_pct=None,
            trend_direction=None,
            avg_consumption=None,
            peak_value=None,
            peak_label=None,
            lowest_value=None,
            lowest_label=None,
            record_count=total_recs,
            points=[],
            available_calendar_dates=[],
            missing_notice="No operational dataset available. Upload CSV/Excel to begin."
        )

    anchor = _parse_anchor_date(anchor_date, conn)
    period_lower = (period or "monthly").lower()

    if period_lower == "weekly":
        return _aggregate_weekly(conn, station, anchor, available_dates)
    elif period_lower == "yearly":
        return _aggregate_yearly(conn, station, anchor, available_dates)
    elif period_lower in ("range", "daily", "custom"):
        return _aggregate_range(conn, station, anchor, start_date, end_date, available_dates)
    else:
        # Default: monthly
        return _aggregate_monthly(conn, station, anchor, available_dates)


def _aggregate_weekly(
    conn,
    station: Optional[str],
    anchor: date,
    available_dates: List[str]
) -> PeriodAggregationResponse:
    """Aggregates 7-day Monday-to-Sunday window around anchor date."""
    weekday = anchor.weekday()  # Monday is 0, Sunday is 6
    mon = anchor - timedelta(days=weekday)
    sun = mon + timedelta(days=6)

    st_clause, st_params = _get_station_clause(station)

    start_str = mon.isoformat()
    end_str = f"{sun.isoformat()} 23:59:59"

    sql = f"""
        SELECT substr(timestamp, 1, 10) as dt,
               SUM(energy_consumption) as daily_energy,
               COUNT(*) as rec_count
        FROM mdm_records
        WHERE timestamp >= ? AND timestamp <= ? AND energy_consumption IS NOT NULL {st_clause}
        GROUP BY dt
        ORDER BY dt ASC
    """
    rows = conn.execute(sql, (start_str, end_str, *st_params)).fetchall()
    day_map = {r["dt"]: (float(r["daily_energy"]), int(r["rec_count"])) for r in rows}

    points: List[AggregatedPoint] = []
    current_total = 0.0
    active_days_count = 0
    total_records = 0

    for i in range(7):
        cur_day = mon + timedelta(days=i)
        cur_str = cur_day.isoformat()
        day_name = cur_day.strftime("%a")
        full_label = cur_day.strftime("%A, %B %d, %Y")

        if cur_str in day_map:
            val, count = day_map[cur_str]
            points.append(AggregatedPoint(
                key=cur_str,
                label=f"{day_name} {cur_day.day}",
                full_date_label=full_label,
                value=round(val, 2),
                record_count=count,
                is_peak=False,
                is_lowest=False,
                has_data=True
            ))
            current_total += val
            active_days_count += 1
            total_records += count
        else:
            points.append(AggregatedPoint(
                key=cur_str,
                label=f"{day_name} {cur_day.day}",
                full_date_label=full_label,
                value=0.0,
                record_count=0,
                is_peak=False,
                is_lowest=False,
                has_data=False
            ))

    _mark_peaks(points)
    _compute_point_changes(points)

    # Previous 7-day window comparison
    prev_mon = mon - timedelta(days=7)
    prev_sun = mon - timedelta(days=1)
    prev_sql = f"""
        SELECT SUM(energy_consumption) as prev_total, COUNT(*) as prev_count
        FROM mdm_records
        WHERE timestamp >= ? AND timestamp <= ? AND energy_consumption IS NOT NULL {st_clause}
    """
    prev_row = conn.execute(prev_sql, (prev_mon.isoformat(), f"{prev_sun.isoformat()} 23:59:59", *st_params)).fetchone()
    prev_total = float(prev_row["prev_total"]) if prev_row and prev_row["prev_total"] is not None else None
    prev_count = int(prev_row["prev_count"]) if prev_row and prev_row["prev_count"] else 0

    trend_pct, trend_dir = _calculate_trend(current_total, prev_total, prev_count)

    avg_daily = round(current_total / active_days_count, 2) if active_days_count > 0 else 0.0
    peak_pt = max([p for p in points if p.has_data], key=lambda x: x.value, default=None)
    lowest_pt = min([p for p in points if p.has_data], key=lambda x: x.value, default=None)

    period_label = f"{mon.strftime('%b %d')} – {sun.strftime('%b %d, %Y')}"

    return PeriodAggregationResponse(
        has_data=active_days_count > 0,
        period="weekly",
        period_label=period_label,
        anchor_date=anchor.isoformat(),
        current_total=round(current_total, 2),
        previous_total=round(prev_total, 2) if prev_total is not None else None,
        trend_pct=trend_pct,
        trend_direction=trend_dir,
        avg_consumption=avg_daily,
        peak_value=peak_pt.value if peak_pt else None,
        peak_label=peak_pt.label if peak_pt else None,
        lowest_value=lowest_pt.value if lowest_pt and len([p for p in points if p.has_data]) >= 2 else None,
        lowest_label=lowest_pt.label if lowest_pt and len([p for p in points if p.has_data]) >= 2 else None,
        record_count=total_records,
        points=points,
        available_calendar_dates=available_dates,
        missing_notice="No telemetry available for this week." if active_days_count == 0 else None
    )


def _aggregate_monthly(
    conn,
    station: Optional[str],
    anchor: date,
    available_dates: List[str]
) -> PeriodAggregationResponse:
    """Aggregates entire calendar month of anchor date."""
    year = anchor.year
    month = anchor.month
    _, num_days = calendar.monthrange(year, month)

    month_start = date(year, month, 1)
    month_end = date(year, month, num_days)

    st_clause, st_params = _get_station_clause(station)

    start_str = month_start.isoformat()
    end_str = f"{month_end.isoformat()} 23:59:59"

    sql = f"""
        SELECT substr(timestamp, 1, 10) as dt,
               SUM(energy_consumption) as daily_energy,
               COUNT(*) as rec_count
        FROM mdm_records
        WHERE timestamp >= ? AND timestamp <= ? AND energy_consumption IS NOT NULL {st_clause}
        GROUP BY dt
        ORDER BY dt ASC
    """
    rows = conn.execute(sql, (start_str, end_str, *st_params)).fetchall()
    day_map = {r["dt"]: (float(r["daily_energy"]), int(r["rec_count"])) for r in rows}

    points: List[AggregatedPoint] = []
    current_total = 0.0
    active_days_count = 0
    total_records = 0

    month_abbr = MONTH_NAMES[month - 1]
    full_month_name = FULL_MONTH_NAMES[month - 1]

    for d in range(1, num_days + 1):
        cur_day = date(year, month, d)
        cur_str = cur_day.isoformat()
        day_label = f"{month_abbr} {d:02d}"
        full_label = f"{full_month_name} {d}, {year}"

        if cur_str in day_map:
            val, count = day_map[cur_str]
            points.append(AggregatedPoint(
                key=cur_str,
                label=day_label,
                full_date_label=full_label,
                value=round(val, 2),
                record_count=count,
                is_peak=False,
                is_lowest=False,
                has_data=True
            ))
            current_total += val
            active_days_count += 1
            total_records += count
        else:
            points.append(AggregatedPoint(
                key=cur_str,
                label=day_label,
                full_date_label=full_label,
                value=0.0,
                record_count=0,
                is_peak=False,
                is_lowest=False,
                has_data=False
            ))

    _mark_peaks(points)
    _compute_point_changes(points)

    # Previous calendar month comparison
    if month == 1:
        prev_year = year - 1
        prev_month = 12
    else:
        prev_year = year
        prev_month = month - 1

    _, prev_num_days = calendar.monthrange(prev_year, prev_month)
    prev_start = date(prev_year, prev_month, 1)
    prev_end = date(prev_year, prev_month, prev_num_days)

    prev_sql = f"""
        SELECT SUM(energy_consumption) as prev_total, COUNT(*) as prev_count
        FROM mdm_records
        WHERE timestamp >= ? AND timestamp <= ? AND energy_consumption IS NOT NULL {st_clause}
    """
    prev_row = conn.execute(prev_sql, (prev_start.isoformat(), f"{prev_end.isoformat()} 23:59:59", *st_params)).fetchone()
    prev_total = float(prev_row["prev_total"]) if prev_row and prev_row["prev_total"] is not None else None
    prev_count = int(prev_row["prev_count"]) if prev_row and prev_row["prev_count"] else 0

    trend_pct, trend_dir = _calculate_trend(current_total, prev_total, prev_count)

    avg_daily = round(current_total / active_days_count, 2) if active_days_count > 0 else 0.0
    peak_pt = max([p for p in points if p.has_data], key=lambda x: x.value, default=None)
    lowest_pt = min([p for p in points if p.has_data], key=lambda x: x.value, default=None)

    period_label = f"{full_month_name} {year}"

    return PeriodAggregationResponse(
        has_data=active_days_count > 0,
        period="monthly",
        period_label=period_label,
        anchor_date=anchor.isoformat(),
        current_total=round(current_total, 2),
        previous_total=round(prev_total, 2) if prev_total is not None else None,
        trend_pct=trend_pct,
        trend_direction=trend_dir,
        avg_consumption=avg_daily,
        peak_value=peak_pt.value if peak_pt else None,
        peak_label=peak_pt.label if peak_pt else None,
        lowest_value=lowest_pt.value if lowest_pt and len([p for p in points if p.has_data]) >= 2 else None,
        lowest_label=lowest_pt.label if lowest_pt and len([p for p in points if p.has_data]) >= 2 else None,
        record_count=total_records,
        points=points,
        available_calendar_dates=available_dates,
        missing_notice=f"No telemetry available for {period_label}." if active_days_count == 0 else None
    )


def _aggregate_yearly(
    conn,
    station: Optional[str],
    anchor: date,
    available_dates: List[str]
) -> PeriodAggregationResponse:
    """Aggregates 12 calendar months (Jan to Dec) of anchor date's year."""
    year = anchor.year
    st_clause, st_params = _get_station_clause(station)

    start_str = f"{year}-01-01"
    end_str = f"{year}-12-31 23:59:59"

    sql = f"""
        SELECT substr(timestamp, 1, 7) as ym,
               SUM(energy_consumption) as monthly_energy,
               COUNT(*) as rec_count
        FROM mdm_records
        WHERE timestamp >= ? AND timestamp <= ? AND energy_consumption IS NOT NULL {st_clause}
        GROUP BY ym
        ORDER BY ym ASC
    """
    rows = conn.execute(sql, (start_str, end_str, *st_params)).fetchall()
    month_map = {r["ym"]: (float(r["monthly_energy"]), int(r["rec_count"])) for r in rows}

    points: List[AggregatedPoint] = []
    current_total = 0.0
    active_months_count = 0
    total_records = 0

    for m in range(1, 13):
        ym_key = f"{year}-{m:02d}"
        label = MONTH_NAMES[m - 1]
        full_label = f"{FULL_MONTH_NAMES[m - 1]} {year}"

        if ym_key in month_map:
            val, count = month_map[ym_key]
            points.append(AggregatedPoint(
                key=ym_key,
                label=label,
                full_date_label=full_label,
                value=round(val, 2),
                record_count=count,
                is_peak=False,
                is_lowest=False,
                has_data=True
            ))
            current_total += val
            active_months_count += 1
            total_records += count
        else:
            points.append(AggregatedPoint(
                key=ym_key,
                label=label,
                full_date_label=full_label,
                value=0.0,
                record_count=0,
                is_peak=False,
                is_lowest=False,
                has_data=False
            ))

    _mark_peaks(points)
    _compute_point_changes(points)

    # Previous year comparison
    prev_year = year - 1
    prev_start = f"{prev_year}-01-01"
    prev_end = f"{prev_year}-12-31 23:59:59"

    prev_sql = f"""
        SELECT SUM(energy_consumption) as prev_total, COUNT(*) as prev_count
        FROM mdm_records
        WHERE timestamp >= ? AND timestamp <= ? AND energy_consumption IS NOT NULL {st_clause}
    """
    prev_row = conn.execute(prev_sql, (prev_start, prev_end, *st_params)).fetchone()
    prev_total = float(prev_row["prev_total"]) if prev_row and prev_row["prev_total"] is not None else None
    prev_count = int(prev_row["prev_count"]) if prev_row and prev_row["prev_count"] else 0

    trend_pct, trend_dir = _calculate_trend(current_total, prev_total, prev_count)

    avg_monthly = round(current_total / active_months_count, 2) if active_months_count > 0 else 0.0
    peak_pt = max([p for p in points if p.has_data], key=lambda x: x.value, default=None)
    lowest_pt = min([p for p in points if p.has_data], key=lambda x: x.value, default=None)

    period_label = f"{year}"

    return PeriodAggregationResponse(
        has_data=active_months_count > 0,
        period="yearly",
        period_label=period_label,
        anchor_date=anchor.isoformat(),
        current_total=round(current_total, 2),
        previous_total=round(prev_total, 2) if prev_total is not None else None,
        trend_pct=trend_pct,
        trend_direction=trend_dir,
        avg_consumption=avg_monthly,
        peak_value=peak_pt.value if peak_pt else None,
        peak_label=peak_pt.label if peak_pt else None,
        lowest_value=lowest_pt.value if lowest_pt and len([p for p in points if p.has_data]) >= 2 else None,
        lowest_label=lowest_pt.label if lowest_pt and len([p for p in points if p.has_data]) >= 2 else None,
        record_count=total_records,
        points=points,
        available_calendar_dates=available_dates,
        missing_notice=f"No telemetry available for {year}." if active_months_count == 0 else None
    )


def _aggregate_range(
    conn,
    station: Optional[str],
    anchor: date,
    start_date: Optional[str],
    end_date: Optional[str],
    available_dates: List[str]
) -> PeriodAggregationResponse:
    """Aggregates a specified date range (or default last 30 days ending on anchor date)."""
    st_clause, st_params = _get_station_clause(station)

    if not start_date:
        start_dt = anchor - timedelta(days=29)
        end_dt = anchor
    else:
        try:
            start_dt = datetime.strptime(start_date[:10], "%Y-%m-%d").date()
        except Exception:
            start_dt = anchor - timedelta(days=29)

        if end_date:
            try:
                end_dt = datetime.strptime(end_date[:10], "%Y-%m-%d").date()
            except Exception:
                end_dt = anchor
        else:
            end_dt = anchor

    if start_dt > end_dt:
        start_dt, end_dt = end_dt, start_dt

    num_days = (end_dt - start_dt).days + 1
    start_str = start_dt.isoformat()
    end_str = f"{end_dt.isoformat()} 23:59:59"

    sql = f"""
        SELECT substr(timestamp, 1, 10) as dt,
               SUM(energy_consumption) as daily_energy,
               COUNT(*) as rec_count
        FROM mdm_records
        WHERE timestamp >= ? AND timestamp <= ? AND energy_consumption IS NOT NULL {st_clause}
        GROUP BY dt
        ORDER BY dt ASC
    """
    rows = conn.execute(sql, (start_str, end_str, *st_params)).fetchall()
    day_map = {r["dt"]: (float(r["daily_energy"]), int(r["rec_count"])) for r in rows}

    points: List[AggregatedPoint] = []
    current_total = 0.0
    active_days_count = 0
    total_records = 0

    for i in range(num_days):
        cur_day = start_dt + timedelta(days=i)
        cur_str = cur_day.isoformat()
        label = cur_day.strftime("%b %d")
        full_label = cur_day.strftime("%B %d, %Y")

        if cur_str in day_map:
            val, count = day_map[cur_str]
            points.append(AggregatedPoint(
                key=cur_str,
                label=label,
                full_date_label=full_label,
                value=round(val, 2),
                record_count=count,
                is_peak=False,
                is_lowest=False,
                has_data=True
            ))
            current_total += val
            active_days_count += 1
            total_records += count
        else:
            points.append(AggregatedPoint(
                key=cur_str,
                label=label,
                full_date_label=full_label,
                value=0.0,
                record_count=0,
                is_peak=False,
                is_lowest=False,
                has_data=False
            ))

    _mark_peaks(points)
    _compute_point_changes(points)

    # Previous period window
    prev_start_dt = start_dt - timedelta(days=num_days)
    prev_end_dt = start_dt - timedelta(days=1)
    prev_sql = f"""
        SELECT SUM(energy_consumption) as prev_total, COUNT(*) as prev_count
        FROM mdm_records
        WHERE timestamp >= ? AND timestamp <= ? AND energy_consumption IS NOT NULL {st_clause}
    """
    prev_row = conn.execute(prev_sql, (prev_start_dt.isoformat(), f"{prev_end_dt.isoformat()} 23:59:59", *st_params)).fetchone()
    prev_total = float(prev_row["prev_total"]) if prev_row and prev_row["prev_total"] is not None else None
    prev_count = int(prev_row["prev_count"]) if prev_row and prev_row["prev_count"] else 0

    trend_pct, trend_dir = _calculate_trend(current_total, prev_total, prev_count)

    avg_daily = round(current_total / active_days_count, 2) if active_days_count > 0 else 0.0
    peak_pt = max([p for p in points if p.has_data], key=lambda x: x.value, default=None)
    lowest_pt = min([p for p in points if p.has_data], key=lambda x: x.value, default=None)

    period_label = f"{start_dt.strftime('%b %d')} – {end_dt.strftime('%b %d, %Y')}"

    return PeriodAggregationResponse(
        has_data=active_days_count > 0,
        period="range",
        period_label=period_label,
        anchor_date=anchor.isoformat(),
        current_total=round(current_total, 2),
        previous_total=round(prev_total, 2) if prev_total is not None else None,
        trend_pct=trend_pct,
        trend_direction=trend_dir,
        avg_consumption=avg_daily,
        peak_value=peak_pt.value if peak_pt else None,
        peak_label=peak_pt.label if peak_pt else None,
        lowest_value=lowest_pt.value if lowest_pt and len([p for p in points if p.has_data]) >= 2 else None,
        lowest_label=lowest_pt.label if lowest_pt and len([p for p in points if p.has_data]) >= 2 else None,
        record_count=total_records,
        points=points,
        available_calendar_dates=available_dates,
        missing_notice=f"No telemetry available between {period_label}." if active_days_count == 0 else None
    )


def _mark_peaks(points: List[AggregatedPoint]) -> None:
    """Marks the highest and lowest valid data points."""
    valid = [p for p in points if p.has_data and p.value > 0]
    if not valid:
        return
    max_val = max(p.value for p in valid)
    min_val = min(p.value for p in valid)

    for p in points:
        if p.has_data and p.value == max_val:
            p.is_peak = True
            break

    if len(valid) >= 2 and min_val < max_val:
        for p in points:
            if p.has_data and p.value == min_val:
                p.is_lowest = True
                break


def _compute_point_changes(points: List[AggregatedPoint]) -> None:
    """Computes point-to-point percentage change for tooltips."""
    last_valid_val = None
    for p in points:
        if p.has_data and p.value > 0:
            if last_valid_val is not None and last_valid_val > 0:
                p.change_pct = round(((p.value - last_valid_val) / last_valid_val) * 100.0, 1)
            last_valid_val = p.value


def _calculate_trend(
    current_total: float,
    prev_total: Optional[float],
    prev_count: int
) -> Tuple[Optional[float], Optional[str]]:
    """Strictly computes percentage change without fake data."""
    if prev_total is None or prev_count == 0 or prev_total <= 0:
        return None, None

    diff = current_total - prev_total
    pct = round((diff / prev_total) * 100.0, 1)
    if pct > 1.0:
        return pct, "Increasing"
    elif pct < -1.0:
        return pct, "Decreasing"
    else:
        return pct, "Stable"
