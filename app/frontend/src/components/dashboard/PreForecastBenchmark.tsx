import React, { useState, useEffect } from 'react';
import ReactECharts from 'echarts-for-react';
import { Zap, Sun, Wind, Activity, Table as TableIcon } from 'lucide-react';
import { formatNumber } from '../../utils/formatters';

interface PreForecastBenchmarkProps {
  currencyMode?: 'TRY' | 'USD';
  usdRate?: number;
}

interface PreForecastMetric {
  total_hours: number;
  load_mae_mw: number;
  load_wape_pct: number;
  solar_mae_mw: number;
  solar_wape_pct: number;
  wind_mae_mw: number;
  wind_wape_pct: number;
}

interface PreForecastSeriesRow {
  timestamp: string;
  date: string;
  hour: string;
  pred_load_mw: number | null;
  actual_load_mw: number | null;
  pred_solar_mw: number | null;
  actual_solar_mw: number | null;
  pred_wind_mw: number | null;
  actual_wind_mw: number | null;
}

export const PreForecastBenchmark: React.FC<PreForecastBenchmarkProps> = () => {
  const [timeRange, setTimeRange] = useState<string>('1m');
  const [loading, setLoading] = useState<boolean>(true);
  const [seriesData, setSeriesData] = useState<PreForecastSeriesRow[]>([]);
  const [metrics, setMetrics] = useState<PreForecastMetric | null>(null);
  const [activeTab, setActiveTab] = useState<'load' | 'solar' | 'wind'>('load');
  const [showTable, setShowTable] = useState<boolean>(false);

  // Dynamic Theme Detection
  const [isLightMode, setIsLightMode] = useState<boolean>(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('etkb_theme') === 'light' || document.documentElement.classList.contains('light-theme');
    }
    return false;
  });

  useEffect(() => {
    const observer = new MutationObserver(() => {
      const isLight = document.documentElement.classList.contains('light-theme') || localStorage.getItem('etkb_theme') === 'light';
      setIsLightMode(isLight);
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    fetchPreForecastData(timeRange);
  }, [timeRange]);

  const fetchPreForecastData = async (range: string) => {
    setLoading(true);
    try {
      const res = await fetch(`/api/db-data?type=pre_forecasts&date=${range}`);
      const json = await res.json();
      if (json && json.series) {
        setSeriesData(json.series);
        setMetrics(json.metrics);
      }
    } catch (err) {
      console.error('Pre-forecast fetch error:', err);
    } finally {
      setLoading(false);
    }
  };

  // Theme Styles
  const theme = {
    cardBg: isLightMode ? '#ffffff' : 'rgba(30, 41, 59, 0.7)',
    cardBorder: isLightMode ? '#e2e8f0' : 'rgba(255, 255, 255, 0.08)',
    textPrimary: isLightMode ? '#0f172a' : '#f8fafc',
    textSecondary: isLightMode ? '#475569' : '#94a3b8',
    textMuted: isLightMode ? '#64748b' : '#cbd5e1',
    innerBg: isLightMode ? '#f8fafc' : '#0f172a',
    innerBorder: isLightMode ? '#cbd5e1' : '#334155',
    tooltipBg: isLightMode ? 'rgba(255, 255, 255, 0.95)' : 'rgba(15, 23, 42, 0.95)',
    tooltipBorder: isLightMode ? '#cbd5e1' : '#334155',
    tooltipText: isLightMode ? '#0f172a' : '#f8fafc',
    tableHeaderBg: isLightMode ? '#f1f5f9' : '#1e293b',
    tableBorder: isLightMode ? '#e2e8f0' : 'rgba(51, 65, 85, 0.4)',
    tableRowAlt: isLightMode ? '#ffffff' : '#0f172a'
  };

  // ECharts Option Generator
  const getChartOption = () => {
    const timestamps = seriesData.map(d => d.timestamp || d.hour);

    let predData: (number | null)[] = [];
    let actualData: (number | null)[] = [];
    let title = '';
    let predColor = '';
    let actualColor = '';

    if (activeTab === 'load') {
      predData = seriesData.map(d => d.pred_load_mw);
      actualData = seriesData.map(d => d.actual_load_mw);
      title = 'Şebeke Yük Tüketim Tahminimiz vs EPİAŞ Resmi Yük Tahmini (LEP - MW)';
      predColor = '#6366f1';
      actualColor = '#0284c7';
    } else if (activeTab === 'solar') {
      predData = seriesData.map(d => d.pred_solar_mw);
      actualData = seriesData.map(d => d.actual_solar_mw);
      title = 'Güneş Üretim Tahminimiz vs EPİAŞ Resmi Güneş Planı (GES KGÜP - MW)';
      predColor = '#d97706';
      actualColor = '#f59e0b';
    } else {
      predData = seriesData.map(d => d.pred_wind_mw);
      actualData = seriesData.map(d => d.actual_wind_mw);
      title = 'Rüzgar Üretim Tahminimiz vs EPİAŞ Resmi Rüzgar Planı (RES KGÜP - MW)';
      predColor = '#059669';
      actualColor = '#10b981';
    }

    return {
      title: {
        text: title,
        textStyle: { color: theme.textPrimary, fontSize: 13, fontWeight: 'bold' }
      },
      tooltip: {
        trigger: 'axis',
        backgroundColor: theme.tooltipBg,
        borderColor: theme.tooltipBorder,
        textStyle: { color: theme.tooltipText },
        formatter: (params: any[]) => {
          let res = `<div style="font-weight:bold;margin-bottom:4px;">${params[0]?.name || ''}</div>`;
          params.forEach(p => {
            const val = p.value !== null && p.value !== undefined ? `${formatNumber(p.value, 0)} MW` : 'N/A';
            res += `<div style="display:flex;justify-content:space-between;gap:12px;">
                      <span><span style="color:${p.color};">●</span> ${p.seriesName}:</span>
                      <span style="font-weight:bold">${val}</span>
                    </div>`;
          });
          return res;
        }
      },
      legend: {
        data: ['Yapay Zeka Pre-Forecast Tahminimiz', 'EPİAŞ Resmi Planı / Tahmini'],
        textStyle: { color: theme.textSecondary },
        right: 10
      },
      grid: { left: '3%', right: '3%', bottom: '3%', containLabel: true },
      xAxis: {
        type: 'category',
        data: timestamps,
        axisLine: { lineStyle: { color: theme.innerBorder } },
        axisLabel: { color: theme.textSecondary, fontSize: 10 }
      },
      yAxis: {
        type: 'value',
        name: 'MW',
        axisLine: { lineStyle: { color: theme.innerBorder } },
        splitLine: { lineStyle: { color: isLightMode ? 'rgba(203, 213, 225, 0.6)' : 'rgba(51, 65, 85, 0.4)', type: 'dashed' } },
        axisLabel: { color: theme.textSecondary }
      },
      series: [
        {
          name: 'Yapay Zeka Pre-Forecast Tahminimiz',
          type: 'line',
          smooth: true,
          showSymbol: false,
          data: predData,
          itemStyle: { color: predColor },
          lineStyle: { width: 2.5 }
        },
        {
          name: 'EPİAŞ Resmi Planı / Tahmini',
          type: 'line',
          smooth: true,
          showSymbol: false,
          data: actualData,
          itemStyle: { color: actualColor },
          lineStyle: { width: 2, type: 'dashed' }
        }
      ]
    };
  };

  return (
    <div style={{ background: theme.cardBg, border: `1px solid ${theme.cardBorder}`, borderRadius: '12px', padding: '20px', display: 'flex', flexDirection: 'column', gap: '20px', transition: 'all 0.2s ease' }}>
      
      {/* Header & Controls */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <Activity style={{ color: '#38bdf8', width: '22px', height: '22px' }} />
          <div>
            <h3 style={{ margin: 0, color: theme.textPrimary, fontSize: '16px', fontWeight: 600 }}>Yük ve Yenilenebilir Üretim Pre-Forecast Tahmin Analizi</h3>
            <p style={{ margin: 0, color: theme.textSecondary, fontSize: '12px' }}>Yapay zeka modellerimizin Şebeke Tüketimi (Load), Güneş (Solar) ve Rüzgar (Wind) tahmin performansları vs EPİAŞ Açıklanan Planlar</p>
          </div>
        </div>

        {/* Time Range Filter Buttons */}
        <div style={{ display: 'flex', gap: '6px', background: theme.innerBg, padding: '4px', borderRadius: '8px', border: `1px solid ${theme.innerBorder}` }}>
          {[
            { id: '7d', label: '7 Gün' },
            { id: '1m', label: '30 Gün' },
            { id: '3m', label: '90 Gün' },
            { id: '1y', label: '1 Yıl' }
          ].map(r => (
            <button
              key={r.id}
              onClick={() => setTimeRange(r.id)}
              style={{
                background: timeRange === r.id ? '#3b82f6' : 'transparent',
                color: timeRange === r.id ? '#ffffff' : theme.textSecondary,
                border: 'none',
                padding: '5px 12px',
                borderRadius: '6px',
                cursor: 'pointer',
                fontSize: '12px',
                fontWeight: 500
              }}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>

      {/* KPI Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '14px' }}>
        {/* Load KPI */}
        <div
          onClick={() => setActiveTab('load')}
          style={{
            background: activeTab === 'load' ? (isLightMode ? '#e0e7ff' : 'rgba(99, 102, 241, 0.15)') : theme.innerBg,
            border: activeTab === 'load' ? '1.5px solid #6366f1' : `1px solid ${theme.innerBorder}`,
            borderRadius: '10px',
            padding: '14px',
            cursor: 'pointer',
            transition: 'all 0.2s ease'
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ color: theme.textPrimary, fontSize: '13px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Zap style={{ width: '16px', height: '16px', color: '#6366f1' }} /> Yük (Tüketim) Tahmini
            </span>
            <span style={{ background: 'rgba(99, 102, 241, 0.2)', color: isLightMode ? '#4338ca' : '#818cf8', fontSize: '10px', padding: '2px 6px', borderRadius: '4px', fontWeight: 600 }}>WAPE</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
            <span style={{ fontSize: '24px', fontWeight: 700, color: theme.textPrimary }}>
              %{metrics?.load_wape_pct !== undefined ? metrics.load_wape_pct : '--'}
            </span>
            <span style={{ color: theme.textSecondary, fontSize: '12px' }}>
              MAE: {metrics?.load_mae_mw ? `${formatNumber(metrics.load_mae_mw, 0)} MW` : '--'}
            </span>
          </div>
        </div>

        {/* Solar KPI */}
        <div
          onClick={() => setActiveTab('solar')}
          style={{
            background: activeTab === 'solar' ? (isLightMode ? '#fef3c7' : 'rgba(245, 158, 11, 0.15)') : theme.innerBg,
            border: activeTab === 'solar' ? '1.5px solid #f59e0b' : `1px solid ${theme.innerBorder}`,
            borderRadius: '10px',
            padding: '14px',
            cursor: 'pointer',
            transition: 'all 0.2s ease'
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ color: theme.textPrimary, fontSize: '13px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Sun style={{ width: '16px', height: '16px', color: '#f59e0b' }} /> Güneş (GES KGÜP) Tahmini
            </span>
            <span style={{ background: 'rgba(245, 158, 11, 0.2)', color: isLightMode ? '#b45309' : '#fbbf24', fontSize: '10px', padding: '2px 6px', borderRadius: '4px', fontWeight: 600 }}>WAPE</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
            <span style={{ fontSize: '24px', fontWeight: 700, color: theme.textPrimary }}>
              %{metrics?.solar_wape_pct !== undefined ? metrics.solar_wape_pct : '--'}
            </span>
            <span style={{ color: theme.textSecondary, fontSize: '12px' }}>
              MAE: {metrics?.solar_mae_mw ? `${formatNumber(metrics.solar_mae_mw, 0)} MW` : '--'}
            </span>
          </div>
        </div>

        {/* Wind KPI */}
        <div
          onClick={() => setActiveTab('wind')}
          style={{
            background: activeTab === 'wind' ? (isLightMode ? '#d1fae5' : 'rgba(16, 185, 129, 0.15)') : theme.innerBg,
            border: activeTab === 'wind' ? '1.5px solid #10b981' : `1px solid ${theme.innerBorder}`,
            borderRadius: '10px',
            padding: '14px',
            cursor: 'pointer',
            transition: 'all 0.2s ease'
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ color: theme.textPrimary, fontSize: '13px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Wind style={{ width: '16px', height: '16px', color: '#10b981' }} /> Rüzgar (RES KGÜP) Tahmini
            </span>
            <span style={{ background: 'rgba(16, 185, 129, 0.2)', color: isLightMode ? '#047857' : '#34d399', fontSize: '10px', padding: '2px 6px', borderRadius: '4px', fontWeight: 600 }}>WAPE</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
            <span style={{ fontSize: '24px', fontWeight: 700, color: theme.textPrimary }}>
              %{metrics?.wind_wape_pct !== undefined ? metrics.wind_wape_pct : '--'}
            </span>
            <span style={{ color: theme.textSecondary, fontSize: '12px' }}>
              MAE: {metrics?.wind_mae_mw ? `${formatNumber(metrics.wind_mae_mw, 0)} MW` : '--'}
            </span>
          </div>
        </div>
      </div>

      {/* Chart Component */}
      <div style={{ background: theme.innerBg, border: `1px solid ${theme.innerBorder}`, borderRadius: '10px', padding: '16px', minHeight: '340px' }}>
        {loading ? (
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '300px', color: theme.textSecondary }}>
            Yük ve Üretim Tahmin Verileri Yükleniyor...
          </div>
        ) : (
          <ReactECharts option={getChartOption()} style={{ height: '320px', width: '100%' }} />
        )}
      </div>

      {/* Toggle Table Button */}
      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
        <button
          onClick={() => setShowTable(!showTable)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            background: theme.innerBg,
            color: theme.textPrimary,
            border: `1px solid ${theme.innerBorder}`,
            padding: '6px 14px',
            borderRadius: '6px',
            cursor: 'pointer',
            fontSize: '12px',
            fontWeight: 500
          }}
        >
          <TableIcon style={{ width: '14px', height: '14px' }} />
          {showTable ? 'Tabloyu Gizle' : 'Saatlik Detay Tablosunu Göster'}
        </button>
      </div>

      {/* Data Table */}
      {showTable && (
        <div style={{ overflowX: 'auto', background: theme.innerBg, border: `1px solid ${theme.innerBorder}`, borderRadius: '8px', maxHeight: '300px' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', color: theme.textPrimary, fontSize: '12px', textAlign: 'left' }}>
            <thead>
              <tr style={{ background: theme.tableHeaderBg, borderBottom: `1px solid ${theme.innerBorder}` }}>
                <th style={{ padding: '8px 12px', color: theme.textPrimary }}>Zaman</th>
                <th style={{ padding: '8px 12px', color: isLightMode ? '#4f46e5' : '#818cf8' }}>Yapay Zeka Yük (MW)</th>
                <th style={{ padding: '8px 12px', color: isLightMode ? '#0284c7' : '#38bdf8' }}>EPİAŞ Yük Tahmini (MW)</th>
                <th style={{ padding: '8px 12px', color: isLightMode ? '#d97706' : '#fbbf24' }}>Yapay Zeka Güneş (MW)</th>
                <th style={{ padding: '8px 12px', color: isLightMode ? '#b45309' : '#f59e0b' }}>EPİAŞ Güneş KGÜP (MW)</th>
                <th style={{ padding: '8px 12px', color: isLightMode ? '#059669' : '#34d399' }}>Yapay Zeka Rüzgar (MW)</th>
                <th style={{ padding: '8px 12px', color: isLightMode ? '#047857' : '#10b981' }}>EPİAŞ Rüzgar KGÜP (MW)</th>
              </tr>
            </thead>
            <tbody>
              {seriesData.map((row, i) => (
                <tr key={i} style={{ borderBottom: `1px solid ${theme.tableBorder}` }}>
                  <td style={{ padding: '8px 12px' }}>{row.timestamp}</td>
                  <td style={{ padding: '8px 12px', color: isLightMode ? '#4f46e5' : '#818cf8', fontWeight: 500 }}>{row.pred_load_mw ? formatNumber(row.pred_load_mw, 0) : '-'}</td>
                  <td style={{ padding: '8px 12px', color: isLightMode ? '#0284c7' : '#38bdf8' }}>{row.actual_load_mw ? formatNumber(row.actual_load_mw, 0) : '-'}</td>
                  <td style={{ padding: '8px 12px', color: isLightMode ? '#d97706' : '#fbbf24', fontWeight: 500 }}>{row.pred_solar_mw ? formatNumber(row.pred_solar_mw, 0) : '-'}</td>
                  <td style={{ padding: '8px 12px', color: isLightMode ? '#b45309' : '#f59e0b' }}>{row.actual_solar_mw ? formatNumber(row.actual_solar_mw, 0) : '-'}</td>
                  <td style={{ padding: '8px 12px', color: isLightMode ? '#059669' : '#34d399', fontWeight: 500 }}>{row.pred_wind_mw ? formatNumber(row.pred_wind_mw, 0) : '-'}</td>
                  <td style={{ padding: '8px 12px', color: isLightMode ? '#047857' : '#10b981' }}>{row.actual_wind_mw ? formatNumber(row.actual_wind_mw, 0) : '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

    </div>
  );
};
