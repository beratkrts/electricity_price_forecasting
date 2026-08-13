import { DashboardMetrics } from '../types/energy';

export function formatDashboardMetrics(
  backendMetrics: any,
  currencyMode: 'TRY' | 'USD' = 'USD',
  usdRate: number = 33.15
): DashboardMetrics {
  
  if (!backendMetrics || Object.keys(backendMetrics).length === 0) {
    return {
      avgPtf: 0,
      avgLightgbmForecast: 0,
      mapeLightgbm: 0,
      wapeLightgbm: 0,
      wapeOob: 0,
      bestModel: 'LightGBM',
      totalIntersections: 0,
      peakHour: '00:00',
      maxPrice: 0,
      minPrice: 0
    };
  }

  const isUsd = currencyMode === 'USD';

  // Yüzdelik Hatalar (WAPE / MAPE)
  // Kur oynamalarından (FX distortion) etkilenmemesi için her zaman USD bazlı metrikleri baz alırız.
  const mapeLightgbm = backendMetrics.mape_usd !== undefined ? Number(backendMetrics.mape_usd) : Number(backendMetrics.mape || 0);
  const wapeLightgbm = backendMetrics.wape_usd !== undefined ? Number(backendMetrics.wape_usd) : Number(backendMetrics.wape || 0);
  const wapeOob = backendMetrics.wape_oob_usd !== undefined ? Number(backendMetrics.wape_oob_usd) : Number(backendMetrics.wape_oob || 0);

  // Fiyat Ortalamaları
  // Eğer kullanıcı TRY seçtiyse ve veritabanı "avg_actual" gönderdiyse onu kullanırız.
  // Eğer USD seçtiyse ve veritabanı "avg_actual_usd" gönderdiyse onu kullanırız, yoksa güncel kur ile böleriz.
  const avgPtf = isUsd && backendMetrics.avg_actual_usd !== undefined 
    ? Number(backendMetrics.avg_actual_usd) 
    : isUsd ? Number(backendMetrics.avg_actual || 0) / (usdRate || 1) : Number(backendMetrics.avg_actual || 0);

  const avgLightgbmForecast = isUsd && backendMetrics.avg_predicted_usd !== undefined 
    ? Number(backendMetrics.avg_predicted_usd) 
    : isUsd ? Number(backendMetrics.avg_predicted || 0) / (usdRate || 1) : Number(backendMetrics.avg_predicted || 0);


  return {
    avgPtf,
    avgLightgbmForecast,
    mapeLightgbm,
    wapeLightgbm,
    wapeOob,
    bestModel: 'LightGBM',
    totalIntersections: backendMetrics.total_hours || 0,
    peakHour: '00:00',
    maxPrice: 0,
    minPrice: 0
  };
}
