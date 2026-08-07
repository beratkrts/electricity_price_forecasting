import React, { useState } from 'react';
import { TomorrowForecastSection } from '../components/dashboard/TomorrowForecastSection';
import { formatTimestampToDDMMYYYY } from '../utils/formatters';
import { HistoricalPerformanceSection } from '../components/dashboard/HistoricalPerformanceSection';
import { EnergyDataPoint, SeriesConfig, DateRangeState, TimeRangePreset, ChartTypeOption } from '../types/energy';
import { TableIcon } from 'lucide-react';

interface HomeProps {
  data: EnergyDataPoint[];
  seriesConfigs: SeriesConfig[];
  toggleSeriesVisibility: (id: string) => void;
  changeSeriesChartType: (id: string, chartType: ChartTypeOption) => void;
  dateRange: DateRangeState;
  setDateRange: React.Dispatch<React.SetStateAction<DateRangeState>>;
  currencyMode?: 'TRY' | 'USD';
  usdRate?: number;
}

export const Home: React.FC<HomeProps> = ({
  data,
  seriesConfigs,
  toggleSeriesVisibility,
  changeSeriesChartType,
  dateRange,
  setDateRange,
  currencyMode = 'USD',
  usdRate = 35.0
}) => {
  const [showTable, setShowTable] = useState<boolean>(false);

  const handlePresetChange = (preset: TimeRangePreset) => {
    if (preset === 'custom') {
      setDateRange((prev) => ({ ...prev, preset: 'custom' }));
    } else {
      setDateRange({
        preset,
        startDate: '2026-07-31',
        endDate: '2026-08-01'
      });
    }
  };

    const dateSelectorNode = (
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', background: 'rgba(15, 23, 42, 0.6)', padding: '6px 12px', borderRadius: '10px', border: '1px solid rgba(255, 255, 255, 0.05)' }}>
        <span style={{ color: '#94a3b8', fontWeight: 600, fontSize: '0.8rem' }}>Tahmin Aralığı:</span>
        <div style={{ display: 'flex', gap: '6px' }}>
          {(['24h', '7d', '30d'] as TimeRangePreset[]).map((r) => {
            const labels: Record<string, string> = { '24h': '1 Gün (Aktif)', '7d': '7 Gün (Yakında)', '30d': '1 Ay (Yakında)' };
            return (
              <button
                key={r}
                onClick={() => handlePresetChange(r)}
                style={{
                  padding: '4px 12px',
                  borderRadius: '6px',
                  border: 'none',
                  fontSize: '0.8rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                  background: dateRange.preset === r ? '#38bdf8' : 'transparent',
                  color: dateRange.preset === r ? '#070a12' : '#94a3b8',
                  opacity: r === '24h' ? 1 : 0.6
                }}
              >
                {labels[r] || r.toUpperCase()}
              </button>
            )
          })}
        </div>

        <div style={{ width: '1px', height: '24px', background: 'rgba(255, 255, 255, 0.1)' }} />

        <button
          onClick={() => setShowTable(!showTable)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '4px 12px',
            borderRadius: '6px',
            border: '1px solid rgba(255, 255, 255, 0.1)',
            fontSize: '0.8rem',
            fontWeight: 600,
            cursor: 'pointer',
            transition: 'all 0.2s ease',
            background: showTable ? '#10b981' : 'rgba(255, 255, 255, 0.08)',
            color: showTable ? '#ffffff' : 'var(--text-primary, #f8fafc)'
          }}
          className="table-toggle-btn"
        >
          {showTable ? 'Tabloyu Gizle' : 'Tabloyu Göster'}
        </button>
      </div>
    );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>

      <TomorrowForecastSection
        data={data}
        seriesConfigs={seriesConfigs}
        toggleSeriesVisibility={toggleSeriesVisibility}
        changeSeriesChartType={changeSeriesChartType}
        dateSelectorNode={dateSelectorNode}
        currencyMode={currencyMode}
      />

      {/* Conditional Data Table for Future Forecasts */}
      {/* Conditional Data Table for Future Forecasts */}
      <div className={`glass-panel ${!showTable ? 'hide-on-screen' : ''}`} style={{ padding: '20px', marginTop: '10px', boxSizing: 'border-box', maxWidth: '100%', overflow: 'hidden' }}>
        <h3 style={{ fontSize: '1rem', fontWeight: 700, color: '#fff', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <TableIcon size={18} color="#10b981" />
            Saatlik Gelecek Gün Tahminleri
          </h3>
          <div className="export-expandable-table" style={{ overflowX: 'auto', maxHeight: '400px', width: '100%' }}>
            <table style={{ width: '100%', minWidth: '700px', borderCollapse: 'collapse', fontSize: '0.85rem', textAlign: 'left' }}>
              <thead>
                <tr style={{ background: '#0f172a', color: '#38bdf8', position: 'sticky', top: 0, zIndex: 10, boxShadow: '0 2px 4px rgba(0,0,0,0.2)' }}>
                  <th style={{ padding: '12px', borderBottom: '1px solid rgba(255, 255, 255, 0.1)' }}>Tarih / Saat</th>
                  <th style={{ padding: '12px', borderBottom: '1px solid rgba(255, 255, 255, 0.1)' }}>Yapay Zeka Fiyat Tahmini ({currencyMode === 'USD' ? '$/MWh' : '₺/MWh'})</th>
                </tr>
              </thead>
              <tbody>
                {data.map((row, idx) => (
                  <tr key={idx} style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.04)' }}>
                    <td style={{ padding: '8px 12px', color: '#94a3b8' }}>{formatTimestampToDDMMYYYY(row.timestamp)}</td>
                    <td style={{ padding: '8px 12px', color: '#e11d48', fontWeight: 600 }}>{(row.lightgbmForecast).toLocaleString('tr-TR')} {currencyMode === 'USD' ? '$' : '₺'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
      </div>

      {/* Independent Historical Performance Section */}
      <HistoricalPerformanceSection currencyMode={currencyMode} usdRate={usdRate} />
    </div>
  );
};
