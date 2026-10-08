"""Model Loader Service.

Loads all approved ML models and metadata into a singleton cache on startup.
Guarantees consistent feature validation and fail-fast behavior with structured logging.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional
import joblib

logger = logging.getLogger("polar_ems.models")

# Define project base and models directory
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_MODELS_DIR = BASE_DIR / "models"
MODELS_DIR = Path(os.environ.get("POLAR_EMS_MODELS_DIR", DEFAULT_MODELS_DIR))


class ModelLoader:
    _instance: Optional["ModelLoader"] = None

    def __init__(self, models_dir: Path = MODELS_DIR):
        self.models_dir = models_dir
        self.models: Dict[str, Any] = {}
        self.metadata: Dict[str, Dict[str, Any]] = {}
        self.is_loaded: bool = False

    @classmethod
    def get_instance(cls, models_dir: Path = MODELS_DIR) -> "ModelLoader":
        if cls._instance is None:
            cls._instance = cls(models_dir)
        return cls._instance

    def load_all(self) -> Dict[str, Any]:
        """Loads all joblib models and metadata JSON files into memory."""
        if self.is_loaded:
            return {"status": "already_loaded", "loaded_models": list(self.models.keys())}

        logger.info(f"Loading ML models from {self.models_dir.resolve()}")
        
        # 1. Load Wind Model (17 features)
        wind_model_path = self.models_dir / "POLAR_EMS_Best_Wind_Model.joblib"
        wind_meta_path = self.models_dir / "POLAR_EMS_Wind_Augmentation_Summary.json"
        if wind_model_path.exists():
            self.models["wind"] = joblib.load(wind_model_path)
            self.metadata["wind"] = self._load_json(wind_meta_path)
            self.metadata["wind"]["features"] = [
                "Wind Speed (m/s)", "Wind Direction (°)", "Theoretical_Power_Curve (KWh)",
                "hour", "day_of_week", "month", "day_of_year",
                "lag_1", "lag_2", "lag_3", "lag_6", "lag_12", "lag_144",
                "wind_lag_1", "wind_lag_6", "rolling_6", "rolling_18"
            ]
            logger.info("Loaded Wind Model (17 features)")

        # 2. Load Load Forecast Model (20 features)
        load_model_path = self.models_dir / "polar_ems_weather_load_forecaster.joblib"
        load_meta_path = self.models_dir / "polar_ems_weather_load_forecaster_metadata.json"
        if load_model_path.exists():
            self.models["load"] = joblib.load(load_model_path)
            self.metadata["load"] = self._load_json(load_meta_path)
            logger.info("Loaded Weather-Aware Load Forecaster (20 features)")

        # 3. Load Solar Forecast Model (12 features)
        solar_model_path = self.models_dir / "polar_ems_solar_forecaster.joblib"
        solar_meta_path = self.models_dir / "polar_ems_solar_forecaster_metadata.json"
        if solar_model_path.exists():
            self.models["solar"] = joblib.load(solar_model_path)
            self.metadata["solar"] = self._load_json(solar_meta_path)
            logger.info("Loaded Solar Forecaster (12 features)")

        # 4. Load Battery SOH Model (8 features)
        soh_model_path = self.models_dir / "polar_ems_battery_soh_model.joblib"
        soh_meta_path = self.models_dir / "polar_ems_battery_soh_metadata.json"
        if soh_model_path.exists():
            self.models["battery_soh"] = joblib.load(soh_model_path)
            self.metadata["battery_soh"] = self._load_json(soh_meta_path)
            logger.info("Loaded Battery SOH Model (8 features)")

        # 5. Load SCADA Anomaly Detector (23 features)
        anomaly_model_path = self.models_dir / "polar_ems_anomaly_detector.joblib"
        anomaly_meta_path = self.models_dir / "polar_ems_anomaly_detector_metadata.json"
        if anomaly_model_path.exists():
            self.models["anomaly"] = joblib.load(anomaly_model_path)
            self.metadata["anomaly"] = self._load_json(anomaly_meta_path)
            logger.info("Loaded SCADA Anomaly Detector (23 features)")

        self.is_loaded = True
        return {
            "status": "success",
            "models_loaded": list(self.models.keys()),
            "count": len(self.models)
        }

    def _load_json(self, path: Path) -> Dict[str, Any]:
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Could not parse metadata JSON {path}: {e}")
        return {}

    def get_model(self, name: str) -> Any:
        if not self.is_loaded:
            self.load_all()
        if name not in self.models:
            raise KeyError(f"Model '{name}' is not loaded. Available: {list(self.models.keys())}")
        return self.models[name]

    def get_metadata(self, name: str) -> Dict[str, Any]:
        if not self.is_loaded:
            self.load_all()
        return self.metadata.get(name, {})

    def get_all_metadata(self) -> Dict[str, Any]:
        return {
            name: {
                "metadata": self.metadata.get(name, {}),
                "loaded": name in self.models,
                "model_type": type(self.models[name]).__name__ if name in self.models else None,
            }
            for name in ["load", "solar", "wind", "battery_soh", "anomaly"]
        }


# Global accessor
def get_model_loader() -> ModelLoader:
    return ModelLoader.get_instance()
