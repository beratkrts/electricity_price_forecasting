import React from 'react';
import { HistoricalBenchmark } from '../components/dashboard/HistoricalBenchmark';

export const Analysis: React.FC = () => {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <HistoricalBenchmark />
    </div>
  );
};
