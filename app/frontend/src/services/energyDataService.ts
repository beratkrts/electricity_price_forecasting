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

      return {
        timestamp: `${targetDate} ${hourStr}`,
        hour: hourStr,
        date: targetDate,
        ptf: 0,
        epnetForecast: rawFcVal,
        lightgbmForecast: rawFcVal,
        hybridForecast: rawFcVal,
        upperBound: Math.round(rawFcVal * 1.05),
        lowerBound: Math.round(rawFcVal * 0.95),
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
export async function fetchLatestRealizedComparison(dateStr: string = 'latest'): Promise<EnergyDataPoint[]> {
  try {
    const res = await fetch(`/api/db-data?date=${dateStr}&type=today_performance`);
    const data = res.ok ? await res.json() : [];

    if (!Array.isArray(data) || data.length === 0) {
      return [];
    }

    return data.map((item: any) => {
      const ptfVal = item && item.ptf !== undefined && item.ptf !== null ? parseFloat(item.ptf) : 0;
      const lgbVal = item && item.lightgbm_forecast !== undefined && item.lightgbm_forecast !== null ? parseFloat(item.lightgbm_forecast) : ptfVal;
      const dateVal = item.date || dateStr;
      const hourVal = item.hour || '00:00';
      const tsVal = item.timestamp || `${dateVal} ${hourVal}`;

      return {
        timestamp: tsVal,
        hour: hourVal,
        date: dateVal,
        ptf: isNaN(ptfVal) ? 0 : ptfVal,
        epnetForecast: lgbVal,
        lightgbmForecast: isNaN(lgbVal) ? ptfVal : lgbVal,
        hybridForecast: lgbVal,
        upperBound: Math.round(lgbVal * 1.05),
        lowerBound: Math.round(lgbVal * 0.95),
        smf: ptfVal
      };
    });
  } catch (err) {
    console.error('Error fetching realized comparison:', err);
    return [];
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
