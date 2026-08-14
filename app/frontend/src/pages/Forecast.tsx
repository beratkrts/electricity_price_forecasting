import React, { useState } from 'react';
import { TodayBenchmarkSection } from '../components/dashboard/TodayBenchmarkSection';
import { HistoricalPerformanceSection } from '../components/dashboard/HistoricalPerformanceSection';
import { EnergyDataPoint, SeriesConfig, DashboardMetrics, ChartTypeOption } from '../types/energy';
import { Calendar, Table as TableIcon, CheckCircle2 } from 'lucide-react';
import { formatCurrency } from '../utils/formatters';
import { fetchLatestRealizedComparison } from '../services/energyDataService';
import { formatDashboardMetrics } from '../utils/mathHelpers';


interface ForecastProps {
  data: EnergyDataPoint[];
  seriesConfigs: SeriesConfig[];
  toggleSeriesVisibility: (id: string) => void;
  changeSeriesChartType: (id: string, chartType: ChartTypeOption) => void;
  metrics: DashboardMetrics;
  currencyMode?: 'TRY' | 'USD';
  usdRate?: number;
}

export const Forecast: React.FC<ForecastProps> = ({
  data: initialData,
  seriesConfigs,
  toggleSeriesVisibility,
  changeSeriesChartType,
  metrics: initialMetrics,
  currencyMode = 'USD',
  usdRate = 33.15
}) => {
  const todayStr = React.useMemo(() => new Date().toISOString().split('T')[0], []);
  const [activeQueryParam, setActiveQueryParam] = useState<string>('1d');
  const [historyStartDate, setHistoryStartDate] = useState<string>(todayStr);
  const [historyEndDate, setHistoryEndDate] = useState<string>(todayStr);
  const [compareMode, setCompareMode] = useState<'preset' | 'month' | 'year'>('preset');
  const [selectedMonth, setSelectedMonth] = useState<string>('2026-08');
  const [selectedYear, setSelectedYear] = useState<string>('2026');
  const [showTable, setShowTable] = useState<boolean>(false);
  const [rawChartData, setRawChartData] = useState<EnergyDataPoint[]>(initialData || []);

  const [backendMetrics, setBackendMetrics] = useState<any>({});

  React.useEffect(() => {
    if (initialData && initialData.length > 0 && rawChartData.length === 0) {
      setRawChartData(initialData);
    }
  }, [initialData]);

  React.useEffect(() => {
    let mounted = true;
    const updateComparisonData = async () => {
      const resData = await fetchLatestRealizedComparison(activeQueryParam);
      if (mounted) {
        if (resData.series && resData.series.length > 0) {
          setRawChartData(resData.series);
          // Set date inputs to the actual database dates being displayed
          if (activeQueryParam === 'latest' || activeQueryParam === '1d') {
            const actualDbDate = resData.series[0].date;
            if (actualDbDate) {
              setHistoryStartDate(actualDbDate);
              setHistoryEndDate(actualDbDate);
            }
          }
        } else if (activeQueryParam !== 'latest') {
          // If selected specific date (e.g. 2026-08-01) has no realized PTF data yet,
          // fall back to 'latest' so the graph doesn't render empty $0.00
          const fallbackData = await fetchLatestRealizedComparison('latest');
          if (mounted && fallbackData.series && fallbackData.series.length > 0) {
            setRawChartData(fallbackData.series);
            const actualDbDate = fallbackData.series[0].date;
            if (actualDbDate) {
              setHistoryStartDate(actualDbDate);
              setHistoryEndDate(actualDbDate);
            }
            if (fallbackData.metrics) setBackendMetrics(fallbackData.metrics);
          }
        }
        if (resData.metrics && Object.keys(resData.metrics).length > 0) {
          setBackendMetrics(resData.metrics);
        }
      }
    };
    updateComparisonData();
    return () => { mounted = false; };
  }, [activeQueryParam]);

  // Convert rawChartData based on currencyMode (Use DB USD values if available)
  const chartData = React.useMemo(() => {
    if (currencyMode === 'TRY') return rawChartData;
    const fallbackRate = usdRate > 0 ? usdRate : 33.15;
    return rawChartData.map(d => {
      const ptfVal = d.ptfUsd !== undefined && d.ptfUsd !== null ? d.ptfUsd : Number((d.ptf / fallbackRate).toFixed(2));
      const lgbVal = d.lightgbmForecastUsd !== undefined && d.lightgbmForecastUsd !== null ? d.lightgbmForecastUsd : Number((d.lightgbmForecast / fallbackRate).toFixed(2));
      const ubVal = d.upperBoundUsd !== undefined && d.upperBoundUsd !== null ? d.upperBoundUsd : Number((d.upperBound / fallbackRate).toFixed(2));
      const lbVal = d.lowerBoundUsd !== undefined && d.lowerBoundUsd !== null ? d.lowerBoundUsd : Number((d.lowerBound / fallbackRate).toFixed(2));
      return {
        ...d,
        ptf: ptfVal,
        lightgbmForecast: lgbVal,
        upperBound: ubVal,
        lowerBound: lbVal,
      };
    });
  }, [rawChartData, currencyMode, usdRate]);

  const currentMetrics = React.useMemo(() => {
    if (Object.keys(backendMetrics).length > 0) {
      return formatDashboardMetrics(backendMetrics, currencyMode, usdRate);
    }
    return initialMetrics;
  }, [backendMetrics, currencyMode, usdRate, initialMetrics]);

  const formatDate = (dateStr: string) => {
    if (!dateStr) return '';
    const parts = dateStr.split('-');
    if (parts.length !== 3) return dateStr;
    return `${parts[2]}.${parts[1]}.${parts[0]}`;
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>

      {/* Section Header (Moved from TodayBenchmarkSection) */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '-6px' }}>
        <div style={{ padding: '6px', borderRadius: '8px', background: 'rgba(56, 189, 248, 0.2)', color: '#38bdf8' }}>
          <CheckCircle2 size={20} />
        </div>
        <div>
          <h2 style={{ fontSize: '1.2rem', fontWeight: 700, color: '#fff', margin: 0 }}>
            {chartData && chartData.length > 0 && chartData[0].date ? formatDate(chartData[0].date) : 'Seçilen Tarih'} Model Tahminimiz vs EPİAŞ Gerçekleşen PTF Kıyaslaması
          </h2>
          <p style={{ fontSize: '0.8rem', color: '#94a3b8', margin: 0 }}>
            EPİAŞ gerçekleşen PTF geldikten sonra model tahmini ile gerçek fiyatların karşılaştırılması ve hata payları ({chartData && chartData.length > 0 && chartData[0].date ? formatDate(chartData[0].date) : 'Seçilen Tarih'})
          </p>
        </div>
      </div>

      {/* Forecast comparison page controls */}
      <div className="glass-panel" style={{ padding: '12px 16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%', gap: '8px', flexWrap: 'nowrap', overflowX: 'auto' }}>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'nowrap', flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px', flexShrink: 0, marginRight: '0' }}>
            <Calendar size={18} color="#f43f5e" />
            <span style={{ color: '#fff', fontWeight: 600, fontSize: '0.95rem', whiteSpace: 'nowrap' }}>Kıyaslama Aralığı:</span>
          </div>

          <div style={{ display: 'flex', background: 'rgba(15, 23, 42, 0.6)', padding: '2px', borderRadius: '10px', border: '1px solid rgba(255, 255, 255, 0.1)', flexShrink: 0 }}>
            <button
              onClick={() => setCompareMode('preset')}
              style={{ background: compareMode === 'preset' ? '#38bdf8' : 'transparent', color: compareMode === 'preset' ? '#0f172a' : '#94a3b8', border: 'none', padding: '4px 8px', borderRadius: '6px', fontSize: '0.8rem', fontWeight: 600, cursor: 'pointer', transition: 'all 0.2s' }}
            >
              Gün Bazlı Kıyaslama
            </button>
            <button
              onClick={() => setCompareMode('month')}
              style={{ background: compareMode === 'month' ? '#38bdf8' : 'transparent', color: compareMode === 'month' ? '#0f172a' : '#94a3b8', border: 'none', padding: '4px 8px', borderRadius: '6px', fontSize: '0.8rem', fontWeight: 600, cursor: 'pointer', transition: 'all 0.2s' }}
            >
              Ay Bazlı Kıyaslama
            </button>
            <button
              onClick={() => setCompareMode('year')}
              style={{ background: compareMode === 'year' ? '#38bdf8' : 'transparent', color: compareMode === 'year' ? '#0f172a' : '#94a3b8', border: 'none', padding: '4px 8px', borderRadius: '6px', fontSize: '0.8rem', fontWeight: 600, cursor: 'pointer', transition: 'all 0.2s' }}
            >
              Yıl Bazlı Kıyaslama
            </button>
          </div>

          {compareMode === 'preset' && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'nowrap' }}>
              <div style={{ display: 'flex', background: 'rgba(15, 23, 42, 0.6)', padding: '2px', borderRadius: '8px', border: '1px solid rgba(255, 255, 255, 0.05)' }}>
                {[
                  { id: '1d', label: '1g' },
                  { id: '7d', label: '1h' },
                  { id: '1m', label: '1a' },
                  { id: '3m', label: '3a' },
                  { id: '6m', label: '6a' },
                  { id: '1y', label: '1y' },
                  { id: '2y', label: '2y' }
                ].map((preset) => (
                  <button
                    key={preset.id}
                    onClick={() => { setActiveQueryParam(preset.id); }}
                    style={{ padding: '4px 6px', borderRadius: '4px', border: 'none', fontSize: '0.75rem', fontWeight: 600, cursor: 'pointer', background: activeQueryParam === preset.id ? '#38bdf8' : 'transparent', color: activeQueryParam === preset.id ? '#0f172a' : '#94a3b8' }}
                  >
                    {preset.label}
                  </button>
                ))}
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px', background: 'rgba(15, 23, 42, 0.6)', padding: '4px 8px', borderRadius: '10px', border: '1px solid rgba(255, 255, 255, 0.1)', flexShrink: 0 }}>
                <input
                  type="date"
                  value={historyStartDate}
                  onChange={(e) => setHistoryStartDate(e.target.value)}
                  style={{ background: 'rgba(0,0,0,0.3)', border: '1px solid rgba(255,255,255,0.2)', color: '#fff', borderRadius: '6px', padding: '4px 8px', fontSize: '0.85rem', outline: 'none', colorScheme: 'dark' }}
                />
                <span style={{ color: '#94a3b8', fontSize: '0.9rem' }}>-</span>
                <input
                  type="date"
                  value={historyEndDate}
                  onChange={(e) => setHistoryEndDate(e.target.value)}
                  style={{ background: 'rgba(0,0,0,0.3)', border: '1px solid rgba(255,255,255,0.2)', color: '#fff', borderRadius: '6px', padding: '4px 8px', fontSize: '0.85rem', outline: 'none', colorScheme: 'dark' }}
                />
                <button
                  onClick={() => {
                    if (historyStartDate && historyEndDate) {
                      setActiveQueryParam(historyStartDate === historyEndDate ? historyStartDate : `${historyStartDate}_to_${historyEndDate}`);
                    }
                  }}
                  style={{
                    background: '#10b981', color: '#fff', padding: '4px 10px', borderRadius: '6px', border: 'none', fontWeight: 600, cursor: 'pointer', fontSize: '0.8rem', marginLeft: '4px'
                  }}
                >
                  Göster
                </button>
              </div>
            </div>
          )}

          {compareMode === 'month' && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', background: 'rgba(15, 23, 42, 0.6)', padding: '6px 12px', borderRadius: '10px', border: '1px solid rgba(255, 255, 255, 0.1)', flexShrink: 0 }}>
              <Calendar size={16} color="#38bdf8" />
              <input
                type="month"
                value={selectedMonth}
                min="2024-08"
                max="2026-08"
                onChange={(e) => {
                  setSelectedMonth(e.target.value);
                }}
                style={{ background: 'rgba(0,0,0,0.3)', border: '1px solid rgba(255,255,255,0.2)', color: '#fff', borderRadius: '6px', padding: '4px 8px', fontSize: '0.82rem', outline: 'none', colorScheme: 'dark' }}
              />
              <button
                onClick={() => {
                  if (selectedMonth) {
                    const yyyy = selectedMonth.split('-')[0];
                    const mm = selectedMonth.split('-')[1];
                    const days = new Date(parseInt(yyyy), parseInt(mm), 0).getDate();
                    setActiveQueryParam(`${selectedMonth}-01_to_${selectedMonth}-${days}`);
                  }
                }}
                style={{
                  background: '#10b981', color: '#fff', padding: '4px 10px', borderRadius: '6px', border: 'none', fontWeight: 600, cursor: 'pointer', fontSize: '0.8rem'
                }}
              >
                Göster
              </button>
            </div>
          )}

          {compareMode === 'year' && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', background: 'rgba(15, 23, 42, 0.6)', padding: '6px 12px', borderRadius: '10px', border: '1px solid rgba(255, 255, 255, 0.1)', flexShrink: 0 }}>
              <Calendar size={16} color="#fbbf24" />
              <select
                value={selectedYear}
                onChange={(e) => {
                  setSelectedYear(e.target.value);
                }}
                style={{ background: 'rgba(0,0,0,0.3)', border: '1px solid rgba(255,255,255,0.2)', color: '#fff', borderRadius: '6px', padding: '4px 8px', fontSize: '0.82rem', outline: 'none', cursor: 'pointer' }}
              >
                <option value="2026">2026</option>
                <option value="2025">2025</option>
                <option value="2024">2024</option>
              </select>
              <button
                onClick={() => {
                  if (selectedYear) {
                    setActiveQueryParam(`${selectedYear}-01-01_to_${selectedYear}-12-31`);
                  }
                }}
                style={{
                  background: '#10b981', color: '#fff', padding: '4px 10px', borderRadius: '6px', border: 'none', fontWeight: 600, cursor: 'pointer', fontSize: '0.8rem'
                }}
              >
                Göster
              </button>
            </div>
          )}
        </div>

        <button
          className="table-toggle-btn"
          onClick={() => setShowTable(!showTable)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '6px 16px',
            borderRadius: '8px',
            border: '1px solid rgba(255, 255, 255, 0.1)',
            fontSize: '0.85rem',
            fontWeight: 600,
            cursor: 'pointer',
            transition: 'all 0.2s ease',
            background: showTable ? '#10b981' : 'rgba(255, 255, 255, 0.05)',
            color: showTable ? '#ffffff' : '#f8fafc',
            flexShrink: 0
          }}
        >
          <TableIcon size={16} />
          {showTable ? 'Tabloyu Gizle' : 'Tabloyu Göster'}
        </button>
      </div>

      <TodayBenchmarkSection
        data={chartData}
        seriesConfigs={seriesConfigs}
        toggleSeriesVisibility={toggleSeriesVisibility}
        changeSeriesChartType={changeSeriesChartType}
        metrics={currentMetrics}
        currencyMode={currencyMode}
      />

      {/* Conditional Data Table for Forecast vs Actuals */}
      <div className={`glass-panel ${!showTable ? 'hide-on-screen' : ''}`} style={{ padding: '20px', marginTop: '10px', boxSizing: 'border-box', maxWidth: '100%', overflow: 'hidden' }}>
        <h3 style={{ fontSize: '1rem', fontWeight: 700, color: '#fff', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <TableIcon size={18} color="#10b981" />
            Tahmin vs Gerçekleşen Değerler Tablosu
          </h3>
          <div className="export-expandable-table" style={{ overflowX: 'auto', maxHeight: '400px', width: '100%' }}>
            <table style={{ width: '100%', minWidth: '700px', borderCollapse: 'collapse', fontSize: '0.85rem', textAlign: 'left' }}>
              <thead>
                <tr style={{ background: '#0f172a', color: '#38bdf8', position: 'sticky', top: 0, zIndex: 10, boxShadow: '0 2px 4px rgba(0,0,0,0.2)' }}>
                  <th style={{ padding: '12px', borderBottom: '1px solid rgba(255, 255, 255, 0.1)' }}>Tarih / Saat</th>
                  <th style={{ padding: '12px', borderBottom: '1px solid rgba(255, 255, 255, 0.1)' }}>Gerçekleşen PTF</th>
                  <th style={{ padding: '12px', borderBottom: '1px solid rgba(255, 255, 255, 0.1)' }}>Yapay Zeka Fiyat Tahmini</th>
                  <th style={{ padding: '12px', borderBottom: '1px solid rgba(255, 255, 255, 0.1)' }}>Fark (Hata)</th>
                  <th style={{ padding: '12px', borderBottom: '1px solid rgba(255, 255, 255, 0.1)' }}>Hata Oranı</th>
                </tr>
              </thead>
              <tbody>
                {chartData.map((row, idx) => {
                  const ptfVal = row.ptf || 0;
                  const lgbVal = row.lightgbmForecast || 0;
                  const diff = Math.abs(lgbVal - ptfVal);
                  
                  // Always use USD values for percentage error to prevent FX distortion
                  const ptfUsd = row.ptfUsd && row.ptfUsd > 0 ? row.ptfUsd : ptfVal;
                  const lgbUsd = row.lightgbmForecastUsd !== undefined ? row.lightgbmForecastUsd : lgbVal;
                  const ape = ptfUsd > 0 ? (Math.abs(lgbUsd - ptfUsd) / ptfUsd) * 100 : 0;
                  
                  const symbolStr = currencyMode === 'USD' ? '$' : '₺';

                  return (
                    <tr key={idx} style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.04)' }}>
                      <td style={{ padding: '8px 12px', color: '#94a3b8', whiteSpace: 'nowrap' }}>{row.timestamp}</td>
                      <td style={{ padding: '8px 12px', color: '#fff', fontWeight: 600 }}>{formatCurrency(ptfVal, symbolStr)}</td>
                      <td style={{ padding: '8px 12px', color: '#c084fc', fontWeight: 600 }}>{formatCurrency(lgbVal, symbolStr)}</td>
                      <td style={{ padding: '8px 12px', color: '#38bdf8' }}>{formatCurrency(diff, symbolStr)}</td>
                      <td style={{ padding: '8px 12px', color: ape > 10 ? '#f43f5e' : '#10b981' }}>%{ape.toFixed(2)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      <HistoricalPerformanceSection
        selectedRange={activeQueryParam}
        currencyMode={currencyMode}
        usdRate={usdRate}
      />

    </div>
  );
};
