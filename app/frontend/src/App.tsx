import React, { useState, useEffect, useMemo } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';

import { Header } from './components/layout/Header';
import { CurrencyTicker } from './components/layout/CurrencyTicker';
import { ExportModal } from './components/dashboard/ExportModal';

import { Home } from './pages/Home';
import { Forecast } from './pages/Forecast';
import { Analysis } from './pages/Analysis';

import { DateRangeState, EnergyDataPoint, SeriesConfig, ChartTypeOption, CurrencyMode } from './types/energy';
import { CurrencyRate } from './types/currency';

import { INITIAL_CURRENCY_RATES, fetchMarketData } from './services/fxService';
import { findSeriesIntersections } from './utils/intersectionDetector';
import { fetchNextDayForecast, fetchLatestRealizedComparison } from './services/energyDataService';
import { calculateDashboardMetrics } from './utils/mathHelpers';

export const App: React.FC = () => {
  // Global Data State
  const [dateRange, setDateRange] = useState<DateRangeState>({
    preset: '24h',
    startDate: '2026-07-31',
    endDate: '2026-08-01'
  });

  const [showIntersections, setShowIntersections] = useState<boolean>(true);
  const [isExportOpen, setIsExportOpen] = useState<boolean>(false);
  const [nextDayData, setNextDayData] = useState<EnergyDataPoint[]>([]);
  const [comparisonData, setComparisonData] = useState<EnergyDataPoint[]>([]);

  const [seriesConfigs, setSeriesConfigs] = useState<SeriesConfig[]>([
    { id: 'lightgbmForecast', name: 'LightGBM PTF Tahmini', color: '#c084fc', visible: true, chartType: 'smooth', unit: '₺/MWh', isForecast: true, modelType: 'lightgbm' },
    { id: 'ptf', name: 'EPİAŞ PTF (Gerçekleşen)', color: '#38bdf8', visible: true, chartType: 'smooth', unit: '₺/MWh' }
  ]);

  const [currencyMode, setCurrencyMode] = useState<CurrencyMode>('USD');
  const [currencyRates, setCurrencyRates] = useState<CurrencyRate[]>(INITIAL_CURRENCY_RATES);

  // Convert values based on selected currencyMode (TRY / USD)
  const usdRate = useMemo(() => {
    const usdObj = currencyRates.find(r => r.symbol === 'USD/TRY');
    return usdObj && usdObj.price > 0 ? usdObj.price : 33.15;
  }, [currencyRates]);

  const convertDataCurrency = (dataPoints: EnergyDataPoint[]): EnergyDataPoint[] => {
    if (currencyMode === 'TRY') return dataPoints;
    return dataPoints.map(d => ({
      ...d,
      ptf: Number((d.ptf / usdRate).toFixed(2)),
      epnetForecast: Number((d.epnetForecast / usdRate).toFixed(2)),
      lightgbmForecast: Number((d.lightgbmForecast / usdRate).toFixed(2)),
      hybridForecast: Number((d.hybridForecast / usdRate).toFixed(2)),
      upperBound: Number((d.upperBound / usdRate).toFixed(2)),
      lowerBound: Number((d.lowerBound / usdRate).toFixed(2)),
      smf: d.smf ? Number((d.smf / usdRate).toFixed(2)) : undefined
    }));
  };

  const displayNextDayData = useMemo(() => convertDataCurrency(nextDayData), [nextDayData, currencyMode, usdRate]);
  const displayComparisonData = useMemo(() => convertDataCurrency(comparisonData), [comparisonData, currencyMode, usdRate]);

  const updatedSeriesConfigs = useMemo(() => {
    const unitStr = currencyMode === 'TRY' ? '₺/MWh' : '$/MWh';
    return seriesConfigs.map(s => ({ ...s, unit: unitStr }));
  }, [seriesConfigs, currencyMode]);
  const [lastRefreshTime, setLastRefreshTime] = useState<string>(
    new Date().toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  );

  const loadData = async () => {
    const nextDay = await fetchNextDayForecast();
    const comp = await fetchLatestRealizedComparison(dateRange.startDate || '2026-07-31');
    setNextDayData(nextDay);
    setComparisonData(comp);
  };

  useEffect(() => {
    loadData();
  }, [dateRange]);

  useEffect(() => {
    let mounted = true;
    
    const fetchRealData = async () => {
      const newRates = await fetchMarketData();
      if (mounted) {
        setCurrencyRates(newRates);
        setLastRefreshTime(new Date().toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit', second: '2-digit' }));
      }
    };

    fetchRealData(); // Initial real fetch
    const fetchInterval = setInterval(fetchRealData, 60000); // Fetch real data every 60 seconds
    
    return () => {
      mounted = false;
      clearInterval(fetchInterval);
    };
  }, []);

  const intersections = useMemo(() => {
    if (!showIntersections) return [];
    return findSeriesIntersections(comparisonData, seriesConfigs);
  }, [comparisonData, seriesConfigs, showIntersections]);

  const metrics = useMemo(() => {
    return calculateDashboardMetrics(comparisonData, intersections.length);
  }, [comparisonData, intersections]);

  const toggleSeriesVisibility = (id: string) => {
    setSeriesConfigs((prev) =>
      prev.map((s) => (s.id === id ? { ...s, visible: !s.visible } : s))
    );
  };

  const changeSeriesChartType = (id: string, chartType: ChartTypeOption) => {
    setSeriesConfigs((prev) =>
      prev.map((s) => (s.id === id ? { ...s, chartType } : s))
    );
  };

  return (
    <BrowserRouter>
      <div style={{ minHeight: '100vh', backgroundColor: '#070a12', paddingBottom: '60px', display: 'flex', flexDirection: 'column' }} id="dashboard-export-root">
        
        {/* Global Persistent Header */}
        <Header
          onRefresh={loadData}
          onOpenExport={() => setIsExportOpen(true)}
          intersectionCount={intersections.length}
          currencyMode={currencyMode}
          onCurrencyChange={(mode) => setCurrencyMode(mode)}
        />

        {/* Page Content Area */}
        <main style={{ padding: '20px', flex: 1 }}>
          <Routes>
            <Route 
              path="/" 
              element={
                <Home 
                  data={displayNextDayData}
                  seriesConfigs={updatedSeriesConfigs}
                  toggleSeriesVisibility={toggleSeriesVisibility}
                  changeSeriesChartType={changeSeriesChartType}
                  dateRange={dateRange}
                  setDateRange={setDateRange}
                  currencyMode={currencyMode}
                />
              } 
            />
            
            <Route 
              path="/forecast" 
              element={
                <Forecast 
                  data={displayComparisonData}
                  seriesConfigs={updatedSeriesConfigs}
                  toggleSeriesVisibility={toggleSeriesVisibility}
                  changeSeriesChartType={changeSeriesChartType}
                  intersections={intersections}
                  showIntersections={showIntersections}
                  setShowIntersections={setShowIntersections}
                  metrics={metrics}
                  currencyMode={currencyMode}
                />
              } 
            />
            
            <Route path="/analysis" element={<Analysis />} />
            
            {/* Fallback */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>

        {/* Global Persistent Footer Ticker */}
        <CurrencyTicker rates={currencyRates} lastRefresh={lastRefreshTime} />

        <ExportModal isOpen={isExportOpen} onClose={() => setIsExportOpen(false)} />
      </div>
    </BrowserRouter>
  );
};
export default App;
