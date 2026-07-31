import { DashboardMetrics, EnergyDataPoint } from '../types/energy';

export function calculateDashboardMetrics(data: EnergyDataPoint[], totalIntersections: number): DashboardMetrics {
  if (!data || data.length === 0) {
    return {
      avgPtf: 0,
      avgEpnetForecast: 0,
      avgLightgbmForecast: 0,
      avgHybridForecast: 0,
      mapeEpnet: 0,
      mapeLightgbm: 0,
      mapeHybrid: 0,
      wapeEpnet: 0,
      wapeLightgbm: 0,
      wapeHybrid: 0,
      bestModel: 'Hibrit Model',
      totalIntersections: 0,
      peakHour: '00:00',
      maxPrice: 0,
      minPrice: 0
    };
  }

  let sumPtf = 0;
  let sumEpnet = 0;
  let sumLgb = 0;
  let sumHybrid = 0;

  let sumAbsErrEpnet = 0;
  let sumAbsErrLgb = 0;
  let sumAbsErrHybrid = 0;

  let sumAbsDiffEpnet = 0;
  let sumAbsDiffLgb = 0;
  let sumAbsDiffHybrid = 0;

  let maxPrice = -Infinity;
  let minPrice = Infinity;
  let peakHour = data[0].hour;

  data.forEach((pt) => {
    sumPtf += pt.ptf;
    sumEpnet += pt.epnetForecast;
    sumLgb += pt.lightgbmForecast;
    sumHybrid += pt.hybridForecast;

    // MAPE vs Actual PTF
    if (pt.ptf > 0) {
      sumAbsErrEpnet += Math.abs((pt.ptf - pt.epnetForecast) / pt.ptf);
      sumAbsErrLgb += Math.abs((pt.ptf - pt.lightgbmForecast) / pt.ptf);
      sumAbsErrHybrid += Math.abs((pt.ptf - pt.hybridForecast) / pt.ptf);
    }
    
    // For WAPE (Sum of Absolute Differences)
    sumAbsDiffEpnet += Math.abs(pt.ptf - pt.epnetForecast);
    sumAbsDiffLgb += Math.abs(pt.ptf - pt.lightgbmForecast);
    sumAbsDiffHybrid += Math.abs(pt.ptf - pt.hybridForecast);

    if (pt.ptf > maxPrice) {
      maxPrice = pt.ptf;
      peakHour = pt.hour;
    }
    if (pt.ptf < minPrice) {
      minPrice = pt.ptf;
    }
  });

  const n = data.length;
  const avgPtf = sumPtf / n;
  const avgEpnetForecast = sumEpnet / n;
  const avgLightgbmForecast = sumLgb / n;
  const avgHybridForecast = sumHybrid / n;

  const mapeEpnet = parseFloat(((sumAbsErrEpnet / n) * 100).toFixed(2));
  const mapeLightgbm = parseFloat(((sumAbsErrLgb / n) * 100).toFixed(2));
  const mapeHybrid = parseFloat(((sumAbsErrHybrid / n) * 100).toFixed(2));

  const wapeEpnet = sumPtf > 0 ? parseFloat(((sumAbsDiffEpnet / sumPtf) * 100).toFixed(2)) : 0;
  const wapeLightgbm = sumPtf > 0 ? parseFloat(((sumAbsDiffLgb / sumPtf) * 100).toFixed(2)) : 0;
  const wapeHybrid = sumPtf > 0 ? parseFloat(((sumAbsDiffHybrid / sumPtf) * 100).toFixed(2)) : 0;

  // Determine best model by lowest MAPE
  let bestModel = 'Hibrit Model (Ensemble)';
  const minMape = Math.min(mapeEpnet, mapeLightgbm, mapeHybrid);
  if (minMape === mapeEpnet) bestModel = 'EPNet (CNN+LSTM)';
  else if (minMape === mapeLightgbm) bestModel = 'LightGBM';

  return {
    avgPtf: parseFloat(avgPtf.toFixed(2)),
    avgEpnetForecast: parseFloat(avgEpnetForecast.toFixed(2)),
    avgLightgbmForecast: parseFloat(avgLightgbmForecast.toFixed(2)),
    avgHybridForecast: parseFloat(avgHybridForecast.toFixed(2)),
    mapeEpnet,
    mapeLightgbm,
    mapeHybrid,
    wapeEpnet,
    wapeLightgbm,
    wapeHybrid,
    bestModel,
    totalIntersections,
    peakHour,
    maxPrice: parseFloat(maxPrice.toFixed(2)),
    minPrice: parseFloat(minPrice.toFixed(2))
  };
}
