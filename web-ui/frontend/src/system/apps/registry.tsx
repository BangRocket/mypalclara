import { createContext, useContext } from 'react';
import type { LazyExoticComponent, ComponentType, ReactNode } from 'react';

export interface AppDefinition {
  id: string;
  name: string;
  icon: string;
  defaultWindowSize: { width: number; height: number };
  component: LazyExoticComponent<ComponentType<{ windowId: string }>>;
  singleton?: boolean;
  closeBehavior?: 'close' | 'minimize';
}

interface AppRegistryContextValue {
  apps: Map<string, AppDefinition>;
  getComponent: (appId: string) => LazyExoticComponent<ComponentType<{ windowId: string }>> | null;
  getApp: (appId: string) => AppDefinition | undefined;
}

const AppRegistryContext = createContext<AppRegistryContextValue>({
  apps: new Map(),
  getComponent: () => null,
  getApp: () => undefined,
});

export function AppRegistryProvider({
  apps,
  children,
}: {
  apps: Map<string, AppDefinition>;
  children: ReactNode;
}) {
  const value: AppRegistryContextValue = {
    apps,
    getComponent: (appId) => apps.get(appId)?.component ?? null,
    getApp: (appId) => apps.get(appId),
  };

  return (
    <AppRegistryContext.Provider value={value}>
      {children}
    </AppRegistryContext.Provider>
  );
}

export function useAppRegistry() {
  return useContext(AppRegistryContext);
}
