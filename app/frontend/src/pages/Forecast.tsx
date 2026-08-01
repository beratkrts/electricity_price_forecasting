import React, { useState } from 'react';
import { TodayBenchmarkSection } from '../components/dashboard/TodayBenchmarkSection';
import { HistoricalPerformanceSection } from '../components/dashboard/HistoricalPerformanceSection';
import { IntersectionList } from '../components/dashboard/IntersectionList';
import { EnergyDataPoint, SeriesConfig, IntersectionPoint, DashboardMetrics, ChartTypeOption } from '../types/energy';
import { Calendar, Table as TableIcon } from 'lucide-react';
import { formatCurrency } from '../utils/formatters';
import { fetchLatestRealizedComparison } from '../services/energyDataService';

interface ForecastProps {
  data: EnergyDataPoint[];
  seriesConfigs: SeriesConfig[];
  toggleSeriesVisibility: (id: string) => void;
  changeSeriesChartType: (id: string, chartType: ChartTypeOption) => void;
  intersections: IntersectionPoint[];
  showIntersections: boolean;
  setShowIntersections: (show: boolean) => void;
  metrics: DashboardMetrics;
  currencyMode?: 'TRY' | 'USD';
}

export const Forecast: React.FC<ForecastProps> = ({
  data: initialData,
  seriesConfigs,
  toggleSeriesVisibility,
  changeSeriesChartType,
  intersections,
  showIntersections,
  setShowIntersections,
  metrics,
  currencyMode = 'USD'
}) => {
  const [selectedIntersection, setSelectedIntersection] = useState<IntersectionPoint | null>(null);
  
  const todayStr = React.useMemo(() => {
    const d = new Date();
    return d.toISOString().split('T')[0];
  }, []);

  const [historyStartDate, setHistoryStartDate] = useState<string>(todayStr);
  const [historyEndDate, setHistoryEndDate] = useState<string>(todayStr);
  const [showTable, setShowTable] = useState<boolean>(false);
  const [rawChartData, setRawChartData] = useState<EnergyDataPoint[]>(initialData);

  // Sync rawChartData when initialData prop changes
  React.useEffect(() => {
    if (initialData && initialData.length > 0) {
      setRawChartData(initialData);
    }
  }, [initialData]);

  React.useEffect(() => {
    let mounted = true;
    const updateComparisonData = async () => {
      if (historyStartDate && historyEndDate) {
        const queryParam = historyStartDate === historyEndDate 
          ? historyEndDate 
          : `${historyStartDate}_to_${historyEndDate}`;
        const newData = await fetchLatestRealizedComparison(queryParam);
        if (mounted && newData && newData.length > 0) {
          setRawChartData(newData);
        }
      }
    };
    updateComparisonData();
    return () => { mounted = false; };
  }, [historyStartDate, historyEndDate]);

  // Convert rawChartData based on currencyMode
  const chartData = React.useMemo(() => {
    if (currencyMode === 'TRY') return rawChartData;
    // Assuming USD conversion rate if raw data is TRY
    const rate = 33.15;
    return rawChartData.map(d => ({
      ...d,
      ptf: Number((d.ptf / rate).toFixed(2)),
      epnetForecast: Number((d.epnetForecast / rate).toFixed(2)),
      lightgbmForecast: Number((d.lightgbmForecast / rate).toFixed(2)),
      hybridForecast: Number((d.hybridForecast / rate).toFixed(2)),
      upperBound: Number((d.upperBound / rate).toFixed(2)),
      lowerBound: Number((d.lowerBound / rate).toFixed(2)),
      smf: d.smf ? Number((d.smf / rate).toFixed(2)) : undefined
    }));
  }, [rawChartData, currencyMode]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      
      {/* Forecast comparison page controls */}
      <div className="glass-panel" style={{ padding: '12px 20px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <Calendar size={18} color="#f43f5e" />
          <span style={{ color: '#fff', fontWeight: 600, fontSize: '0.9rem' }}>Kıyaslama Aralığı:</span>
          
          <div style={{ display: 'flex', background: 'rgba(15, 23, 42, 0.6)', padding: '2px', borderRadius: '6px', border: '1px solid rgba(255, 255, 255, 0.05)', marginRight: '8px' }}>
            {[
              { id: '1d', label: '1g' },
              { id: '7d', label: '7g' },
              { id: '1m', label: '1a' },
              { id: '3m', label: '3a' },
              { id: '6m', label: '6a' },
              { id: '1y', label: '1y' }
            ].map((preset) => (
              <button
                key={preset.id}
                onClick={() => {
                  const today = new Date();
                  const endStr = today.toISOString().split('T')[0];
                  setHistoryEndDate(endStr);
                  let start = new Date(today);
                  if (preset.id === '1d') start.setDate(today.getDate() - 1);
                  else if (preset.id === '7d') start.setDate(today.getDate() - 7);
                  else if (preset.id === '1m') start.setMonth(today.getMonth() - 1);
                  else if (preset.id === '3m') start.setMonth(today.getMonth() - 3);
                  else if (preset.id === '6m') start.setMonth(today.getMonth() - 6);
                  else if (preset.id === '1y') start.setFullYear(today.getFullYear() - 1);
                  setHistoryStartDate(start.toISOString().split('T')[0]);
                }}
                style={{
                  padding: '4px 8px',
                  borderRadius: '4px',
                  border: 'none',
                  fontSize: '0.75rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  background: 'transparent',
                  color: '#94a3b8'
                }}
                onMouseOver={(e) => { e.currentTarget.style.color = '#fff'; }}
                onMouseOut={(e) => { e.currentTarget.style.color = '#94a3b8'; }}
              >
                {preset.label}
              </button>
            ))}
          </div>

          <input
            type="date"
            value={historyStartDate}
            onChange={(e) => setHistoryStartDate(e.target.value)}
            style={{
              background: 'rgba(15, 23, 42, 0.9)',
              border: '1px solid rgba(244, 63, 94, 0.4)',
              color: '#fff',
              padding: '6px 12px',
              borderRadius: '8px',
              fontSize: '0.85rem',
              outline: 'none',
              colorScheme: 'dark'
            }}
          />
          <span style={{ color: '#94a3b8', fontSize: '0.9rem' }}>-</span>
          <input
            type="date"
            value={historyEndDate}
            onChange={(e) => setHistoryEndDate(e.target.value)}
            style={{
              background: 'rgba(15, 23, 42, 0.9)',
              border: '1px solid rgba(244, 63, 94, 0.4)',
              color: '#fff',
              padding: '6px 12px',
              borderRadius: '8px',
              fontSize: '0.85rem',
              outline: 'none',
              colorScheme: 'dark'
            }}
          />
        </div>

        <button
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
            color: showTable ? '#ffffff' : '#f8fafc'
          }}
        >
          <TableIcon size={16} />
          {showTable ? 'Tablo Görünümünü Kapat' : 'Değerleri Tablo Olarak Gör'}
        </button>
      </div>

      <TodayBenchmarkSection
        data={chartData}
        seriesConfigs={seriesConfigs}
        toggleSeriesVisibility={toggleSeriesVisibility}
        changeSeriesChartType={changeSeriesChartType}
        intersections={intersections}
        showIntersections={showIntersections}
        setShowIntersections={setShowIntersections}
        metrics={metrics}
        onIntersectionSelect={(it) => setSelectedIntersection(it)}
        currencyMode={currencyMode}
      />

      <HistoricalPerformanceSection selectedRange={historyStartDate && historyEndDate ? `${historyStartDate}_to_${historyEndDate}` : '1y'} />

      {showIntersections && intersections.length > 0 && (
        <IntersectionList
          intersections={intersections}
          selectedIntersection={selectedIntersection}
          onSelectIntersection={(it) => setSelectedIntersection(it)}
        />
      )}

      {/* Conditional Data Table for Forecast vs Actuals */}
      {showTable && (
        <div className="glass-panel" style={{ padding: '20px', marginTop: '10px', boxSizing: 'border-box', maxWidth: '100%', overflow: 'hidden' }}>
          <h3 style={{ fontSize: '1rem', fontWeight: 700, color: '#fff', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <TableIcon size={18} color="#10b981" />
            Tahmin vs Gerçekleşen Değerler Tablosu
          </h3>
          <div style={{ overflowX: 'auto', maxHeight: '400px', width: '100%' }}>
            <table style={{ width: '100%', minWidth: '700px', borderCollapse: 'collapse', fontSize: '0.85rem', textAlign: 'left' }}>
              <thead>
                <tr style={{ background: '#0f172a', color: '#38bdf8', position: 'sticky', top: 0, zIndex: 10, boxShadow: '0 2px 4px rgba(0,0,0,0.2)' }}>
                  <th style={{ padding: '12px', borderBottom: '1px solid rgba(255, 255, 255, 0.1)' }}>Tarih / Saat</th>
                  <th style={{ padding: '12px', borderBottom: '1px solid rgba(255, 255, 255, 0.1)' }}>Gerçekleşen PTF</th>
                  <th style={{ padding: '12px', borderBottom: '1px solid rgba(255, 255, 255, 0.1)' }}>Hibrit Tahmin</th>
                  <th style={{ padding: '12px', borderBottom: '1px solid rgba(255, 255, 255, 0.1)' }}>EPNet Tahmin</th>
                  <th style={{ padding: '12px', borderBottom: '1px solid rgba(255, 255, 255, 0.1)' }}>LightGBM Tahmin</th>
                  <th style={{ padding: '12px', borderBottom: '1px solid rgba(255, 255, 255, 0.1)' }}>MAPE (%)</th>
                  <th style={{ padding: '12px', borderBottom: '1px solid rgba(255, 255, 255, 0.1)' }}>WAPE (%)</th>
                </tr>
              </thead>
              <tbody>
                {chartData.map((row, idx) => {
                  const mape = row.ptf ? Math.abs((row.hybridForecast - row.ptf) / row.ptf) * 100 : 0;
                  const wape = row.ptf ? Math.abs(row.hybridForecast - row.ptf) / (row.ptf > 0 ? row.ptf : 1) * 100 : 0;
                  
                  return (
                    <tr key={idx} style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.04)' }}>
                      <td style={{ padding: '8px 12px', color: '#94a3b8', whiteSpace: 'nowrap' }}>{row.timestamp}</td>
                      <td style={{ padding: '8px 12px', color: '#fff', fontWeight: 600 }}>{formatCurrency(row.ptf, '₺')}</td>
                      <td style={{ padding: '8px 12px', color: '#fbbf24' }}>{formatCurrency(row.hybridForecast, '₺')}</td>
                      <td style={{ padding: '8px 12px', color: '#10b981' }}>{formatCurrency(row.epnetForecast, '₺')}</td>
                      <td style={{ padding: '8px 12px', color: '#c084fc' }}>{formatCurrency(row.lightgbmForecast, '₺')}</td>
                      <td style={{ padding: '8px 12px', color: mape > 10 ? '#f43f5e' : '#10b981' }}>%{mape.toFixed(2)}</td>
                      <td style={{ padding: '8px 12px', color: wape > 10 ? '#f43f5e' : '#10b981' }}>%{wape.toFixed(2)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

    </div>
  );
};
