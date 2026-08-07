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
import { formatDashboardMetrics } from './utils/mathHelpers';

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
    return dataPoints.map(d => {
      // PTF (Actuals) values are historically fixed. NEVER apply live FX rate to them!
      const ptfTry = d.ptf;
      const ptfUsd = d.ptfUsd !== undefined ? d.ptfUsd : 0;
      
      // Forecasts (LightGBM) are predicted in USD. Apply live FX rate to get current TRY equivalent.
      const lgbUsd = d.lightgbmForecastUsd !== undefined ? d.lightgbmForecastUsd : 0;
      const lgbTry = d.lightgbmForecastUsd !== undefined ? Number((d.lightgbmForecastUsd * usdRate).toFixed(2)) : d.lightgbmForecast;

      if (currencyMode === 'USD') {
        return {
          ...d,
          ptf: ptfUsd,
          epnetForecast: lgbUsd,
          lightgbmForecast: lgbUsd,
          hybridForecast: lgbUsd,
          upperBound: Number((lgbUsd * 1.05).toFixed(2)),
          lowerBound: Number((lgbUsd * 0.95).toFixed(2)),
          smf: d.smf ? Number((d.smf / usdRate).toFixed(2)) : undefined
        };
      } else {
        return {
          ...d,
          ptf: ptfTry,
          epnetForecast: lgbTry,
          lightgbmForecast: lgbTry,
          hybridForecast: lgbTry,
          upperBound: Number((lgbTry * 1.05).toFixed(2)),
          lowerBound: Number((lgbTry * 0.95).toFixed(2)),
          smf: d.smf
        };
      }
    });
  };

  const displayNextDayData = useMemo(() => convertDataCurrency(nextDayData), [nextDayData, currencyMode, usdRate]);

  const updatedSeriesConfigs = useMemo(() => {
    const unitStr = currencyMode === 'TRY' ? '₺/MWh' : '$/MWh';
    return seriesConfigs.map(s => ({ ...s, unit: unitStr }));
  }, [seriesConfigs, currencyMode]);
  const [lastRefreshTime, setLastRefreshTime] = useState<string>(
    new Date().toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  );

  const [backendMetrics, setBackendMetrics] = useState<any>({});

  const loadData = async () => {
    const nextDay = await fetchNextDayForecast();
    const compResult = await fetchLatestRealizedComparison(dateRange.startDate || 'latest');
    setNextDayData(nextDay);
    setComparisonData(compResult.series || []);
    setBackendMetrics(compResult.metrics || {});
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
    return formatDashboardMetrics(backendMetrics, currencyMode, usdRate);
  }, [backendMetrics, currencyMode, usdRate]);

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
                  usdRate={usdRate}
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
