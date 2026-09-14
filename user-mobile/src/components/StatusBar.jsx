import { Signal, Wifi, BatteryFull } from 'lucide-react';

export default function StatusBar({ dark = false }) {
  const color = dark ? '#ffffff' : 'var(--color-text)';
  return (
    <div className="status-bar" style={{ color }}>
      <span>9:41</span>
      <div className="status-bar-icons">
        <Signal size={15} strokeWidth={2.5} />
        <Wifi size={15} strokeWidth={2.5} />
        <BatteryFull size={17} strokeWidth={2} />
      </div>
    </div>
  );
}
