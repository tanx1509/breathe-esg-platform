import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';

export default function Layout() {
  return (
    <div className="min-h-screen bg-[#F8FAF9]">
      <Sidebar />
      <main className="ml-[240px] min-h-screen">
        <div className="px-8 py-6 max-w-[1440px]">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
