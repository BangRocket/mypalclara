import { useEffect, useState } from 'react';
import { COLORS } from '../theme/constants';

export function Clock() {
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const interval = setInterval(() => setTime(new Date()), 60_000);
    return () => clearInterval(interval);
  }, []);

  const formatted = time.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });

  return (
    <span className="text-xs px-2 whitespace-nowrap" style={{ color: COLORS.textMuted }}>
      {formatted}
    </span>
  );
}
