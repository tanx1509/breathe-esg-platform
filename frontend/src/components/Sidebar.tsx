import { NavLink, useLocation } from 'react-router-dom';
import { logout, getDecodedToken } from '../api/client';
import {
  LayoutDashboard, ClipboardCheck, Upload, Shield, LogOut, Leaf,
  ChevronRight, BarChart3,
} from 'lucide-react';

const NAV_ITEMS = [
  { to: '/', icon: LayoutDashboard, label: 'Command Center', desc: 'Pipeline overview' },
  { to: '/review', icon: ClipboardCheck, label: 'Review Queue', desc: 'Analyst workspace' },
  { to: '/analytics', icon: BarChart3, label: 'Analytics', desc: 'Charts & insights' },
  { to: '/upload', icon: Upload, label: 'Data Ingestion', desc: 'Upload source CSVs' },
];

export default function Sidebar() {
  const location = useLocation();
  const user = getDecodedToken();

  return (
    <aside className="fixed left-0 top-0 bottom-0 w-[240px] bg-white border-r border-surface-border flex flex-col z-40">
      {/* Logo */}
      <div className="px-5 py-5">
        <div className="flex items-center gap-3 group cursor-default">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center shadow-md group-hover:shadow-lg group-hover:scale-105 transition-all duration-300"
               style={{ background: 'linear-gradient(135deg, #2E9844 0%, #0bafd0 100%)' }}>
            <Leaf className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-base font-extrabold text-txt-primary tracking-tight">Breathe ESG</h1>
            <p className="text-2xs text-txt-faint font-medium">Activity Platform</p>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-2 space-y-0.5">
        <p className="px-3 mb-3 text-2xs font-bold uppercase tracking-widest text-txt-faint">Operations</p>
        {NAV_ITEMS.map((item) => {
          const isActive = item.to === '/' ? location.pathname === '/' : location.pathname.startsWith(item.to);
          return (
            <NavLink key={item.to} to={item.to}
                     className={`nav-item group ${isActive ? 'nav-item-active' : ''}`}>
              <item.icon size={18} className={`transition-transform duration-200 group-hover:scale-110 ${isActive ? 'text-besg-500' : 'text-txt-faint group-hover:text-txt-secondary'}`} />
              <div className="flex-1 min-w-0">
                <span className="block text-sm">{item.label}</span>
                <span className="block text-2xs text-txt-faint font-normal">{item.desc}</span>
              </div>
              {isActive && <ChevronRight size={14} className="text-besg-400" />}
            </NavLink>
          );
        })}
      </nav>

      {/* Data info */}
      <div className="mx-3 mb-3 p-3 rounded-xl bg-besg-50 border border-besg-100">
        <p className="text-2xs font-bold text-besg-700 mb-1">📊 Live Data</p>
        <p className="text-2xs text-besg-600 leading-relaxed">43 records across 3 source types with full provenance</p>
      </div>

      {/* User */}
      <div className="px-3 py-4 border-t border-surface-border">
        <div className="flex items-center gap-3 px-3 py-2">
          <div className="w-9 h-9 rounded-full flex items-center justify-center text-xs font-bold text-white shadow-md"
               style={{ background: 'linear-gradient(135deg, #2E9844 0%, #0bafd0 100%)' }}>
            {user?.email?.[0]?.toUpperCase() || 'U'}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-txt-primary truncate">{user?.email?.split('@')[0] || 'Unknown'}</p>
            <div className="flex items-center gap-1">
              <Shield size={10} className="text-besg-500" />
              <span className="text-2xs text-txt-faint font-medium">{user?.role || 'VIEWER'}</span>
            </div>
          </div>
        </div>
        <button onClick={logout} className="nav-item w-full mt-1 text-txt-faint hover:text-red-500 transition-colors duration-200">
          <LogOut size={16} /><span>Sign out</span>
        </button>
      </div>
    </aside>
  );
}
