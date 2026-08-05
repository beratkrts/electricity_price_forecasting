import React, { useState, useEffect, useMemo, useLayoutEffect } from 'react';
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

import { fetchNextDayForecast, fetchLatestRealizedComparison } from './services/energyDataService';
import { calculateDashboardMetrics } from './utils/mathHelpers';

export const App: React.FC = () => {
  // Global Data State
  const [dateRange, setDateRange] = useState<DateRangeState>({
    preset: '24h',
    startDate: '2026-07-31',
    endDate: '2026-08-01'
  });


  const [isExportOpen, setIsExportOpen] = useState<boolean>(false);
  const [nextDayData, setNextDayData] = useState<EnergyDataPoint[]>([]);
  const [comparisonData, setComparisonData] = useState<EnergyDataPoint[]>([]);

  const [seriesConfigs, setSeriesConfigs] = useState<SeriesConfig[]>([
    { id: 'lightgbmForecast', name: 'Yapay Zeka Fiyat Tahmini', color: '#f43f5e', visible: true, chartType: 'smooth', unit: '₺/MWh', isForecast: true, modelType: 'lightgbm' },
    { id: 'ptf', name: 'EPİAŞ Gerçekleşen PTF', color: '#38bdf8', visible: true, chartType: 'smooth', unit: '₺/MWh' }
  ]);

  const [currencyMode, setCurrencyMode] = useState<CurrencyMode>('USD');
  const [currencyRates, setCurrencyRates] = useState<CurrencyRate[]>(INITIAL_CURRENCY_RATES);

  const [themeMode, setThemeMode] = useState<'dark' | 'light'>(() => {
    return (localStorage.getItem('etkb_theme') as 'dark' | 'light') || 'dark';
  });

  const applyTheme = (mode: 'dark' | 'light') => {
    document.documentElement.setAttribute('data-theme', mode);
    document.body.className = mode === 'light' ? 'light-theme' : '';
    localStorage.setItem('etkb_theme', mode);
  };

  useLayoutEffect(() => {
    applyTheme(themeMode);
  }, [themeMode]);

  const toggleTheme = () => {
    const nextTheme = themeMode === 'dark' ? 'light' : 'dark';
    applyTheme(nextTheme);
    setThemeMode(nextTheme);
  };

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

  const updatedSeriesConfigs = useMemo(() => {
    const unitStr = currencyMode === 'TRY' ? '₺/MWh' : '$/MWh';
    return seriesConfigs.map(s => ({ ...s, unit: unitStr }));
  }, [seriesConfigs, currencyMode]);
  const [lastRefreshTime, setLastRefreshTime] = useState<string>(
    new Date().toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  );

  const loadData = async () => {
    const nextDay = await fetchNextDayForecast();
    const compResult = await fetchLatestRealizedComparison(dateRange.startDate || 'latest');
    setNextDayData(nextDay);
    setComparisonData(compResult.series || []);
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



  const metrics = useMemo(() => {
    return calculateDashboardMetrics(comparisonData, 0);
  }, [comparisonData]);

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
          intersectionCount={0}
          currencyMode={currencyMode}
          onCurrencyChange={(mode) => setCurrencyMode(mode)}
          themeMode={themeMode}
          onToggleTheme={toggleTheme}
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
                  data={comparisonData}
                  seriesConfigs={updatedSeriesConfigs}
                  toggleSeriesVisibility={toggleSeriesVisibility}
                  changeSeriesChartType={changeSeriesChartType}

                  metrics={metrics}
                  currencyMode={currencyMode}
                  usdRate={usdRate}
                />
              } 
            />
            
            <Route path="/analysis" element={<Analysis currencyMode={currencyMode} usdRate={usdRate} />} />
            
            {/* Fallback */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>

        {/* Global Persistent Footer Ticker */}
        <CurrencyTicker rates={currencyRates} lastRefresh={lastRefreshTime} />
      </div>

      <ExportModal isOpen={isExportOpen} onClose={() => setIsExportOpen(false)} themeMode={themeMode} />
    </BrowserRouter>
  );
};
export default App;
