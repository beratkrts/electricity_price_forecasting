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

      {/* Card 2: EPNet Forecast */}
      <div className="glass-panel glass-panel-interactive" style={{ padding: '16px 18px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
          <span style={{ fontSize: '0.8rem', color: '#94a3b8', fontWeight: 600 }}>EPNet (CNN+LSTM) MAPE</span>
          <div style={{ padding: '6px', borderRadius: '8px', background: 'rgba(16, 185, 129, 0.15)', color: '#10b981' }}>
            <AlertTriangle size={18} />
          </div>
        </div>
        <div style={{ fontSize: '1.45rem', fontWeight: 800, color: '#10b981', fontFamily: 'Outfit' }}>
          %{metrics.mapeEpnet}
        </div>
        <div style={{ fontSize: '0.72rem', color: '#94a3b8', marginTop: '4px' }}>
          Ort. Tahmin: <strong>{formatCurrency(metrics.avgEpnetForecast, '₺')}</strong>
        </div>
      </div>

      {/* Card 3: LightGBM Forecast */}
      <div className="glass-panel glass-panel-interactive" style={{ padding: '16px 18px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
          <span style={{ fontSize: '0.8rem', color: '#94a3b8', fontWeight: 600 }}>LightGBM MAPE</span>
          <div style={{ padding: '6px', borderRadius: '8px', background: 'rgba(192, 132, 252, 0.15)', color: '#c084fc' }}>
            <Activity size={18} />
          </div>
        </div>
        <div style={{ fontSize: '1.45rem', fontWeight: 800, color: '#c084fc', fontFamily: 'Outfit' }}>
          %{metrics.mapeLightgbm}
        </div>
        <div style={{ fontSize: '0.72rem', color: '#94a3b8', marginTop: '4px' }}>
          Ort. Tahmin: <strong>{formatCurrency(metrics.avgLightgbmForecast, '₺')}</strong>
        </div>
      </div>

      {/* Card 4: Hybrid Model Forecast */}
      <div className="glass-panel glass-panel-interactive" style={{ padding: '16px 18px', border: '1px solid rgba(251, 191, 36, 0.3)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
          <span style={{ fontSize: '0.8rem', color: '#fbbf24', fontWeight: 600 }}>Hibrit Model (Ensemble)</span>
          <div style={{ padding: '6px', borderRadius: '8px', background: 'rgba(251, 191, 36, 0.2)', color: '#fbbf24' }}>
            <Award size={18} />
          </div>
        </div>
        <div style={{ fontSize: '1.45rem', fontWeight: 800, color: '#fbbf24', fontFamily: 'Outfit' }}>
          %{metrics.mapeHybrid} <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#94a3b8' }}>MAPE</span>
        </div>
        <div style={{ fontSize: '0.72rem', color: '#fbbf24', marginTop: '4px' }}>
          Lider Model: <strong>{metrics.bestModel}</strong>
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
