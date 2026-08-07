import React, { useMemo, useState, useEffect } from 'react';
import ReactECharts from 'echarts-for-react';
import { CheckCircle2, Layers, TrendingUp, Activity, BarChart2 } from 'lucide-react';
import { DashboardMetrics, EnergyDataPoint, SeriesConfig, ChartTypeOption } from '../../types/energy';
import { formatCurrency, formatToDDMMYYYY } from '../../utils/formatters';

interface TodayBenchmarkSectionProps {
  data: EnergyDataPoint[];
  seriesConfigs: SeriesConfig[];
  toggleSeriesVisibility: (id: string) => void;
  changeSeriesChartType: (id: string, chartType: ChartTypeOption) => void;
  metrics: DashboardMetrics;
  currencyMode?: 'TRY' | 'USD';
}

export const TodayBenchmarkSection: React.FC<TodayBenchmarkSectionProps> = ({
  data,
  seriesConfigs,
  toggleSeriesVisibility,
  changeSeriesChartType,
  metrics: _metrics,
  currencyMode = 'TRY'
}) => {
  const [isLightMode, setIsLightMode] = useState(() => typeof window !== 'undefined' ? localStorage.getItem('etkb_theme') === 'light' : false);
  useEffect(() => {
    const observer = new MutationObserver(() => {
      setIsLightMode(document.documentElement.getAttribute('data-theme') === 'light');
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    return () => observer.disconnect();
  }, []);
  const computedMetrics = useMemo(() => {
    return _metrics;
  }, [_metrics]);

  const displayMetrics = computedMetrics;

  const symbolStr = currencyMode === 'USD' ? '$' : '₺';
  const unitStr = currencyMode === 'USD' ? '$/MWh' : '₺/MWh';

  // Chart Option for Morning Forecast vs Realized EPİAŞ PTF
  const chartOption = useMemo(() => {
    if (!data || data.length === 0) return {};

    const gridLineColor = isLightMode ? 'rgba(0, 0, 0, 0.14)' : 'rgba(255, 255, 255, 0.12)';
    const axisLabelColor = isLightMode ? '#475569' : '#94a3b8';

    const isMultiDay = data.length > 24;
    const xAxisLabels = data.map((d) => isMultiDay ? (d.timestamp || `${d.date} ${d.hour}`) : d.hour);
    const seriesList: any[] = [];

    // Add active series (including PTF Realized)
    seriesConfigs.forEach((sc) => {
      if (!sc.visible) return;

      const seriesData = data.map((d: any) => {
        if (sc.id === 'lightgbmForecast') {
          return d.lightgbmForecast !== undefined ? d.lightgbmForecast : (d.lightgbm_forecast !== undefined ? d.lightgbm_forecast : d.epnetForecast);
        }
        return d[sc.id] !== undefined ? d[sc.id] : 0;
      });
      const isRealized = sc.id === 'ptf';

      seriesList.push({
        name: sc.name,
        type: sc.chartType === 'area' ? 'line' : (sc.chartType === 'smooth' ? 'line' : sc.chartType),
        smooth: sc.chartType === 'smooth' || sc.chartType === 'area',
        data: seriesData,
        symbol: isRealized ? 'rect' : 'circle',
        symbolSize: isRealized ? 8 : 5,
        areaStyle: sc.chartType === 'area' ? { opacity: 0.3 } : undefined,
        itemStyle: { color: sc.color },
        lineStyle: {
          width: isRealized ? 3.5 : 2.5,
          color: sc.color,
          type: 'solid'
        }
      });
    });

    return {
      backgroundColor: 'transparent',
      animationDuration: 800,
      tooltip: {
        trigger: 'axis',
        backgroundColor: isLightMode ? 'rgba(255, 255, 255, 0.95)' : 'rgba(15, 23, 42, 0.95)',
        borderColor: isLightMode ? 'rgba(0, 0, 0, 0.1)' : 'rgba(56, 189, 248, 0.3)',
        textStyle: { color: isLightMode ? '#0f172a' : '#fff', fontSize: 12 },
        formatter: (params: any[]) => {
          if (!params || params.length === 0) return '';
          let res = `<div style="font-weight:700;margin-bottom:6px;color:${isLightMode ? '#0369a1' : '#38bdf8'};">🕒 Saat: ${params[0].name}</div>`;
          params.forEach((item: any) => {
            const val = typeof item.value === 'number' ? item.value.toLocaleString('tr-TR') : item.value;
            res += `<div style="display:flex;align-items:center;justify-content:space-between;gap:12px;margin:3px 0;color:${isLightMode ? '#0f172a' : '#f8fafc'};">
              <span>${item.marker} ${item.seriesName}:</span>
              <strong style="font-family:JetBrains Mono;">${val} ${unitStr}</strong>
            </div>`;
          });
          return res;
        }
      },
      legend: {
        top: '2%',
        right: '2%',
        textStyle: { color: axisLabelColor, fontSize: 11 }
      },
      grid: { top: '15%', left: '3%', right: '3%', bottom: '16%', containLabel: true },
      xAxis: {
        type: 'category',
        data: xAxisLabels,
        boundaryGap: seriesConfigs.some(s => s.visible && s.chartType === 'bar') ? true : false,
        axisLine: { lineStyle: { color: isLightMode ? 'rgba(0, 0, 0, 0.2)' : 'rgba(255, 255, 255, 0.15)' } },
        axisLabel: { color: axisLabelColor, fontSize: 11 },
        splitLine: { show: true, lineStyle: { color: gridLineColor } }
      },
      yAxis: {
        type: 'value',
        name: unitStr,
        nameTextStyle: { color: axisLabelColor, padding: [0, 0, 0, 10] },
        axisLabel: { color: axisLabelColor },
        splitLine: { show: true, lineStyle: { color: gridLineColor } },
        scale: true
      },
      dataZoom: [{ type: 'inside' }, {
        type: 'slider', bottom: '3%', height: 18,
        borderColor: 'rgba(148, 163, 184, 0.24)',
        fillerColor: 'rgba(56, 189, 248, 0.18)',
        handleStyle: { color: '#38bdf8' },
        textStyle: { color: '#94a3b8' }
      }],
      series: seriesList
    };
  }, [data, seriesConfigs, symbolStr, unitStr, isLightMode]);

  const currentDateStr = useMemo(() => {
    if (data && data.length > 0 && data[0].date) {
      return formatToDDMMYYYY(data[0].date);
    }
    return 'Seçilen Tarih';
  }, [data]);

  return (
    <section style={{ marginBottom: '28px' }}>
      <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: '20px' }}>

        {/* Sol Menü: Model Seçimi & Pingleme Switcher */}
        <div className="glass-panel" style={{ padding: '18px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Layers size={16} color="#38bdf8" />
            <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#fff', margin: 0 }}>Karşılaştırılan Veriler</h3>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {seriesConfigs.map((s) => (
              <div
                key={s.id}
                style={{
                  padding: '12px',
                  borderRadius: '8px',
                  background: s.visible ? 'rgba(255, 255, 255, 0.05)' : 'rgba(255, 255, 255, 0.01)',
                  border: `1px solid ${s.visible ? s.color + '50' : 'rgba(255, 255, 255, 0.06)'}`,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '12px'
                }}
              >
                {/* Top row: Name and Toggle */}
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ width: '10px', height: '10px', borderRadius: '2px', backgroundColor: s.color, marginTop: '2px' }} />
                    <span style={{ fontSize: '0.85rem', fontWeight: 600, color: s.visible ? '#fff' : '#64748b', lineHeight: '1.2' }}>{s.name}</span>
                  </div>
                  <button
                    onClick={() => toggleSeriesVisibility(s.id)}
                    style={{
                      background: s.visible ? 'rgba(56, 189, 248, 0.1)' : 'transparent',
                      border: `1px solid ${s.visible ? '#38bdf8' : 'rgba(255,255,255,0.1)'}`,
                      color: s.visible ? '#38bdf8' : '#64748b',
                      padding: '4px 10px',
                      borderRadius: '6px',
                      fontSize: '0.7rem',
                      fontWeight: 600,
                      cursor: 'pointer',
                      transition: 'all 0.2s',
                      minWidth: '60px'
                    }}
                  >
                    {s.visible ? 'Açık' : 'Kapalı'}
                  </button>
                </div>

                {/* Bottom row: Chart style selector */}
                {s.visible && (
                  <div style={{ display: 'flex', justifyContent: 'center' }}>
                    <div style={{ display: 'flex', background: 'rgba(0,0,0,0.3)', borderRadius: '6px', padding: '4px', border: '1px solid rgba(255,255,255,0.05)', gap: '4px' }}>
                      {[
                        { val: 'line', icon: <TrendingUp size={14} /> },
                        { val: 'smooth', icon: <Activity size={14} /> },
                        { val: 'area', icon: <Layers size={14} /> },
                        { val: 'bar', icon: <BarChart2 size={14} /> }
                      ].map((type) => (
                        <div
                          key={type.val}
                          onClick={() => changeSeriesChartType(s.id, type.val as ChartTypeOption)}
                          style={{
                            padding: '6px 12px',
                            borderRadius: '4px',
                            cursor: 'pointer',
                            background: s.chartType === type.val ? 'rgba(56, 189, 248, 0.2)' : 'transparent',
                            color: s.chartType === type.val ? '#38bdf8' : '#64748b',
                            transition: 'all 0.2s ease',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center'
                          }}
                          title={type.val.toUpperCase()}
                        >
                          {type.icon}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Sağ Taraf: Metrik Kartları + Kıyaslama Grafiği */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>

          {/* Top Cards for Realized vs Forecast Models */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px' }}>

            {/* PTF Card */}
            <div className="glass-panel" style={{ padding: '16px', borderTop: '3px solid #38bdf8' }}>
              <div style={{ fontSize: '0.9rem', color: '#38bdf8', fontWeight: 700, marginBottom: '12px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span>Ortalama PTF</span>
              </div>
              <div style={{ fontSize: '1.4rem', fontWeight: 800, color: '#fff', margin: '8px 0', fontFamily: 'Outfit' }}>
                {formatCurrency(displayMetrics.avgPtf, symbolStr)}
              </div>
              <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>EPİAŞ Kesinleşen Fiyatların Ortalaması</div>
            </div>

            {/* AI Model Card */}
            {(() => {
              const forecastSeries = seriesConfigs.find(s => s.id === 'lightgbmForecast' || s.isForecast);
              const modelName = forecastSeries?.name || 'Yapay Zeka Fiyat Tahmini';
              const modelColor = forecastSeries?.color || '#e11d48';

              return (
                <div className="glass-panel" style={{ padding: '16px', borderTop: `3px solid ${modelColor}` }}>
                  <div style={{ fontSize: '0.9rem', color: modelColor, fontWeight: 700, marginBottom: '12px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <span>{modelName}</span>
                    <CheckCircle2 size={16} />
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', paddingBottom: '8px', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
                    <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Ortalama Hata Oranı (WAPE):</span>
                    <strong style={{ fontSize: '0.9rem', color: '#fff' }}>%{displayMetrics.wapeLightgbm}</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ fontSize: '0.7rem', color: '#94a3b8' }}>Ortalama Fiyat Tahmini:</span>
                    <strong style={{ fontSize: '0.8rem', color: '#fff' }}>{formatCurrency(displayMetrics.avgLightgbmForecast, symbolStr)}</strong>
                  </div>
                </div>
              );
            })()}

          </div>

          {/* Main Chart 2: Forecast vs Realized */}
          <div className="glass-panel" style={{ padding: '18px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
              <h3 style={{ fontSize: '1rem', fontWeight: 700, color: '#fff', margin: 0 }}>
                {currentDateStr} Sabah Tahmini vs EPİAŞ Gerçekleşen PTF Kıyaslama Grafiği
              </h3>
            </div>

            <div style={{ width: '100%', height: '340px' }}>
              <ReactECharts option={chartOption} style={{ height: '100%', width: '100%' }} notMerge={true} />
            </div>
          </div>

        </div>

      </div>

    </section>
  );
};
