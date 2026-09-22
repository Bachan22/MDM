"""AI Analysis Service for Polar-EMS MDM.
Integrates with the practice AI API (Groq / OpenAI compatible) using backend-only environment variables.
Never exposes API keys to frontend or client responses.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from ..config import AI_API_ENDPOINT, AI_API_KEY, AI_MODEL
from .energy_analysis_service import calculate_energy_analytics
from .equipment_health_service import calculate_equipment_health_analytics
from .mdm_storage_service import get_mdm_status, query_mdm_records
from .resource_risk_service import calculate_station_resource_risk

_offline_until = 0.0


class AIAnalysisService:
    @staticmethod
    def analyze_dataset(
        data: Dict[str, Any],
        analysis_type: str = "general",
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Main entry point for AI-assisted dataset analysis.
        Types: 'energy_consumption', 'equipment_health', 'station_resource_risk', 'general'
        """
        if AI_API_KEY and not AI_API_KEY.startswith("YOUR_"):
            ai_result = AIAnalysisService._call_ai_api(data, analysis_type, context)
            if ai_result:
                return ai_result

        return AIAnalysisService._generate_fallback_response(data, analysis_type)

    @staticmethod
    def _call_ai_api(
        data: Dict[str, Any],
        analysis_type: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Sends focused prompt to practice AI API and parses structured JSON response."""
        global _offline_until
        import time

        if time.time() < _offline_until:
            return None

        system_prompt = (
            "You are an expert Antarctic Research Station Management Data Analytics (MDM) AI. "
            "Analyze the provided empirical station telemetry statistics and produce a strict JSON response. "
            "CRITICAL: Do NOT invent fake measurements. Only draw conclusions supported by the provided data. "
            "Output JSON with these exact keys: "
            "{\n"
            '  "summary": "Concise 1-2 sentence executive finding.",\n'
            '  "key_findings": ["Bullet 1 with evidence", "Bullet 2 with evidence"],\n'
            '  "risk_level": "LOW" | "MODERATE" | "HIGH" | "CRITICAL",\n'
            '  "primary_driver": "Main operational or environmental driver",\n'
            '  "anomalies": ["Observed anomaly or nominal note"],\n'
            '  "recommendations": ["Actionable operator recommendation"],\n'
            '  "supporting_metrics": {"key": "value"},\n'
            '  "limitations": ["Data limitations if any"]\n'
            "}"
        )

        user_content = json.dumps({
            "analysis_type": analysis_type,
            "station_data_summary": data,
            "context": context or {}
        }, indent=2)

        payload = {
            "model": AI_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Analyze this station data for {analysis_type}:\n{user_content}"}
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"}
        }

        try:
            req = urllib.request.Request(
                AI_API_ENDPOINT,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {AI_API_KEY}"
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                if resp.status == 200:
                    resp_json = json.loads(resp.read().decode("utf-8"))
                    content_str = resp_json["choices"][0]["message"]["content"]
                    parsed = json.loads(content_str)
                    parsed["source"] = f"AI-Powered Analysis ({AI_MODEL})"
                    return parsed
        except urllib.error.HTTPError:
            _offline_until = time.time() + 15.0
        except Exception:
            _offline_until = time.time() + 15.0

        return None

    @staticmethod
    def chat_with_analyst(
        message: str,
        dashboard_context: Optional[Dict[str, Any]] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Processes operator questions using structured two-level dataset context.
        Answers questions about uploaded data, energy trends, equipment anomalies, and station resource risk.
        """
        dashboard_context = dashboard_context or {}
        conversation_history = conversation_history or []

        # Check dataset status
        status = get_mdm_status()
        if not status.has_data:
            return {
                "answer": "No dataset is currently uploaded. Please upload a CSV, XLSX, or XLS station file in the Data Upload section to begin data-grounded analysis.",
                "key_metrics": ["Connected records: 0", "Active stations: 0"],
                "evidence": ["The database contains 0 uploaded records."],
                "recommendations": ["Navigate to Data Upload and select a station telemetry file."],
                "confidence": "high",
                "data_limitations": ["No empirical dataset connected."],
                "source": "System Context Engine"
            }

        selected_station = dashboard_context.get("selected_station")
        date_range = dashboard_context.get("date_range", {})
        start_date = date_range.get("start")
        end_date = date_range.get("end")

        # Level 1: Consolidated computed metrics
        energy = calculate_energy_analytics(selected_station, start_date, end_date).dict()
        equipment = calculate_equipment_health_analytics(selected_station, start_date, end_date).dict()
        resource = calculate_station_resource_risk(selected_station, start_date, end_date).dict()

        # Level 2: Targeted records based on question intent
        msg_lower = message.lower()
        targeted_data: Dict[str, Any] = {}

        # If user asks about what data is used or upload metadata
        if "what data" in msg_lower or "dataset" in msg_lower or "files" in msg_lower or "upload" in msg_lower:
            targeted_data["dataset_metadata"] = {
                "total_records": status.records_count,
                "total_stations": status.stations_count,
                "stations_list": status.stations,
                "date_range": f"{status.date_range_start} to {status.date_range_end}",
                "uploaded_files": [
                    {
                        "id": d.id,
                        "filename": d.filename,
                        "rows_accepted": d.rows_accepted,
                        "duplicates_removed": d.duplicates_removed,
                        "period": f"{d.start_date} to {d.end_date}"
                    }
                    for d in status.datasets
                ]
            }

        # If user asks about peak demand or consumption spikes
        if "peak" in msg_lower or "highest" in msg_lower or "surge" in msg_lower or "spike" in msg_lower:
            all_records = query_mdm_records(station=selected_station, start_date=start_date, end_date=end_date)
            sorted_by_energy = sorted(
                [r for r in all_records if r.get("energy_consumption") is not None],
                key=lambda r: float(r["energy_consumption"]),
                reverse=True
            )[:5]
            targeted_data["top_peak_records"] = [
                {
                    "timestamp": r["timestamp"],
                    "station": r["station"],
                    "energy_kwh": r.get("energy_consumption"),
                    "equipment_load_kw": r.get("equipment_load"),
                    "temperature_c": r.get("temperature")
                }
                for r in sorted_by_energy
            ]

        # If user asks about anomalies or equipment
        if "anomal" in msg_lower or "equipment" in msg_lower or "fail" in msg_lower or "machine" in msg_lower:
            targeted_data["monitored_equipment"] = equipment.get("equipment_records", [])[:5]
            targeted_data["recent_anomaly_events"] = equipment.get("anomaly_timeline", [])[:8]

        # If user asks about battery or storage
        if "battery" in msg_lower or "soc" in msg_lower or "deplet" in msg_lower:
            all_records = query_mdm_records(station=selected_station, start_date=start_date, end_date=end_date)
            bat_records = [r for r in all_records if r.get("battery_level") is not None]
            if bat_records:
                sorted_by_bat = sorted(bat_records, key=lambda r: float(r["battery_level"]))[:5]
                targeted_data["lowest_battery_observations"] = [
                    {
                        "timestamp": r["timestamp"],
                        "station": r["station"],
                        "battery_soc_pct": r.get("battery_level"),
                        "energy_demand_kw": r.get("energy_consumption"),
                        "solar_kw": r.get("solar_generation")
                    }
                    for r in sorted_by_bat
                ]

        # Build full compact prompt context
        prompt_context = {
            "current_dashboard_filter": {
                "station": selected_station or "All Stations",
                "start_date": start_date or status.date_range_start,
                "end_date": end_date or status.date_range_end,
                "active_module": dashboard_context.get("active_module", "overview")
            },
            "dataset_provenance": {
                "records_count": status.records_count,
                "stations": status.stations,
                "period": f"{status.date_range_start} -> {status.date_range_end}",
                "total_datasets_uploaded": status.datasets_count
            },
            "energy_summary": {
                "total_energy": energy.get("total_energy_kwh"),
                "unit": energy.get("total_energy_unit"),
                "avg_power_kw": energy.get("avg_power_kw"),
                "peak_demand_kw": energy.get("peak_demand_kw"),
                "trend_direction": energy.get("trend_direction"),
                "trend_pct": energy.get("trend_pct"),
                "consumption_by_station": energy.get("consumption_by_station")
            },
            "equipment_summary": {
                "records_analyzed": equipment.get("records_analyzed"),
                "anomalies_detected": equipment.get("anomalies_detected"),
                "high_risk_signals": equipment.get("high_risk_signals_count"),
                "overall_risk_level": equipment.get("overall_risk_level"),
                "methodology_note": equipment.get("methodology_note")
            },
            "station_resource_risk_summary": {
                "overall_network_risk": resource.get("overall_network_risk"),
                "high_risk_stations_count": resource.get("high_risk_stations_count"),
                "station_risks": resource.get("station_risks", [])[:6]
            },
            "targeted_data": targeted_data
        }

        # Attempt AI API completion
        if AI_API_KEY and not AI_API_KEY.startswith("YOUR_"):
            ai_chat_resp = AIAnalysisService._call_chat_api(message, prompt_context, conversation_history)
            if ai_chat_resp:
                return ai_chat_resp

        # Deterministic fallback response grounded in prompt_context
        return AIAnalysisService._generate_chat_fallback(message, prompt_context)

    @staticmethod
    def _call_chat_api(
        user_message: str,
        context_data: Dict[str, Any],
        history: List[Dict[str, str]]
    ) -> Optional[Dict[str, Any]]:
        """Invokes chat API with structured response formatting."""
        global _offline_until
        import time

        if time.time() < _offline_until:
            return None

        system_instruction = (
            "You are an expert AI Analyst for Antarctic Research Station Management Data Analytics (POLAR-EMS). "
            "You are answering questions from the station operations manager based ON THE ACTUAL CONNECTED DATASET AND DASHBOARD STATE. "
            "CRITICAL INTEGRITY RULES:\n"
            "1. Ground every statement in the provided context_data.\n"
            "2. Never fabricate numbers, probabilities, or fake events.\n"
            "3. Clearly distinguish 'Observed facts' from 'Contributing factors' and 'Recommendations'.\n"
            "4. If requested data was not recorded (e.g. no solar sensor or no fault codes), explicitly state that limitation.\n"
            "5. Respond in valid JSON matching this schema:\n"
            "{\n"
            '  "answer": "Detailed markdown explanation answering the question directly.",\n'
            '  "key_metrics": ["Metric 1: value", "Metric 2: value"],\n'
            '  "evidence": ["Exact observation with timestamps/values from data"],\n'
            '  "recommendations": ["Actionable recommendation"],\n'
            '  "confidence": "high" | "medium" | "low",\n'
            '  "data_limitations": ["Any limitation in available columns or timeline"]\n'
            "}"
        )

        messages = [{"role": "system", "content": system_instruction}]

        # Append compact conversation history (last 4 turns)
        for turn in history[-4:]:
            role = turn.get("role", "user")
            content = turn.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

        messages.append({
            "role": "user",
            "content": f"Context Data:\n{json.dumps(context_data, indent=1)}\n\nOperator Question: {user_message}"
        })

        payload = {
            "model": AI_MODEL,
            "messages": messages,
            "temperature": 0.2,
            "response_format": {"type": "json_object"}
        }

        try:
            req = urllib.request.Request(
                AI_API_ENDPOINT,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {AI_API_KEY}"
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=6.0) as resp:
                if resp.status == 200:
                    resp_json = json.loads(resp.read().decode("utf-8"))
                    content_str = resp_json["choices"][0]["message"]["content"]
                    parsed = json.loads(content_str)
                    parsed["source"] = f"AI Analyst ({AI_MODEL})"
                    return parsed
        except urllib.error.HTTPError:
            _offline_until = time.time() + 15.0
        except Exception:
            _offline_until = time.time() + 15.0

        return None

    @staticmethod
    def _generate_chat_fallback(message: str, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Grounded statistical fallback for analyst questions when AI API is unavailable."""
        msg_lower = message.lower()
        energy = ctx.get("energy_summary", {})
        equipment = ctx.get("equipment_summary", {})
        resource = ctx.get("station_resource_risk_summary", {})
        prov = ctx.get("dataset_provenance", {})

        if "what data" in msg_lower or "dataset" in msg_lower or "files" in msg_lower:
            return {
                "answer": (
                    f"The current analysis uses **{prov.get('total_datasets_uploaded', 1)} uploaded dataset(s)** "
                    f"containing **{prov.get('records_count', 0):,} cleaned records** across stations **{', '.join(prov.get('stations', []))}**. "
                    f"The covered operational timeframe spans **{prov.get('period', 'the active range')}**."
                ),
                "key_metrics": [
                    f"Cleaned records: {prov.get('records_count', 0):,}",
                    f"Active stations: {len(prov.get('stations', []))}",
                    f"Data period: {prov.get('period')}"
                ],
                "evidence": [f"Registered datasets: {prov.get('total_datasets_uploaded', 1)}"],
                "recommendations": ["Upload additional historical files to expand timeline analytics."],
                "confidence": "high",
                "data_limitations": [],
                "source": "Statistical Context Engine"
            }

        if "risk" in msg_lower or "resource" in msg_lower or "stress" in msg_lower:
            net_risk = resource.get("overall_network_risk", "LOW")
            st_risks = resource.get("station_risks", [])
            high_risks = [r for r in st_risks if r.get("risk_level") in ("HIGH", "CRITICAL")]
            top_st = high_risks[0] if high_risks else (st_risks[0] if st_risks else {})

            return {
                "answer": (
                    f"**Observed:** Overall station network resource risk is **{net_risk}**.\n\n"
                    f"**Contributing factors:** {top_st.get('station', 'Station')} exhibits {top_st.get('risk_level', 'LOW')} risk in {top_st.get('resource', 'Energy')} "
                    f"due to: *{top_st.get('main_driver', 'baseline conditions')}* (current value: {top_st.get('current_value', 'N/A')}, historical baseline: {top_st.get('historical_average', 'N/A')})."
                ),
                "key_metrics": [
                    f"Network Risk: {net_risk}",
                    f"High Risk Stations: {resource.get('high_risk_stations_count', 0)}"
                ],
                "evidence": [top_st.get("evidence_text", "Operational values are within nominal range.")],
                "recommendations": ["Monitor battery draw and evaluate heating load shedding priorities."],
                "confidence": "high",
                "data_limitations": [],
                "source": "Statistical Context Engine"
            }

        if "equipment" in msg_lower or "anomal" in msg_lower or "fault" in msg_lower or "machine" in msg_lower:
            anom_cnt = equipment.get("anomalies_detected", 0)
            risk = equipment.get("overall_risk_level", "LOW")
            return {
                "answer": (
                    f"**Observed:** Detected **{anom_cnt} statistical anomaly events** across {equipment.get('records_analyzed', 0):,} monitored telemetry readings. "
                    f"Current observed equipment risk level is **{risk}**.\n\n"
                    f"**Contributing factors:** Operational anomalies represent z-score deviations > 2.2 in equipment power demand or thermal excursions."
                ),
                "key_metrics": [
                    f"Anomalies Detected: {anom_cnt}",
                    f"Equipment Risk: {risk}"
                ],
                "evidence": [f"Evaluated across {equipment.get('records_analyzed', 0)} operational readings."],
                "recommendations": ["Schedule routine unit inspection on monitored equipment."],
                "confidence": "high",
                "data_limitations": ["Risk estimate is derived from statistical deviations; no verified failure labels present in dataset."],
                "source": "Statistical Context Engine"
            }

        # Default energy / general answer
        peak = energy.get("peak_demand_kw", 0)
        avg = energy.get("avg_power_kw", 0)
        trend = energy.get("trend_direction", "Stable")
        trend_pct = energy.get("trend_pct", 0)

        return {
            "answer": (
                f"**Observed:** Gross energy consumption across the selected period totals **{energy.get('total_energy', 0)} {energy.get('unit', 'kWh')}**, "
                f"with an average power demand of **{avg} kW** and a peak demand spike of **{peak} kW**.\n\n"
                f"**Contributing factors:** The consumption trend is **{trend.lower()}** ({trend_pct:+.1f}%) across the active observation window."
            ),
            "key_metrics": [
                f"Total Energy: {energy.get('total_energy')} {energy.get('unit')}",
                f"Average Demand: {avg} kW",
                f"Peak Demand: {peak} kW",
                f"Trend: {trend} ({trend_pct:+.1f}%)"
            ],
            "evidence": [f"Derived from empirical telemetry data for {ctx.get('current_dashboard_filter', {}).get('station', 'All Stations')}."],
            "recommendations": ["Review high-demand baseload schedules during sub-zero thermal excursions."],
            "confidence": "high",
            "data_limitations": [],
            "source": "Statistical Context Engine"
        }

    @staticmethod
    def _generate_fallback_response(data: Dict[str, Any], analysis_type: str) -> Dict[str, Any]:
        """Deterministic statistical fallback when AI API is unavailable."""
        if analysis_type == "energy_consumption":
            total = data.get("total_energy_kwh", 0)
            avg = data.get("avg_power_kw", 0)
            peak = data.get("peak_demand_kw", 0)
            trend = data.get("trend_direction", "Stable")
            trend_pct = data.get("trend_pct", 0)

            return {
                "summary": f"Station energy consumption averaged {avg} kW (peak {peak} kW) with a {trend.lower()} trend ({trend_pct}%).",
                "key_findings": [
                    f"Integrated energy consumption across period: {total} {data.get('total_energy_unit', 'kWh')}.",
                    f"Peak demand spike observed at {peak} kW."
                ],
                "risk_level": "MODERATE" if trend == "Increasing" and trend_pct > 15 else "LOW",
                "primary_driver": "Station operational baseload and thermal heating requirements.",
                "anomalies": ["Peak load surges during sub-zero thermal excursions."] if peak > avg * 1.3 else [],
                "recommendations": ["Monitor heating schedules during high demand periods."],
                "supporting_metrics": {"avg_power_kw": avg, "peak_demand_kw": peak, "trend": trend},
                "limitations": data.get("missing_fields_notice", []),
                "source": "AI-Assisted Analysis (Statistical Engine)"
            }

        if analysis_type == "equipment_health":
            anom_cnt = data.get("anomalies_detected", 0)
            risk = data.get("overall_risk_level", "LOW")
            recs = data.get("equipment_records", [])
            most_affected = recs[0].get("equipment_id") if recs else "Plant"

            return {
                "summary": f"Equipment health evaluation detected {anom_cnt} statistical operating deviations across monitored units.",
                "key_findings": [
                    f"Observed network risk level: {risk}.",
                    f"Most affected monitored unit: {most_affected} with {anom_cnt} anomaly events."
                ],
                "risk_level": risk,
                "primary_driver": recs[0].get("main_signal") if recs else "Nominal operating telemetry",
                "anomalies": [f"{most_affected}: {anom_cnt} excursions exceeding 2.2 standard deviations."],
                "recommendations": ["Inspect unit telemetry and schedule routine mechanical check."],
                "supporting_metrics": {"anomalies_detected": anom_cnt, "risk_level": risk},
                "limitations": ["Risk estimate is derived from statistical deviations; no verified failure labels present in dataset."],
                "source": "AI-Assisted Analysis (Statistical Engine)"
            }

        st_risks = data.get("station_risks", [])
        net_risk = data.get("overall_network_risk", "LOW")

        return {
            "summary": f"Station network resource risk evaluated at {net_risk} across {data.get('stations_analyzed', 0)} active stations.",
            "key_findings": [
                f"{len([r for r in st_risks if r.get('risk_level') == 'HIGH'])} station(s) require active resource monitoring.",
                f"Primary resource pressure: {st_risks[0].get('resource') if st_risks else 'Nominal'}."
            ],
            "risk_level": net_risk,
            "primary_driver": st_risks[0].get("main_driver") if st_risks else "Stable operational margins",
            "anomalies": [],
            "recommendations": ["Maintain active buffer for critical heating and power dispatch."],
            "supporting_metrics": {"stations_analyzed": data.get("stations_analyzed", 0)},
            "limitations": data.get("missing_fields_notice", []),
            "source": "AI-Assisted Analysis (Statistical Engine)"
        }

    @staticmethod
    def generate_management_insights(
        energy_data: Dict[str, Any],
        equipment_data: Dict[str, Any],
        resource_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Unified overview insights combining the 3 modules."""
        insights: List[Dict[str, Any]] = []

        if energy_data and energy_data.get("has_data"):
            ai_e = AIAnalysisService.analyze_dataset(energy_data, "energy_consumption")
            insights.append({
                "category": "Energy Dynamics",
                "title": "Energy Consumption & Demand Profile",
                "finding": ai_e.get("summary", ""),
                "risk_level": ai_e.get("risk_level", "LOW"),
                "primary_driver": ai_e.get("primary_driver", "Station demand"),
                "recommendation": ai_e.get("recommendations", ["Continue standard monitoring."])[0],
                "evidence": f"Peak: {energy_data.get('peak_demand_kw')} kW, Avg: {energy_data.get('avg_power_kw')} kW.",
                "source": ai_e.get("source", "AI-Assisted Analysis")
            })

        if equipment_data and equipment_data.get("has_data"):
            ai_eq = AIAnalysisService.analyze_dataset(equipment_data, "equipment_health")
            insights.append({
                "category": "Equipment Health",
                "title": "Operational Anomaly & Unit Health",
                "finding": ai_eq.get("summary", ""),
                "risk_level": ai_eq.get("risk_level", "LOW"),
                "primary_driver": ai_eq.get("primary_driver", "Operating telemetry"),
                "recommendation": ai_eq.get("recommendations", ["Monitor unit telemetry."])[0],
                "evidence": f"Anomalies: {equipment_data.get('anomalies_detected', 0)} events detected.",
                "source": ai_eq.get("source", "AI-Assisted Analysis")
            })

        if resource_data and resource_data.get("has_data"):
            ai_rr = AIAnalysisService.analyze_dataset(resource_data, "station_resource_risk")
            insights.append({
                "category": "Resource Allocation",
                "title": "Station Resource & Storage Status",
                "finding": ai_rr.get("summary", ""),
                "risk_level": ai_rr.get("risk_level", "LOW"),
                "primary_driver": ai_rr.get("primary_driver", "Resource balance"),
                "recommendation": ai_rr.get("recommendations", ["Maintain standard reserves."])[0],
                "evidence": f"Network risk: {resource_data.get('overall_network_risk', 'LOW')}.",
                "source": ai_rr.get("source", "AI-Assisted Analysis")
            })

        return insights
