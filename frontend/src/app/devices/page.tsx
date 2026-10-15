'use client';

// The actual device-registry UI lives in DeviceRegistry (extracted so it can
// also be embedded, container-relative, inside SituationRoom's
// SELF_MONITORING panel without dragging TeamShell's `min-h-screen` and the
// viewport-fixed detail sidebar/backdrop along with it — see
// components/devices/DeviceRegistry.tsx for details on what changed and why).
import TeamShell from '@/components/Layout/TeamShell';
import { DeviceRegistry } from '@/components/devices/DeviceRegistry';

export default function DevicesPage() {
  return (
    <TeamShell
      team="blue"
      title="ASSET REGISTRY & DEVICE INVENTORY"
      subtitle="Network-wide device discovery — hostname, IP, OS, risk posture, service map"
    >
      <DeviceRegistry />
    </TeamShell>
  );
}
