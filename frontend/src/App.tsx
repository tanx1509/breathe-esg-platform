import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Analytics as VercelAnalytics } from '@vercel/analytics/react';
import { isAuthenticated } from './api/client';
import Layout from './components/Layout';
import Login from './pages/Login';
import CommandCenter from './pages/CommandCenter';
import ReviewQueue from './pages/ReviewQueue';
import UploadPage from './pages/UploadPage';
import Analytics from './pages/Analytics';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  if (!isAuthenticated()) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
          <Route path="/" element={<CommandCenter />} />
          <Route path="/review" element={<ReviewQueue />} />
          <Route path="/analytics" element={<Analytics />} />
          <Route path="/upload" element={<UploadPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      <VercelAnalytics />
    </BrowserRouter>
  );
}
