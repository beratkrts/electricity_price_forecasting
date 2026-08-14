import React from 'react';
import { HistoricalBenchmark } from '../components/dashboard/HistoricalBenchmark';
import { PreForecastBenchmark } from '../components/dashboard/PreForecastBenchmark';

interface AnalysisProps {
  currencyMode?: 'TRY' | 'USD';
  usdRate?: number;
}

export const Analysis: React.FC<AnalysisProps> = ({ currencyMode = 'USD', usdRate = 33.15 }) => {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <PreForecastBenchmark currencyMode={currencyMode} usdRate={usdRate} />
      <HistoricalBenchmark currencyMode={currencyMode} usdRate={usdRate} />
    </div>
  );
};

