import { useWindowStore } from './store';
import { Window } from './Window';
import { useAppRegistry } from '../apps/registry';

export function WindowSystem() {
  const openedIds = useWindowStore((s) => s.getOpenedIds());
  const { getApp } = useAppRegistry();

  return (
    <>
      {openedIds.map((id) => {
        const win = useWindowStore.getState().getWindow(id);
        if (!win) return null;
        const app = getApp(win.appId);
        const onClose = app?.closeBehavior === 'minimize'
          ? () => useWindowStore.getState().minimizeWindow(id)
          : undefined;
        return <Window key={id} windowId={id} onClose={onClose} />;
      })}
    </>
  );
}
