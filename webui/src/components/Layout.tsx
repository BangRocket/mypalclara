import { ReactNode } from 'react';
import { Sidebar } from './Sidebar';
import { DateNavigation } from './Calendar';
import { useUiStore } from '../stores';

interface LayoutProps {
  children: ReactNode;
}

export function Layout({ children }: LayoutProps) {
  const sidebarCollapsed = useUiStore((state) => state.sidebarCollapsed);
  const toggleSidebar = useUiStore((state) => state.toggleSidebar);

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      <aside
        className={`${
          sidebarCollapsed ? 'w-0' : 'w-80'
        } flex-shrink-0 transition-all duration-200 overflow-hidden border-r border-gray-200 bg-white`}
      >
        <Sidebar />
      </aside>

      {/* Main content */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Header bar */}
        <header className="h-12 border-b border-gray-200 bg-white flex items-center px-4">
          <button
            onClick={toggleSidebar}
            className="p-1 hover:bg-gray-100 rounded"
            title={sidebarCollapsed ? 'Show sidebar' : 'Hide sidebar'}
          >
            <svg
              className="w-5 h-5 text-gray-600"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 6h16M4 12h16M4 18h16"
              />
            </svg>
          </button>
          <span className="ml-4 text-sm text-gray-600">MyPalClara</span>
        </header>

        {/* Date navigation for daily notes */}
        <DateNavigation />

        {/* Content area */}
        <div className="flex-1 overflow-auto">
          {children}
        </div>
      </main>
    </div>
  );
}
