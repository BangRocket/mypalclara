import { lazy } from 'react';
import type { AppDefinition } from './registry';

const PlaceholderApp = lazy(() =>
  Promise.resolve({
    default: ({ windowId }: { windowId: string }) => {
      return (
        <div style={{ padding: 16, color: '#94a3b8' }}>
          <p>App placeholder for window: {windowId}</p>
        </div>
      );
    },
  }),
);

export const defaultApps = new Map<string, AppDefinition>([
  ['clara-chat', {
    id: 'clara-chat',
    name: 'Clara',
    icon: '\u{1F4AC}',
    defaultWindowSize: { width: 700, height: 550 },
    component: PlaceholderApp,
    singleton: true,
    closeBehavior: 'minimize',
  }],
  ['settings', {
    id: 'settings',
    name: 'Settings',
    icon: '\u2699\uFE0F',
    defaultWindowSize: { width: 500, height: 400 },
    component: PlaceholderApp,
    singleton: true,
  }],
]);
