import React from 'react';
import { TrendingUp, AlertTriangle, Crosshair, Zap, Award, Activity } from 'lucide-react';
import { DashboardMetrics } from '../../types/energy';
import { formatCurrency } from '../../utils/formatters';

interface MetricCardsProps {
  metrics: DashboardMetrics;
}

export const MetricCards: React.FC<MetricCardsProps> = ({ metrics }) => {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: '16px', marginBottom: '20px' }}>
      
      {/* Card 1: Avg PTF */}
      <div className="glass-panel glass-panel-interactive" style={{ padding: '16px 18px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
          <span style={{ fontSize: '0.8rem', color: '#94a3b8', fontWeight: 600 }}>Ortalama PTF (Gerçekleşen)</span>
          <div style={{ padding: '6px', borderRadius: '8px', background: 'rgba(56, 189, 248, 0.15)', color: '#38bdf8' }}>
            <Zap size={18} />
          </div>
        </div>
        <div style={{ fontSize: '1.45rem', fontWeight: 800, color: '#fff', fontFamily: 'Outfit' }}>
          {formatCurrency(metrics.avgPtf, '₺')}
        </div>
        <div style={{ fontSize: '0.72rem', color: '#38bdf8', marginTop: '4px', display: 'flex', alignItems: 'center', gap: '4px' }}>
          <TrendingUp size={12} />
          <span>EPİAŞ Gün Öncesi Piyasası</span>
        </div>
      </div>

      {/* Card 2: LightGBM WAPE */}
      <div className="glass-panel glass-panel-interactive" style={{ padding: '16px 18px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
          <span style={{ fontSize: '0.8rem', color: '#94a3b8', fontWeight: 600 }}>LightGBM WAPE</span>
          <div style={{ padding: '6px', borderRadius: '8px', background: 'rgba(16, 185, 129, 0.15)', color: '#10b981' }}>
            <AlertTriangle size={18} />
          </div>
        </div>
        <div style={{ fontSize: '1.45rem', fontWeight: 800, color: '#10b981', fontFamily: 'Outfit' }}>
          %{metrics.wapeLightgbm}
        </div>
        <div style={{ fontSize: '0.72rem', color: '#94a3b8', marginTop: '4px' }}>
          Ağırlıklı Mutlak Yüzde Hata
        </div>
      </div>

      {/* Card 3: LightGBM MAPE */}
      <div className="glass-panel glass-panel-interactive" style={{ padding: '16px 18px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
          <span style={{ fontSize: '0.8rem', color: '#94a3b8', fontWeight: 600 }}>LightGBM MAPE</span>
          <div style={{ padding: '6px', borderRadius: '8px', background: 'rgba(225, 29, 72, 0.15)', color: '#e11d48' }}>
            <Activity size={18} />
          </div>
        </div>
        <div style={{ fontSize: '1.45rem', fontWeight: 800, color: '#e11d48', fontFamily: 'Outfit' }}>
          %{metrics.mapeLightgbm}
        </div>
        <div style={{ fontSize: '0.72rem', color: '#94a3b8', marginTop: '4px' }}>
          Ort. Fiyat Tahmini: <strong>{formatCurrency(metrics.avgLightgbmForecast, '₺')}</strong>
        </div>
      </div>

      {/* Card 4: Best Model */}
      <div className="glass-panel glass-panel-interactive" style={{ padding: '16px 18px', border: '1px solid rgba(251, 191, 36, 0.3)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
          <span style={{ fontSize: '0.8rem', color: '#fbbf24', fontWeight: 600 }}>Aktif Tahmin Modeli</span>
          <div style={{ padding: '6px', borderRadius: '8px', background: 'rgba(251, 191, 36, 0.2)', color: '#fbbf24' }}>
            <Award size={18} />
          </div>
        </div>
        <div style={{ fontSize: '1.1rem', fontWeight: 800, color: '#fbbf24', fontFamily: 'Outfit' }}>
          {metrics.bestModel}
        </div>
        <div style={{ fontSize: '0.72rem', color: '#fbbf24', marginTop: '4px' }}>
          Ort. Tahmin: <strong>{formatCurrency(metrics.avgLightgbmForecast, '₺')}</strong>
        </div>
      </div>

      {/* Card 5: Intersections Ping Count */}
      <div className="glass-panel glass-panel-interactive" style={{ padding: '16px 18px', border: '1px solid rgba(244, 63, 94, 0.3)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
          <span style={{ fontSize: '0.8rem', color: '#fda4af', fontWeight: 600 }}>Kesişim Ping Sayısı</span>
          <div style={{ padding: '6px', borderRadius: '8px', background: 'rgba(244, 63, 94, 0.2)', color: '#f43f5e' }}>
            <Crosshair size={18} />
          </div>
        </div>
        <div style={{ fontSize: '1.45rem', fontWeight: 800, color: '#f43f5e', fontFamily: 'Outfit' }}>
          {metrics.totalIntersections} Nokta
        </div>
        <div style={{ fontSize: '0.72rem', color: '#fda4af', marginTop: '4px' }}>
          Model - Gerçekleşen Çaprazlaması
        </div>
      </div>

    </div>
  );
};
