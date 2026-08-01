import React, { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import { CheckCircle2, Layers, TrendingUp, Activity, BarChart2 } from 'lucide-react';
import { DashboardMetrics, EnergyDataPoint, IntersectionPoint, SeriesConfig, ChartTypeOption } from '../../types/energy';
import { formatCurrency } from '../../utils/formatters';

interface TodayBenchmarkSectionProps {
  data: EnergyDataPoint[];
  seriesConfigs: SeriesConfig[];
  toggleSeriesVisibility: (id: string) => void;
  changeSeriesChartType: (id: string, chartType: ChartTypeOption) => void;
  intersections: IntersectionPoint[];
  showIntersections: boolean;
  setShowIntersections: (show: boolean) => void;
  metrics: DashboardMetrics;
  onIntersectionSelect?: (intersection: IntersectionPoint) => void;
  currencyMode?: 'TRY' | 'USD';
}

export const TodayBenchmarkSection: React.FC<TodayBenchmarkSectionProps> = ({
  data,
  seriesConfigs,
  toggleSeriesVisibility,
  changeSeriesChartType,
  intersections,
  showIntersections,
  setShowIntersections,
  metrics: _metrics,
  onIntersectionSelect,
  currencyMode = 'TRY'
}) => {
  const computedMetrics = useMemo(() => {
    if (!data || data.length === 0) {
      return {
        avgPtf: 0,
        mapeLightgbm: '0.00',
        wapeLightgbm: '0.00',
        avgLightgbmForecast: 0,
        bestModel: 'LightGBM'
      };
    }
    let sumPtf = 0;
    let sumLgb = 0;
    let sumAbsDiff = 0;
    let sumRelErr = 0;
    let countPtf = 0;

    data.forEach((d) => {
      const ptfVal = d.ptf || 0;
      const lgbVal = d.lightgbmForecast || d.epnetForecast || 0;
      sumLgb += lgbVal;

      if (ptfVal > 0) {
        sumPtf += ptfVal;
        countPtf += 1;
        const absDiff = Math.abs(lgbVal - ptfVal);
        sumAbsDiff += absDiff;
        sumRelErr += absDiff / ptfVal;
      }
    });

    const avgPtf = countPtf > 0 ? sumPtf / countPtf : (sumLgb / data.length);
    const avgLightgbmForecast = sumLgb / data.length;
    const mape = countPtf > 0 ? (sumRelErr / countPtf) * 100 : 0;
    const wape = sumPtf > 0 ? (sumAbsDiff / sumPtf) * 100 : 0;

    return {
      avgPtf,
      mapeLightgbm: mape.toFixed(2),
      wapeLightgbm: wape.toFixed(2),
      avgLightgbmForecast,
      bestModel: 'LightGBM'
    };
  }, [data]);

  const displayMetrics = computedMetrics;

  const symbolStr = currencyMode === 'USD' ? '$' : '₺';
  const unitStr = currencyMode === 'USD' ? '$/MWh' : '₺/MWh';

  // Chart Option for Morning Forecast vs Realized EPİAŞ PTF
  const chartOption = useMemo(() => {
    if (!data || data.length === 0) return {};

    const isMultiDay = data.length > 24;
    const xAxisLabels = data.map((d) => isMultiDay ? (d.timestamp || `${d.date} ${d.hour}`) : d.hour);
    const seriesList: any[] = [];

    // Add active series (including PTF Realized)
    seriesConfigs.forEach((sc) => {
      if (!sc.visible) return;

      const seriesData = data.map((d) => d[sc.id] as number);
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
          type: isRealized ? 'solid' : 'dashed'
        }
      });
    });

    // Add Intersection Pings Scatter if enabled
    if (showIntersections && intersections.length > 0) {
      const pingData = intersections.map((it) => ({
        name: `Kesişim: ${it.series1Name} & ${it.series2Name}`,
        value: [it.xIndex, it.exactValue],
        intersectionObj: it
      }));

      seriesList.push({
        name: 'Kesişim Pingleme',
        type: 'effectScatter',
        coordinateSystem: 'cartesian2d',
        data: pingData,
        symbolSize: 14,
        rippleEffect: { brushType: 'stroke', scale: 4.5, period: 2 },
        itemStyle: { color: '#f43f5e', shadowBlur: 15, shadowColor: '#f43f5e' },
        zlevel: 10
      });
    }

    return {
      backgroundColor: 'transparent',
      animationDuration: 800,
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(15, 23, 42, 0.95)',
        borderColor: 'rgba(56, 189, 248, 0.3)',
        textStyle: { color: '#fff', fontSize: 12 },
        formatter: (params: any[]) => {
          if (!params || params.length === 0) return '';
          let res = `<div style="font-weight:700;margin-bottom:6px;color:#38bdf8;">🕒 Saat: ${params[0].name}</div>`;
          params.forEach((item: any) => {
            if (item.seriesName === 'Kesişim Pingleme') return;
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
        textStyle: { color: '#94a3b8', fontSize: 11 }
      },
      grid: { top: '15%', left: '3%', right: '3%', bottom: '10%', containLabel: true },
      xAxis: {
        type: 'category',
        data: xAxisLabels,
        axisLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.15)' } },
        axisLabel: { color: '#94a3b8', fontSize: 11 }
      },
      yAxis: {
        type: 'value',
        name: unitStr,
        nameTextStyle: { color: '#94a3b8' },
        axisLabel: { color: '#94a3b8', formatter: `{value} ${symbolStr}` },
        splitLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.06)' } },
        scale: true
      },
      series: seriesList
    };
  }, [data, seriesConfigs, intersections, showIntersections, symbolStr, unitStr]);

  const onChartClick = (params: any) => {
    if (params.seriesName === 'Kesişim Pingleme' && params.data?.intersectionObj && onIntersectionSelect) {
      onIntersectionSelect(params.data.intersectionObj);
    }
  };

  const currentDateStr = useMemo(() => {
    if (data && data.length > 0 && data[0].date) {
      return data[0].date;
    }
    return 'Seçilen Tarih';
  }, [data]);

  return (
    <section style={{ marginBottom: '28px' }}>
      
      {/* Section Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '14px' }}>
        <div style={{ padding: '6px', borderRadius: '8px', background: 'rgba(56, 189, 248, 0.2)', color: '#38bdf8' }}>
          <CheckCircle2 size={20} />
        </div>
        <div>
          <h2 style={{ fontSize: '1.2rem', fontWeight: 700, color: '#fff', margin: 0 }}>
            BÖLÜM 2: {currentDateStr} Model Tahminimiz vs EPİAŞ Gerçekleşen PTF Kıyaslaması
          </h2>
          <p style={{ fontSize: '0.8rem', color: '#94a3b8', margin: 0 }}>
            EPİAŞ ilan bülteni geldikten sonra model tahmini ile gerçek fiyatların karşılaştırılması ve hata payları ({currentDateStr})
          </p>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: '20px' }}>
        
        {/* Sol Menü: Model Seçimi & Pingleme Switcher */}
        <div className="glass-panel" style={{ padding: '18px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Layers size={16} color="#38bdf8" />
            <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#fff', margin: 0 }}>Karşılaştırılacak Seriler</h3>
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

          {/* Kesişim Noktaları Pingleme Toggle Switcher */}
          <div style={{ borderTop: '1px solid rgba(255, 255, 255, 0.08)', paddingTop: '14px' }}>
            <label style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              fontSize: '0.8rem',
              color: '#cbd5e1',
              cursor: 'pointer',
              background: 'rgba(244, 63, 94, 0.08)',
              padding: '10px',
              borderRadius: '8px',
              border: '1px solid rgba(244, 63, 94, 0.2)'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <TrendingUp size={15} color="#f43f5e" />
                <span style={{ fontWeight: 600 }}>Kesişim Pingleme Göster</span>
              </div>
              <input
                type="checkbox"
                checked={showIntersections}
                onChange={(e) => setShowIntersections(e.target.checked)}
                style={{ accentColor: '#f43f5e', width: '16px', height: '16px', cursor: 'pointer' }}
              />
            </label>
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
              <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>EPİAŞ Bülteni Kesinleşti</div>
            </div>

            {/* LightGBM Card */}
            <div className="glass-panel" style={{ padding: '16px', borderTop: '3px solid #c084fc' }}>
              <div style={{ fontSize: '0.9rem', color: '#c084fc', fontWeight: 700, marginBottom: '12px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span>LightGBM</span>
                {displayMetrics.bestModel.includes('LightGBM') && <CheckCircle2 size={16} />}
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>MAPE:</span>
                <strong style={{ fontSize: '0.9rem', color: '#fff' }}>%{displayMetrics.mapeLightgbm}</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', paddingBottom: '8px', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
                <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>WAPE:</span>
                <strong style={{ fontSize: '0.9rem', color: '#fff' }}>%{displayMetrics.wapeLightgbm}</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ fontSize: '0.7rem', color: '#94a3b8' }}>Ort. Tahmin:</span>
                <strong style={{ fontSize: '0.8rem', color: '#c084fc' }}>{formatCurrency(displayMetrics.avgLightgbmForecast, symbolStr)}</strong>
              </div>
            </div>

          </div>

          {/* Main Chart 2: Forecast vs Realized */}
          <div className="glass-panel" style={{ padding: '18px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
              <h3 style={{ fontSize: '1rem', fontWeight: 700, color: '#fff', margin: 0 }}>
                {currentDateStr} Sabah Tahmini vs EPİAŞ Gerçekleşen PTF Kıyaslama Grafiği
              </h3>
              {showIntersections && intersections.length > 0 && (
                <span className="ping-badge">
                  ⚡ {intersections.length} Çapraz Kesişim Pinglemesi Aktif
                </span>
              )}
            </div>

            <div style={{ width: '100%', height: '340px' }}>
              <ReactECharts option={chartOption} style={{ height: '100%', width: '100%' }} onEvents={{ click: onChartClick }} notMerge={true} />
            </div>
          </div>

        </div>

      </div>

    </section>
  );
};
