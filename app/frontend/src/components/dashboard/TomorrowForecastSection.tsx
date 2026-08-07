import React, { useMemo, useState, useEffect } from 'react';
import ReactECharts from 'echarts-for-react';
import { Cpu, Zap, Activity, TrendingUp, Layers, BarChart2 } from 'lucide-react';
import { EnergyDataPoint, SeriesConfig, ChartTypeOption } from '../../types/energy';
import { formatCurrency, formatToDDMMYYYY } from '../../utils/formatters';

interface TomorrowForecastSectionProps {
  data: EnergyDataPoint[];
  seriesConfigs: SeriesConfig[];
  toggleSeriesVisibility: (id: string) => void;
  changeSeriesChartType: (id: string, chartType: ChartTypeOption) => void;
  dateSelectorNode?: React.ReactNode;
  currencyMode?: 'TRY' | 'USD';
}

export const TomorrowForecastSection: React.FC<TomorrowForecastSectionProps> = ({
  data,
  seriesConfigs,
  toggleSeriesVisibility,
  changeSeriesChartType,
  dateSelectorNode,
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

  // Compute Tomorrow Averages
  const averages = useMemo(() => {
    if (!data || data.length === 0) return { lgb: 0 };
    let sumL = 0;
    data.forEach((d) => {
      sumL += d.lightgbmForecast;
    });
    const n = data.length;
    return {
      lgb: sumL / n
    };
  }, [data]);

  const targetDateStr = useMemo(() => {
    if (data && data.length > 0 && data[0].date) {
      return formatToDDMMYYYY(data[0].date);
    }
    return 'Gelecek Gün';
  }, [data]);

  const symbolStr = currencyMode === 'USD' ? '$' : '₺';
  const unitStr = currencyMode === 'USD' ? '$/MWh' : '₺/MWh';

  // ECharts Option for PTF Forecast (Tomorrow)
  const chartOption = useMemo(() => {
    if (!data || data.length === 0) return {};

    const gridLineColor = isLightMode ? 'rgba(0, 0, 0, 0.14)' : 'rgba(255, 255, 255, 0.12)';
    const axisLabelColor = isLightMode ? '#475569' : '#94a3b8';

    const xAxisLabels = data.map((d) => d.hour);

    const seriesList: any[] = [];

    // Add AI Forecast Models
    seriesConfigs.forEach((sc) => {
      if (!sc.visible || sc.id === 'ptf') return; // Only show forecast models for tomorrow

      const seriesData = data.map((d) => d[sc.id] as number);

      seriesList.push({
        name: sc.name,
        type: sc.chartType === 'area' ? 'line' : (sc.chartType === 'smooth' ? 'line' : sc.chartType),
        smooth: sc.chartType === 'smooth' || sc.chartType === 'area',
        data: seriesData,
        symbol: 'circle',
        symbolSize: 6,
        showSymbol: false,
        areaStyle: sc.chartType === 'area' ? { opacity: 0.3 } : undefined,
        itemStyle: { color: sc.color },
        lineStyle: { width: 3, color: sc.color, type: 'solid' }
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
          let res = `<div style="font-weight:700;margin-bottom:6px;color:#fbbf24;">🕒 ${targetDateStr} Saat: ${params[0].name}</div>`;
          params.forEach((item: any) => {
            if (item.seriesName.includes('Güven Aralığı')) return;
            const val = typeof item.value === 'number' ? item.value.toLocaleString('tr-TR') : item.value;
            res += `<div style="display:flex;align-items:center;justify-content:space-between;gap:12px;margin:3px 0;">
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
        nameTextStyle: { color: axisLabelColor },
        axisLabel: { color: axisLabelColor, formatter: `{value} ${symbolStr}` },
        splitLine: { lineStyle: { color: gridLineColor } },
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
  }, [data, seriesConfigs, targetDateStr, symbolStr, unitStr, isLightMode]);

  const [perfMetric, setPerfMetric] = React.useState<{ wape: string; accuracy: string }>({
    wape: '--',
    accuracy: '--'
  });

  React.useEffect(() => {
    let mounted = true;
    const fetchPerf = async () => {
      try {
        const res = await fetch('/api/db-data?date=1d&type=performance');
        if (!res.ok) return;
        const pData = await res.json();
        if (mounted && Array.isArray(pData) && pData.length > 0) {
          const wapeStr = pData[0].wape_usd !== undefined ? pData[0].wape_usd : pData[0].wape;
          if (wapeStr !== undefined && wapeStr !== null) {
            const wapeVal = parseFloat(wapeStr);
            const accVal = Math.max(0, 100 - wapeVal).toFixed(2);
            setPerfMetric({
              wape: wapeStr.toString(),
              accuracy: accVal
            });
          }
        }
      } catch (err) {
        console.error('Performance metric fetch error:', err);
      }
    };
    fetchPerf();
    return () => { mounted = false; };
  }, []);

  return (
    <section style={{ marginBottom: '28px' }}>

      {/* Section Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px', marginBottom: '14px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{ padding: '6px', borderRadius: '8px', background: 'rgba(251, 191, 36, 0.2)', color: '#fbbf24' }}>
            <Zap size={20} />
          </div>
          <div>
            <h2 style={{ fontSize: '1.2rem', fontWeight: 700, color: '#fff', margin: 0 }}>
              Gelecek PTF Fiyat Tahminleri ({targetDateStr})
            </h2>
            <p style={{ fontSize: '0.8rem', color: '#94a3b8', margin: 0 }}>
              Üretilen güncel PTF fiyat tahmin eğrileri ({targetDateStr})
            </p>
          </div>
        </div>

        {/* Optional UI Node for Date Selection */}
        {dateSelectorNode && (
          <div>
            {dateSelectorNode}
          </div>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: '20px' }}>

        {/* Sol Menü: Model Seçici */}
        <div className="glass-panel" style={{ padding: '18px', display: 'flex', flexDirection: 'column', gap: '18px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
              <Cpu size={16} color="#fbbf24" />
              <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#fff', margin: 0 }}>Modeller</h3>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {seriesConfigs.filter(s => s.id !== 'ptf').map((s) => (
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
        </div>

        {/* Sağ Taraf: Metrik Kartları + Ana 1 Ağustos Tahmin Grafiği */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>

          {/* Top Cards for Tomorrow (Active Model: LightGBM) */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px' }}>

            {(() => {
              const fcSeries = seriesConfigs?.find(s => s.id === 'lightgbmForecast' || s.isForecast);
              const modelColor = fcSeries?.color || '#e11d48';

              return (
                <div className="glass-panel" style={{ padding: '14px', border: `1px solid ${modelColor}60` }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', color: modelColor, fontSize: '0.75rem', fontWeight: 600 }}>
                    <span>Yapay Zeka Fiyat Tahmini Ortalaması</span>
                    <Cpu size={16} />
                  </div>
                  <div style={{ fontSize: '1.4rem', fontWeight: 800, color: '#fff', margin: '4px 0', fontFamily: 'Outfit' }}>
                    {formatCurrency(averages.lgb, symbolStr)}
                  </div>
                  <div style={{ fontSize: '0.7rem', color: modelColor }}>Aktif Yapay Zeka Modeli</div>
                </div>
              );
            })()}

            <div className="glass-panel" style={{ padding: '14px', border: '1px solid rgba(16, 185, 129, 0.3)' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', color: '#10b981', fontSize: '0.75rem', fontWeight: 600 }}>
                <span>Model Başarı Metriği (Son 24s)</span>
                <TrendingUp size={16} />
              </div>
              <div style={{ fontSize: '1.4rem', fontWeight: 800, color: '#10b981', margin: '4px 0', fontFamily: 'Outfit' }}>
                %{perfMetric.accuracy} <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Doğruluk</span>
              </div>
              <div style={{ fontSize: '0.7rem', color: '#94a3b8' }}>Ortalama Hata Oranı %{perfMetric.wape}</div>
            </div>

          </div>

          {/* Main Chart 1: Tomorrow PTF Forecast */}
          <div className="glass-panel" style={{ padding: '18px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
              <h3 style={{ fontSize: '1rem', fontWeight: 700, color: '#fff', margin: 0 }}>
                {targetDateStr} 24 Saatlik PTF Gelecek Fiyat Tahmin Grafiği
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
