import { DateRangeState, EnergyDataPoint } from '../types/energy';

/**
 * Fetches NEXT DAY forecast (1 Ağustos 2026) for Page 1 (Home).
 */
export async function fetchNextDayForecast(): Promise<EnergyDataPoint[]> {
  try {
    const nextRes = await fetch(`/api/db-data?date=latest&type=next_day_forecast`);
    const forecastData = nextRes.ok ? await nextRes.json() : [];

    const targetDate = Array.isArray(forecastData) && forecastData.length > 0 && forecastData[0].target_date 
      ? forecastData[0].target_date 
      : '2026-08-01';

    return Array.from({ length: 24 }, (_, i) => {
      const hourStr = i.toString().padStart(2, '0') + ':00';
      const fItem = Array.isArray(forecastData) ? forecastData.find((x: any) => x.hour === hourStr) : null;

      const rawFcVal = fItem ? parseFloat(fItem.lightgbm_forecast || fItem.price) : 0;
      const usdFcVal = fItem && fItem.lightgbm_forecast_usd !== undefined ? parseFloat(fItem.lightgbm_forecast_usd) : undefined;
      const fcP10 = fItem && fItem.price_p10 !== undefined && fItem.price_p10 !== null ? parseFloat(fItem.price_p10) : Math.round(rawFcVal * 0.95);
      const fcP90 = fItem && fItem.price_p90 !== undefined && fItem.price_p90 !== null ? parseFloat(fItem.price_p90) : Math.round(rawFcVal * 1.05);
      const fcP10Usd = fItem && fItem.price_usd_p10 !== undefined && fItem.price_usd_p10 !== null ? parseFloat(fItem.price_usd_p10) : (usdFcVal !== undefined ? Number((usdFcVal * 0.95).toFixed(2)) : undefined);
      const fcP90Usd = fItem && fItem.price_usd_p90 !== undefined && fItem.price_usd_p90 !== null ? parseFloat(fItem.price_usd_p90) : (usdFcVal !== undefined ? Number((usdFcVal * 1.05).toFixed(2)) : undefined);

      return {
        timestamp: `${targetDate} ${hourStr}`,
        hour: hourStr,
        date: targetDate,
        ptf: 0,
        lightgbmForecast: rawFcVal,
        lightgbmForecastUsd: usdFcVal,
        upperBound: fcP90,
        lowerBound: fcP10,
        upperBoundUsd: fcP90Usd,
        lowerBoundUsd: fcP10Usd,
        smf: 0
      };
    });
  } catch (err) {
    console.error('Error fetching next day forecast:', err);
    return [];
  }
}

/**
 * Fetches LATEST REALIZED PTF DAY comparison (31 Temmuz 2026) for Page 2 (Forecast).
 */
export async function fetchLatestRealizedComparison(dateStr: string = 'latest', groupBy?: string): Promise<{ series: EnergyDataPoint[]; metrics: any }> {
  try {
    const url = groupBy ? `/api/db-data?date=${dateStr}&type=today_performance&group_by=${groupBy}` : `/api/db-data?date=${dateStr}&type=today_performance`;
    const res = await fetch(url);
    const payload = res.ok ? await res.json() : {};
    
    const data = Array.isArray(payload) ? payload : (payload.series || []);
    const metrics = payload.metrics || {};

    if (!Array.isArray(data) || data.length === 0) {
      return { series: [], metrics: {} };
    }

    const seriesData = data.map((item: any) => {
      const ptfVal = item && item.ptf !== undefined && item.ptf !== null ? parseFloat(item.ptf) : 0;
      const lgbVal = item && item.lightgbm_forecast !== undefined && item.lightgbm_forecast !== null ? parseFloat(item.lightgbm_forecast) : ptfVal;
      const dateVal = item.date || dateStr;
      const hourVal = item.hour || '00:00';
      const tsVal = item.timestamp || `${dateVal} ${hourVal}`;

      const ptfUsdVal = item && item.ptf_usd !== undefined && item.ptf_usd !== null ? parseFloat(item.ptf_usd) : 0;
      const lgbUsdVal = item && item.lightgbm_forecast_usd !== undefined && item.lightgbm_forecast_usd !== null ? parseFloat(item.lightgbm_forecast_usd) : ptfUsdVal;
      
      const p10Val = item && item.lightgbm_forecast_p10 !== undefined && item.lightgbm_forecast_p10 !== null ? parseFloat(item.lightgbm_forecast_p10) : Math.round(lgbVal * 0.95);
      const p90Val = item && item.lightgbm_forecast_p90 !== undefined && item.lightgbm_forecast_p90 !== null ? parseFloat(item.lightgbm_forecast_p90) : Math.round(lgbVal * 1.05);
      
      const p10UsdVal = item && item.lightgbm_forecast_usd_p10 !== undefined && item.lightgbm_forecast_usd_p10 !== null ? parseFloat(item.lightgbm_forecast_usd_p10) : Number((lgbUsdVal * 0.95).toFixed(2));
      const p90UsdVal = item && item.lightgbm_forecast_usd_p90 !== undefined && item.lightgbm_forecast_usd_p90 !== null ? parseFloat(item.lightgbm_forecast_usd_p90) : Number((lgbUsdVal * 1.05).toFixed(2));

      return {
        timestamp: tsVal,
        hour: hourVal,
        date: dateVal,
        ptf: isNaN(ptfVal) ? 0 : ptfVal,
        ptfUsd: isNaN(ptfUsdVal) ? 0 : ptfUsdVal,
        lightgbmForecast: isNaN(lgbVal) ? ptfVal : lgbVal,
        lightgbmForecastUsd: isNaN(lgbUsdVal) ? ptfUsdVal : lgbUsdVal,
        upperBound: p90Val,
        lowerBound: p10Val,
        upperBoundUsd: p90UsdVal,
        lowerBoundUsd: p10UsdVal,
        smf: ptfVal
      };
    });

    return { series: seriesData, metrics };
  } catch (err) {
    console.error('Error fetching realized comparison:', err);
    return { series: [], metrics: {} };
  }
}

// Backward compatibility wrapper
export async function fetchRealEnergyData(_dateStr: string = '2026-07-31'): Promise<EnergyDataPoint[]> {
  return fetchNextDayForecast();
}

export function generateEnergyData(
  _dateRange: DateRangeState,
  _hybridWeights: { epnet: number; lgb: number } = { epnet: 55, lgb: 45 }
): EnergyDataPoint[] {
  return [];
}
