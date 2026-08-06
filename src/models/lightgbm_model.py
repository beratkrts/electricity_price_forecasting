import numpy as np
import pandas as pd
import lightgbm as lgb
import joblib
from pathlib import Path
from typing import Union, List, Dict, Optional


class LightGBMForecaster:
    """
    LightGBM tabanlı enerji fiyat tahmin modeli.
    Log-transform (log1p / expm1) ile eğitilir ve tahmin verir.
    """
    def __init__(self, params: Optional[Dict] = None):
        self.params = params or {
            'n_estimators': 300,
            'learning_rate': 0.03,
            'max_depth': 8,
            'num_leaves': 63,
            'subsample': 0.8,
            'colsample_bytree': 0.8,
            'reg_alpha': 0.1,
            'reg_lambda': 0.1,
            'min_child_samples': 20,
            'verbose': -1,
            'random_state': 42,
            'deterministic': True,
            'force_col_wise': True,
        }
        self.model = None
        self.feature_columns = None

    def fit(self, X: pd.DataFrame, y: Union[pd.Series, np.ndarray], feature_columns: Optional[List[str]] = None):
        """
        Modeli eğitir. Hedef değişkene (y) log-transform uygular.
        """
        if feature_columns:
            self.feature_columns = feature_columns
            X_train = X[feature_columns]
        else:
            self.feature_columns = list(X.columns)
            X_train = X

        y_arr = np.array(y)
        y_log = np.log1p(np.maximum(y_arr, 0.0))

        self.model = lgb.LGBMRegressor(**self.params)
        self.model.fit(X_train, y_log)
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """
        Tahmin üretir ve log dönüşümünü tersine çevirir (expm1).
        """
        if self.model is None:
            raise ValueError("Model henüz eğitilmedi.")

        if self.feature_columns:
            X_test = X[self.feature_columns]
        else:
            X_test = X

        preds_log = self.model.predict(X_test)
        preds = np.expm1(preds_log)
        return np.maximum(preds, 0.0)

    def save(self, file_path: Union[str, Path]):
        """Modeli diske kaydeder."""
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({'model': self.model, 'feature_columns': self.feature_columns, 'params': self.params}, file_path)

    def load(self, file_path: Union[str, Path]):
        """Diskteki modeli yükler."""
        data = joblib.load(file_path)
        self.model = data['model']
        self.feature_columns = data['feature_columns']
        self.params = data['params']
        return self
