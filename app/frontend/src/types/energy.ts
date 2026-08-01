export type ChartTypeOption = 'line' | 'smooth' | 'area' | 'bar';

export type ModelType = 'epnet' | 'lightgbm' | 'hybrid';

export interface EnergyDataPoint {
  timestamp: string; // '2026-07-31 00:00'
  hour: string; // '00:00'
  date: string; // '2026-07-31'
  ptf: number; // Gerçekleşen EPİAŞ PTF (₺/MWh)
  epnetForecast: number; // EPNet (CNN+LSTM) PTF Tahmini (₺/MWh)
  lightgbmForecast: number; // LightGBM PTF Tahmini (₺/MWh)
  hybridForecast: number; // Hibrit Model (EPNet + LightGBM Ensemble) PTF Tahmini (₺/MWh)
  upperBound: number; // %95 Güven Aralığı Üst Sınır (₺/MWh)
  lowerBound: number; // %95 Güven Aralığı Alt Sınır (₺/MWh)
  smf?: number; // Referans SMF (₺/MWh)
}

export interface SeriesConfig {
  id: keyof Omit<EnergyDataPoint, 'timestamp' | 'hour' | 'date'>;
  name: string;
  color: string;
  visible: boolean;
  chartType: ChartTypeOption;
  unit: string;
  isForecast?: boolean;
  modelType?: ModelType;
}

export interface IntersectionPoint {
  id: string;
  xIndex: number;
  timestamp: string;
  hourLabel: string;
  dateLabel: string;
  exactValue: number;
  series1Id: string;
  series1Name: string;
  series1Color: string;
  series2Id: string;
  series2Name: string;
  series2Color: string;
  differenceBefore: number;
  differenceAfter: number;
}

export interface DashboardMetrics {
  avgPtf: number;
  avgEpnetForecast: number;
  avgLightgbmForecast: number;
  avgHybridForecast: number;
  mapeEpnet: number;
  mapeLightgbm: number;
  mapeHybrid: number;
  wapeEpnet: number;
  wapeLightgbm: number;
  wapeHybrid: number;
  bestModel: string;
  totalIntersections: number;
  peakHour: string;
  maxPrice: number;
  minPrice: number;
}

export type TimeRangePreset = '24h' | '48h' | '7d' | '30d' | 'custom';

export interface DateRangeState {
  preset: TimeRangePreset;
  startDate: string; // 'YYYY-MM-DD'
  endDate: string; // 'YYYY-MM-DD'
}

export type CurrencyMode = 'TRY' | 'USD';

