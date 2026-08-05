import React from 'react';
import { Layers, Eye, EyeOff, BarChart2, TrendingUp, Sliders, Cpu } from 'lucide-react';
import { ChartTypeOption, SeriesConfig } from '../../types/energy';

interface SidebarProps {
  seriesConfigs: SeriesConfig[];
  toggleSeriesVisibility: (id: string) => void;
  updateSeriesType: (id: string, chartType: ChartTypeOption) => void;
  showIntersections: boolean;
  setShowIntersections: (show: boolean) => void;
  showConfidenceInterval: boolean;
  setShowConfidenceInterval: (show: boolean) => void;
  hybridWeights: { epnet: number; lgb: number };
  setHybridWeights: React.Dispatch<React.SetStateAction<{ epnet: number; lgb: number }>>;
}

export const Sidebar: React.FC<SidebarProps> = ({
  seriesConfigs,
  toggleSeriesVisibility,
  updateSeriesType,
  showIntersections,
  setShowIntersections,
  showConfidenceInterval,
  setShowConfidenceInterval,
  hybridWeights,
  setHybridWeights
}) => {
  return (
    <aside className="glass-panel" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '22px' }}>
      
      {/* Models & PTF Series Controls */}
      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
          <Cpu size={18} color="#38bdf8" />
          <h3 style={{ fontSize: '1rem', fontWeight: 600, color: '#fff' }}>PTF Tahmin Modelleri</h3>
        </div>
        <p style={{ fontSize: '0.78rem', color: '#94a3b8', marginBottom: '14px', lineHeight: '1.4' }}>
          Grafikte kıyaslamak istediğiniz PTF tahmin modellerini seçin ve grafik türlerini özelleştirin:
        </p>

        {/* Series Controls */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {seriesConfigs.map((s) => (
            <div
              key={s.id}
              style={{
                background: s.visible ? 'rgba(255, 255, 255, 0.04)' : 'rgba(255, 255, 255, 0.01)',
                border: `1px solid ${s.visible ? s.color + '40' : 'rgba(255, 255, 255, 0.06)'}`,
                borderRadius: '10px',
                padding: '10px 12px',
                transition: 'all 0.2s ease'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{
                    width: '12px',
                    height: '12px',
                    borderRadius: '3px',
                    backgroundColor: s.color,
                    boxShadow: s.visible ? `0 0 8px ${s.color}` : 'none'
                  }} />
                  <span style={{ fontSize: '0.85rem', fontWeight: 600, color: s.visible ? '#fff' : '#64748b' }}>
                    {s.name}
                  </span>
                </div>

                <button
                  onClick={() => toggleSeriesVisibility(s.id)}
                  style={{
                    background: 'transparent',
                    border: 'none',
                    color: s.visible ? '#38bdf8' : '#64748b',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center'
                  }}
                  title={s.visible ? 'Gizle' : 'Göster'}
                >
                  {s.visible ? <Eye size={16} /> : <EyeOff size={16} />}
                </button>
              </div>

              {/* Chart Type Selector for this series */}
              {s.visible && (
                <div style={{ display: 'flex', gap: '4px', marginTop: '6px' }}>
                  {(['line', 'smooth', 'area', 'bar'] as ChartTypeOption[]).map((type) => (
                    <button
                      key={type}
                      onClick={() => updateSeriesType(s.id, type)}
                      style={{
                        flex: 1,
                        padding: '3px 0',
                        fontSize: '0.7rem',
                        fontWeight: 500,
                        borderRadius: '4px',
                        border: 'none',
                        cursor: 'pointer',
                        background: s.chartType === type ? s.color : 'rgba(255, 255, 255, 0.06)',
                        color: s.chartType === type ? '#070a12' : '#94a3b8'
                      }}
                    >
                      {type === 'line' ? 'Çizgi' : type === 'smooth' ? 'Kavis' : type === 'area' ? 'Alan' : 'Çubuk'}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Hybrid Model Weight Adjuster */}
      <div style={{ borderTop: '1px solid rgba(255, 255, 255, 0.08)', paddingTop: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
          <Sliders size={16} color="#fbbf24" />
          <h4 style={{ fontSize: '0.88rem', fontWeight: 600, color: '#fff' }}>Hibrit Model Ağırlığı</h4>
        </div>
        
        <div style={{ background: 'rgba(255, 255, 255, 0.03)', padding: '10px 12px', borderRadius: '8px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: '#94a3b8', marginBottom: '6px' }}>
            <span>EPNet: <strong>%{hybridWeights.epnet}</strong></span>
            <span>LightGBM: <strong>%{hybridWeights.lgb}</strong></span>
          </div>
          <input
            type="range"
            min="0"
            max="100"
            value={hybridWeights.epnet}
            onChange={(e) => {
              const epVal = Number(e.target.value);
              setHybridWeights({ epnet: epVal, lgb: 100 - epVal });
            }}
            style={{ width: '100%', accentColor: '#fbbf24', cursor: 'pointer' }}
          />
        </div>
      </div>

      {/* Advanced Features & Intersection Ping Controls */}
      <div style={{ borderTop: '1px solid rgba(255, 255, 255, 0.08)', paddingTop: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
          <Layers size={18} color="#10b981" />
          <h3 style={{ fontSize: '0.95rem', fontWeight: 600, color: '#fff' }}>Grafik & Kesişim Araçları</h3>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          
          {/* Intersection Ping Toggle */}
          <label style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            fontSize: '0.83rem',
            color: '#cbd5e1',
            cursor: 'pointer',
            background: 'rgba(244, 63, 94, 0.08)',
            padding: '10px',
            borderRadius: '8px',
            border: '1px solid rgba(244, 63, 94, 0.2)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <TrendingUp size={16} color="#f43f5e" />
              <span>PTF Kesişim Noktalarını Pingler</span>
            </div>
            <input
              type="checkbox"
              checked={showIntersections}
              onChange={(e) => setShowIntersections(e.target.checked)}
              style={{ accentColor: '#f43f5e', width: '16px', height: '16px', cursor: 'pointer' }}
            />
          </label>

          {/* Confidence Intervals Toggle */}
          <label style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            fontSize: '0.83rem',
            color: '#cbd5e1',
            cursor: 'pointer',
            background: 'rgba(255, 255, 255, 0.03)',
            padding: '10px',
            borderRadius: '8px',
            border: '1px solid rgba(255, 255, 255, 0.06)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <BarChart2 size={16} color="#e11d48" />
              <span>%95 Güven Aralığı Bantsı</span>
            </div>
            <input
              type="checkbox"
              checked={showConfidenceInterval}
              onChange={(e) => setShowConfidenceInterval(e.target.checked)}
              style={{ accentColor: '#e11d48', width: '16px', height: '16px', cursor: 'pointer' }}
            />
          </label>

        </div>
      </div>

    </aside>
  );
};
