import React, { useState, useEffect } from 'react';
import { BarChart2, History } from 'lucide-react';
import { formatNumber } from '../../utils/formatters';

interface HistoricalPerformanceSectionProps {
  selectedRange?: string;
  currencyMode?: 'TRY' | 'USD';
}

export const HistoricalPerformanceSection: React.FC<HistoricalPerformanceSectionProps> = ({ selectedRange, currencyMode = 'USD' }) => {
  const [range, setRange] = useState<string>(selectedRange || '1d');
  const [viewType, setViewType] = useState<'cards' | 'table'>('cards');
  const [isLightMode, setIsLightMode] = useState(() => typeof window !== 'undefined' ? localStorage.getItem('etkb_theme') === 'light' : false);
  
  useEffect(() => {
    const observer = new MutationObserver(() => {
      setIsLightMode(document.documentElement.getAttribute('data-theme') === 'light');
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (selectedRange) {
      setRange(selectedRange);
    }
  }, [selectedRange]);
  
  const [perfData, setPerfData] = useState<{
    wape: string;
    wapeUsd: string;
    mape: string;
    mapeUsd: string;
    mae: string;
    maeUsd: string;
    avgPredicted: string;
    avgActual: string;
    avgPredictedUsd: string;
    avgActualUsd: string;
    totalHours: number;
  }>({
    wape: '16.88',
    wapeUsd: '16.92',
    mape: '18.42',
    mapeUsd: '18.51',
    mae: '371.35',
    maeUsd: '11.20',
    avgPredicted: '2169.32',
    avgActual: '2199.63',
    avgPredictedUsd: '65.44',
    avgActualUsd: '66.35',
    totalHours: 8688
  });

  useEffect(() => {
    let mounted = true;
    const fetchPerf = async () => {
      try {
        const res = await fetch(`/api/db-data?date=${range}&type=performance`);
        if (!res.ok) return;
        const data = await res.json();
        if (mounted && Array.isArray(data) && data.length > 0) {
          const item = data[0];
          setPerfData({
            wape: item.wape || '16.88',
            wapeUsd: item.wape_usd || '16.92',
            mape: item.mape || '18.42',
            mapeUsd: item.mape_usd || '18.51',
            mae: item.mae || '371.35',
            maeUsd: item.mae_usd || '11.20',
            avgPredicted: item.avg_predicted || '2169.32',
            avgActual: item.avg_actual || '2199.63',
            avgPredictedUsd: item.avg_predicted_usd || '65.44',
            avgActualUsd: item.avg_actual_usd || '66.35',
            totalHours: item.total_hours || 8688
          });
        }
      } catch (err) {
        console.error('Performance fetch error:', err);
      }
    };

    fetchPerf();
    return () => { mounted = false; };
  }, [range]);

  const ranges: { value: string, label: string }[] = [
    { value: '1d', label: '1 Gün' },
    { value: '7d', label: '7 Gün' },
    { value: '1m', label: '1 Ay' },
    { value: '3m', label: '3 Ay' },
    { value: '6m', label: '6 Ay' },
    { value: '1y', label: '1 Yıl' },
    { value: '2y', label: '2 Yıl' }
  ];

  const symbol = currencyMode === 'USD' ? '$' : '₺';

  const wapeVal = currencyMode === 'USD' ? perfData.wapeUsd : perfData.wape;
  const accuracyVal = (100 - parseFloat(wapeVal || '0')).toFixed(2);
  const maeVal = currencyMode === 'USD' ? perfData.maeUsd : perfData.mae;
  const avgPredVal = currencyMode === 'USD' ? perfData.avgPredictedUsd : perfData.avgPredicted;
  const avgActVal = currencyMode === 'USD' ? perfData.avgActualUsd : perfData.avgActual;

  return (
    <section className="glass-panel" style={{ padding: '24px', marginTop: '20px' }}>
      
      {/* Header and Controls */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px', marginBottom: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ padding: '8px', borderRadius: '8px', background: 'rgba(56, 189, 248, 0.2)', color: '#38bdf8' }}>
            <History size={22} />
          </div>
          <div>
            <h2 style={{ fontSize: '1.2rem', fontWeight: 700, color: isLightMode ? '#0f172a' : '#fff', margin: 0 }}>
              Geçmiş Performans Analizi
            </h2>
            <p style={{ fontSize: '0.85rem', color: isLightMode ? '#475569' : '#94a3b8', margin: '4px 0 0 0' }}>
              Son {perfData.totalHours} saatlik Yapay Zeka model tahminlerinin gerçekleşen fiyatlarla karşılaştırmalı hata analizi
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          {/* Range Selector */}
          <div style={{ display: 'flex', background: 'rgba(15, 23, 42, 0.6)', padding: '4px', borderRadius: '8px', border: '1px solid rgba(255, 255, 255, 0.05)' }}>
            {ranges.map((r) => (
              <button
                key={r.value}
                onClick={() => setRange(r.value)}
                style={{
                  background: range === r.value ? '#38bdf8' : 'transparent',
                  color: range === r.value ? '#0f172a' : '#94a3b8',
                  border: 'none',
                  padding: '6px 12px',
                  borderRadius: '6px',
                  fontSize: '0.8rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  transition: 'all 0.2s'
                }}
              >
                {r.label}
              </button>
            ))}
          </div>

          {/* View Toggle */}
          <div style={{ display: 'flex', background: 'rgba(15, 23, 42, 0.6)', padding: '4px', borderRadius: '8px', border: '1px solid rgba(255, 255, 255, 0.05)' }}>
            <button
              onClick={() => setViewType('cards')}
              style={{
                background: viewType === 'cards' ? (isLightMode ? 'rgba(0,0,0,0.1)' : 'rgba(255,255,255,0.1)') : 'transparent',
                color: viewType === 'cards' ? (isLightMode ? '#0f172a' : '#fff') : '#64748b',
                border: 'none',
                padding: '6px 12px',
                borderRadius: '6px',
                fontSize: '0.8rem',
                fontWeight: 600,
                cursor: 'pointer'
              }}
            >
              Kartlar
            </button>
            <button
              onClick={() => setViewType('table')}
              style={{
                background: viewType === 'table' ? (isLightMode ? 'rgba(0,0,0,0.1)' : 'rgba(255,255,255,0.1)') : 'transparent',
                color: viewType === 'table' ? (isLightMode ? '#0f172a' : '#fff') : '#64748b',
                border: 'none',
                padding: '6px 12px',
                borderRadius: '6px',
                fontSize: '0.8rem',
                fontWeight: 600,
                cursor: 'pointer'
              }}
            >
              Tablo
            </button>
          </div>
        </div>
      </div>

      {/* Content Area */}
      <div className={viewType === 'cards' ? '' : 'hide-on-screen'} style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px', marginBottom: '16px' }}>
        
        {/* LightGBM Active Primary Model */}
        <div style={{ background: 'rgba(15, 23, 42, 0.6)', border: '1px solid rgba(255, 255, 255, 0.08)', borderRadius: '12px', padding: '18px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
            <h3 style={{ color: '#f43f5e', fontSize: '1rem', margin: 0, display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 700 }}>
              <BarChart2 size={20} /> Yapay Zeka Fiyat Tahmin Modeli
            </h3>
          </div>
          
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '12px' }}>
            <div style={{ background: 'rgba(0,0,0,0.3)', padding: '10px', borderRadius: '8px', textAlign: 'center' }}>
                <span style={{ fontSize: '0.8rem', color: '#94a3b8', display: 'block', marginBottom: '4px' }}>Model Doğruluğu (100 - WAPE)</span>
                <strong style={{ color: '#10b981', fontSize: '1.2rem', fontFamily: 'Outfit' }}>%{accuracyVal}</strong>
            </div>
            <div style={{ background: 'rgba(0,0,0,0.3)', padding: '10px', borderRadius: '8px', textAlign: 'center' }}>
              <span style={{ color: '#94a3b8', fontSize: '0.75rem', display: 'block', marginBottom: '2px' }}>Ortalama Mutlak Hata (MAE)</span>
              <strong style={{ color: '#38bdf8', fontSize: '1.2rem', fontFamily: 'Outfit' }}>{maeVal} {symbol}</strong>
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px', paddingTop: '8px', borderTop: '1px solid rgba(255,255,255,0.06)' }}>
            <span style={{ color: '#94a3b8', fontSize: '0.85rem' }}>Ortalama Yapay Zeka Tahmini</span>
            <strong style={{ color: '#f43f5e', fontSize: '0.95rem', fontFamily: 'JetBrains Mono' }}>{formatNumber(Number(avgPredVal), 2)} {symbol}</strong>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: '#94a3b8', fontSize: '0.85rem' }}>Ortalama Gerçekleşen PTF</span>
            <strong style={{ color: '#38bdf8', fontSize: '0.95rem', fontFamily: 'JetBrains Mono' }}>{formatNumber(Number(avgActVal), 2)} {symbol}</strong>
          </div>
        </div>

      </div>

      <div className={`${viewType === 'table' ? '' : 'hide-on-screen'} export-expandable-table`} style={{ overflowX: 'auto', maxHeight: '400px' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem', textAlign: 'left' }}>
            <thead>
              <tr style={{ background: '#0f172a', color: '#94a3b8', position: 'sticky', top: 0, zIndex: 10, boxShadow: '0 2px 4px rgba(0,0,0,0.2)' }}>
                <th style={{ padding: '12px', borderBottom: '1px solid rgba(255, 255, 255, 0.1)' }}>Model Adı</th>
                <th style={{ padding: '12px', borderBottom: '1px solid rgba(255, 255, 255, 0.1)' }}>Analiz Süresi (Saat)</th>
                <th style={{ padding: '12px', borderBottom: '1px solid rgba(255, 255, 255, 0.1)' }}>Ortalama Hata Oranı</th>
                <th style={{ padding: '12px', borderBottom: '1px solid rgba(255, 255, 255, 0.1)' }}>MAE (Mutlak Hata)</th>
                <th style={{ padding: '12px', borderBottom: '1px solid rgba(255, 255, 255, 0.1)' }}>Ort. Fiyat Tahmini</th>
                <th style={{ padding: '12px', borderBottom: '1px solid rgba(255, 255, 255, 0.1)' }}>Ort. Gerçek PTF</th>
              </tr>
            </thead>
            <tbody>
              <tr style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.04)', background: 'transparent' }}>
                <td style={{ padding: '12px', color: '#f43f5e', fontWeight: 600 }}>Yapay Zeka Fiyat Tahmin Modeli</td>
                <td style={{ padding: '12px' }}>{formatNumber(Number(avgPredVal))} {symbol}</td>
                <td style={{ padding: '12px', color: '#10b981', fontWeight: 700 }}>%{wapeVal}</td>
                <td style={{ padding: '12px', color: '#38bdf8', fontWeight: 700 }}>{maeVal} {symbol}</td>
                <td style={{ padding: '12px', color: '#fff', fontFamily: 'JetBrains Mono' }}>{formatNumber(Number(avgPredVal), 2)} {symbol}</td>
                <td style={{ padding: '12px', color: '#fff', fontFamily: 'JetBrains Mono' }}>{formatNumber(Number(avgActVal), 2)} {symbol}</td>
              </tr>
            </tbody>
          </table>
        </div>

    </section>
  );
};
