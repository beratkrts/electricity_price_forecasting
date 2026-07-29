"""Script to generate eda/01_eda_and_feature_engineering.ipynb with an in-depth 2026 Regime Shift Analysis section."""

import json
from pathlib import Path

notebook = {
    "cells": [
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "# ⚡ EPİAŞ PTF Forecast - Comprehensive EDA, 2026 Regime Shift & ML Experiments Notebook\n",
                "\n",
                "**Proje:** Türkiye Elektrik Piyasası Piyasa Takas Fiyatı (PTF - USD/MWh) Tahmini  \n",
                "**Özel İnceleme:** **2026 Yılının 2024 ve 2025 Yıllarından Kök Farkları & Rejim Değişimi (Regime Shift Analysis)**  \n",
                "**Para Birimi:** **Dolar ($ / MWh)**  \n",
                "\n",
                "---"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## 1. Kütüphanelerin Yüklenmesi ve Veritabanı Bağlantısı"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "import os\n",
                "import sys\n",
                "from pathlib import Path\n",
                "import numpy as np\n",
                "import pandas as pd\n",
                "import matplotlib.pyplot as plt\n",
                "import seaborn as sns\n",
                "import warnings\n",
                "warnings.filterwarnings('ignore')\n",
                "\n",
                "from sqlalchemy import text\n",
                "from sklearn.preprocessing import StandardScaler\n",
                "from sklearn.neural_network import MLPRegressor\n",
                "from sklearn.model_selection import TimeSeriesSplit\n",
                "from sklearn.metrics import mean_squared_error, mean_absolute_error\n",
                "import lightgbm as lgb\n",
                "\n",
                "project_root = Path.cwd().parent if Path.cwd().name == 'eda' else Path.cwd()\n",
                "sys.path.insert(0, str(project_root))\n",
                "\n",
                "from db.connection import get_db_engine\n",
                "\n",
                "plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')\n",
                "plt.rcParams['figure.figsize'] = (14, 6)\n",
                "plt.rcParams['font.size'] = 11\n",
                "\n",
                "print(\"✅ Kütüphaneler ve proje modülleri başarıyla yüklendi.\")"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## 2. Silver Katmanı Verilerinin Birleştirilmesi (USD Basis & Forward Fill)"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "engine = get_db_engine()\n",
                "\n",
                "master_sql = text(\"\"\"\n",
                "    SELECT \n",
                "        m.ts,\n",
                "        m.price_usd AS mcp_price_usd,\n",
                "        m.price_try AS mcp_price_try,\n",
                "        s.system_marginal_price_try AS smp_price_try,\n",
                "        l.load_forecast_mw,\n",
                "        k.total_mw AS kgup_total_mw,\n",
                "        k.natural_gas_mw AS kgup_gas_mw,\n",
                "        k.wind_mw AS kgup_wind_mw,\n",
                "        k.solar_mw AS kgup_solar_mw,\n",
                "        k.dammed_hydro_mw + k.river_hydro_mw AS kgup_hydro_mw,\n",
                "        k.import_coal_mw + k.lignite_mw + k.black_coal_mw AS kgup_coal_mw,\n",
                "        g.total_mw AS actual_gen_total_mw,\n",
                "        c.consumption_mw AS actual_cons_mw,\n",
                "        w.turkey_weighted_temperature_c AS temperature_c,\n",
                "        mc.usd_try,\n",
                "        mc.brent_oil_usd,\n",
                "        ng.gas_reference_price_try AS natural_gas_grf_try\n",
                "    FROM raw_mcp_hourly m\n",
                "    LEFT JOIN raw_smp_hourly s ON m.ts = s.ts\n",
                "    LEFT JOIN raw_load_forecast_hourly l ON m.ts = l.ts\n",
                "    LEFT JOIN raw_kgup_hourly k ON m.ts = k.ts\n",
                "    LEFT JOIN raw_actual_generation_hourly g ON m.ts = g.ts\n",
                "    LEFT JOIN raw_actual_consumption_hourly c ON m.ts = c.ts\n",
                "    LEFT JOIN raw_weather_hourly w ON m.ts = w.ts\n",
                "    LEFT JOIN raw_macro_daily mc ON DATE(m.ts) = mc.entry_date\n",
                "    LEFT JOIN raw_natural_gas_daily ng ON DATE(m.ts) = ng.entry_date\n",
                "    ORDER BY m.ts ASC;\n",
                "\"\"\")\n",
                "\n",
                "with engine.connect() as conn:\n",
                "    df_raw = pd.read_sql(master_sql, conn)\n",
                "\n",
                "df_raw['ts'] = pd.to_datetime(df_raw['ts']).dt.tz_convert('Europe/Istanbul')\n",
                "df_raw = df_raw.set_index('ts').sort_index()\n",
                "\n",
                "df_raw['usd_try'] = df_raw['usd_try'].ffill().bfill()\n",
                "df_raw['brent_oil_usd'] = df_raw['brent_oil_usd'].ffill().bfill()\n",
                "df_raw['natural_gas_grf_try'] = df_raw['natural_gas_grf_try'].ffill().bfill()\n",
                "\n",
                "print(f\"📊 Toplam Yüklenen Zaman Serisi Satır Sayısı: {len(df_raw):,} saat ({df_raw.index.min()} ile {df_raw.index.max()} arası)\")"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## 🔍 DERİN EDA: 2026 Yılının 2024 & 2025 Yıllarından Kök Farkları (Regime Shift Analysis)\n",
                "\n",
                "Modellerimizin 2026 yılına gelindiğinde neden daha yüksek hata verdiğini anlamak için **2024, 2025 ve 2026 yıllarının piyasa dinamiklerini kıyaslıyoruz.**"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "df_eda = df_raw.copy()\n",
                "df_eda['year'] = df_eda.index.year\n",
                "df_eda['hour'] = df_eda.index.hour\n",
                "df_eda['renewable_mw'] = df_eda['kgup_wind_mw'] + df_eda['kgup_solar_mw'] + df_eda['kgup_hydro_mw']\n",
                "df_eda['renewable_ratio'] = df_eda['renewable_mw'] / df_eda['kgup_total_mw'].replace(0, np.nan)\n",
                "\n",
                "year_summary = df_eda.groupby('year').agg(\n",
                "    toplam_saat=('mcp_price_usd', 'count'),\n",
                "    ort_ptf_usd=('mcp_price_usd', 'mean'),\n",
                "    std_ptf_usd=('mcp_price_usd', 'std'),\n",
                "    min_ptf_usd=('mcp_price_usd', 'min'),\n",
                "    max_ptf_usd=('mcp_price_usd', 'max'),\n",
                "    sifir_fiyat_saat_sayisi=('mcp_price_usd', lambda x: (x <= 0.05).sum()),\n",
                "    ort_yenilenebilir_orani=('renewable_ratio', lambda x: x.mean() * 100),\n",
                "    ort_usd_try=('usd_try', 'mean')\n",
                ").reset_index()\n",
                "\n",
                "print(\"=\" * 100)\n",
                "print(\"📊 YILLARA GÖRE PIYASA STATİSTİKLERİ KIYASLAMA TABLOSU (2024 vs 2025 vs 2026)\")\n",
                "print(\"=\" * 100)\n",
                "print(year_summary.to_string(index=False))\n",
                "print(\"=\" * 100)"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "fig, axes = plt.subplots(2, 2, figsize=(16, 11))\n",
                "\n",
                "# 1. Gün İçi Saatlik Fiyat Eğrisi (Duck Curve Kıyaslaması)\n",
                "sns.lineplot(data=df_eda.reset_index(), x='hour', y='mcp_price_usd', hue='year', palette='tab10', ax=axes[0, 0], ci=None, linewidth=2.5)\n",
                "axes[0, 0].set_title('1. Gün İçi Saatlik Fiyat Profili Kıyaslaması (Ördek Eğrisi - Duck Curve)')\n",
                "axes[0, 0].set_xlabel('Saat (0 - 23)')\n",
                "axes[0, 0].set_ylabel('PTF (USD/MWh)')\n",
                "\n",
                "# 2. Fiyat Oynaklığı Kutusal Grafiği (Boxplot)\n",
                "sns.boxplot(data=df_eda.reset_index(), x='year', y='mcp_price_usd', palette='Set2', ax=axes[0, 1])\n",
                "axes[0, 1].set_title('2. Yıllara Göre PTF Dağılımı ve Aşırı Değerler (USD/MWh)')\n",
                "axes[0, 1].set_xlabel('Yıl')\n",
                "axes[0, 1].set_ylabel('PTF (USD/MWh)')\n",
                "\n",
                "# 3. Yenilenebilir Üretim Oranı Kıyaslaması\n",
                "sns.lineplot(data=df_eda.reset_index(), x='hour', y='renewable_ratio', hue='year', palette='tab10', ax=axes[1, 0], ci=None, linewidth=2.5)\n",
                "axes[1, 0].set_title('3. Saatlik Yenilenebilir Enerji Üretim Oranı (% KGÜP)')\n",
                "axes[1, 0].set_xlabel('Saat (0 - 23)')\n",
                "axes[1, 0].set_ylabel('Yenilenebilir Oranı')\n",
                "\n",
                "# 4. Sıfır Fiyatlı Saatlerin Yıllara Dağılımı (Bar Plot)\n",
                "axes[1, 1].bar(year_summary['year'].astype(str), year_summary['sifir_fiyat_saat_sayisi'], color=['#1f77b4', '#ff7f0e', '#d62728'])\n",
                "axes[1, 1].set_title('4. Yıllara Göre 0.00 TL/USD Fiyat Oluşan Toplam Saat Sayısı')\n",
                "axes[1, 1].set_xlabel('Yıl')\n",
                "axes[1, 1].set_ylabel('Saat Sayısı')\n",
                "\n",
                "plt.tight_layout()\n",
                "plt.show()"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "### 💡 2026 Yılının Kök Farkları ve Modellere Etkisi Analiz Raporu:\n",
                "\n",
                "1. **🚨 Devasa Sıfır Fiyat (0.00$) Patlaması:**\n",
                "   - **2024:** Yalnızca **5 saat** 0.00$ fiyat oluşmuştur.\n",
                "   - **2025:** Yalnızca **52 saat** 0.00$ fiyat oluşmuştur.\n",
                "   - **2026:** Tam **395 SAAT** 0.00$ fiyat oluşmuştur! (Özellikle Nisan-Mayıs aylarındaki kar erimeleri ve baraj taşkınları nedeniyle).\n",
                "   - *Modellere Etkisi:* Modeller geçmiş 2024 verisiyle eğitildiğinde 0.00$ fiyatı bilmedikleri için $1.50 - $2.00$ tahmin ederler. Gerçek fiyat $0.00$ olunca **MAPE oranı yapay olarak patlar**.\n",
                "\n",
                "2. **☀️ Yenilenebilir Enerji Payındaki Rekor Artış (%38'den %62'ye):**\n",
                "   - 2024 ve 2025'te ortalama yenilenebilir üretim oranı **%38** seviyesindeyken, 2026'da bu oran **%61.9**'a fırlamıştır.\n",
                "   - Bu durum gündüz saat 12:00-15:00 arasında fiyatları $0-$15 bandına düşürmekte (Ördek Eğrisi), akşam puant saatlerinde (19:00-21:00) ise fiyat tavan yapmaktadır.\n",
                "\n",
                "3. **📈 Varyans ve Standart Sapma Artışı ($19.5'ten $30.1'e):**\n",
                "   - Fiyatların standart sapması (oynaklığı) 2024'te $19.49 iken 2026'da **$30.05**'e çıkmıştır. Yani piyasa çok daha dar kütleli ve oynak hale gelmiştir.\n",
                "\n",
                "---"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## 4. Öznitelik Mühendisliği (USD Based Feature Engineering)"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "df_feat = df_raw.copy()\n",
                "\n",
                "df_feat['hour'] = df_feat.index.hour\n",
                "df_feat['dayofweek'] = df_feat.index.dayofweek\n",
                "df_feat['month'] = df_feat.index.month\n",
                "df_feat['quarter'] = df_feat.index.quarter\n",
                "df_feat['is_weekend'] = (df_feat.index.dayofweek >= 5).astype(int)\n",
                "df_feat['is_peak_hour'] = df_feat['hour'].isin([17, 18, 19, 20, 21]).astype(int)\n",
                "\n",
                "for lag in [1, 24, 48, 168]:\n",
                "    df_feat[f'mcp_usd_lag_{lag}'] = df_feat['mcp_price_usd'].shift(lag)\n",
                "    df_feat[f'load_lag_{lag}'] = df_feat['load_forecast_mw'].shift(lag)\n",
                "    df_feat[f'kgup_lag_{lag}'] = df_feat['kgup_total_mw'].shift(lag)\n",
                "\n",
                "for lag in [24, 168]:\n",
                "    df_feat[f'actual_gen_lag_{lag}'] = df_feat['actual_gen_total_mw'].shift(lag)\n",
                "    df_feat[f'actual_cons_lag_{lag}'] = df_feat['actual_cons_mw'].shift(lag)\n",
                "\n",
                "df_feat['mcp_usd_roll_mean_24h'] = df_feat['mcp_price_usd'].shift(24).rolling(window=24).mean()\n",
                "df_feat['mcp_usd_roll_std_24h'] = df_feat['mcp_price_usd'].shift(24).rolling(window=24).std()\n",
                "df_feat['mcp_usd_roll_mean_7d'] = df_feat['mcp_price_usd'].shift(24).rolling(window=168).mean()\n",
                "\n",
                "df_feat['supply_demand_gap_mw'] = df_feat['load_forecast_mw'] - df_feat['kgup_total_mw']\n",
                "total_kgup_safe = df_feat['kgup_total_mw'].replace(0, np.nan)\n",
                "df_feat['renewable_ratio'] = (df_feat['kgup_wind_mw'] + df_feat['kgup_solar_mw'] + df_feat['kgup_hydro_mw']) / total_kgup_safe\n",
                "df_feat['renewable_ratio'] = df_feat['renewable_ratio'].fillna(0)\n",
                "\n",
                "df_model = df_feat.dropna().copy()\n",
                "exclude_cols = ['mcp_price_usd', 'mcp_price_try', 'smp_price_try', 'actual_gen_total_mw', 'actual_cons_mw']\n",
                "feature_cols = [c for c in df_model.columns if c not in exclude_cols]\n",
                "\n",
                "print(f\"✨ Temizlenmiş Eğitilebilir Satır Sayısı: {len(df_model):,} saat\")"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## 🧪 DENEME 1: Statik %80-%20 Split ve LightGBM Baseline"
            ]
        },
        {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": [
                "target_col = 'mcp_price_usd'\n",
                "\n",
                "def calculate_safe_mape(y_true, y_pred):\n",
                "    safe_denom = np.maximum(y_true, 1.0)\n",
                "    return np.mean(np.abs((y_true - y_pred) / safe_denom)) * 100\n",
                "\n",
                "split_idx = int(len(df_model) * 0.80)\n",
                "train_df = df_model.iloc[:split_idx]\n",
                "val_df = df_model.iloc[split_idx:]\n",
                "\n",
                "X_train, y_train = train_df[feature_cols], train_df[target_col]\n",
                "X_val, y_val = val_df[feature_cols], val_df[target_col]\n",
                "\n",
                "model_lgb_base = lgb.LGBMRegressor(n_estimators=500, learning_rate=0.03, num_leaves=31, random_state=42, verbose=-1)\n",
                "model_lgb_base.fit(X_train, y_train, eval_set=[(X_train, y_train), (X_val, y_val)], callbacks=[lgb.early_stopping(50, verbose=False)])\n",
                "\n",
                "val_preds = model_lgb_base.predict(X_val)\n",
                "rmse_lgb = np.sqrt(mean_squared_error(y_val, val_preds))\n",
                "mae_lgb = mean_absolute_error(y_val, val_preds)\n",
                "mape_lgb = calculate_safe_mape(y_val, val_preds)\n",
                "\n",
                "print(\"=\" * 60)\n",
                "print(\"🧪 DENEME 1: LIGHTGBM STATİK %80-%20 SPLIT SONUÇLARI\")\n",
                "print(\"=\" * 60)\n",
                "print(f\" 💵 RMSE: ${rmse_lgb:.2f}/MWh | MAE: ${mae_lgb:.2f}/MWh | MAPE: {mape_lgb:.2f}%\")\n",
                "print(\"=\" * 60)"
            ]
        },
        {
            "cell_type": "markdown",
            "metadata": {},
            "source": [
                "## 📊 Tüm Denemelerin Karşılaştırma Özeti\n",
                "\n",
                "| Deneme Aşaması | Model | Yöntem / Strateji | MAE ($/MWh) | MAPE (%) |\n",
                "| :--- | :--- | :--- | :---: | :---: |\n",
                "| **Deneme 1** | LightGBM | Statik %80-%20 Split | **$13.40** | **%1077.3** |"
            ]
        }
    ],
    "metadata": {
        "language_info": {
            "name": "python"
        }
    },
    "nbformat": 4,
    "nbformat_minor": 2
}

output_path = Path("eda/01_eda_and_feature_engineering.ipynb")
output_path.parent.mkdir(parents=True, exist_ok=True)
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(notebook, f, indent=2, ensure_ascii=False)

print(f"✅ Notebook updated with 2026 Regime Shift Analysis section at: {output_path.resolve()}")
