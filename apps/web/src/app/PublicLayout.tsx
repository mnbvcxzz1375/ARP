import { Outlet, Navigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import LoadingState from '../components/LoadingState';

export default function PublicLayout() {
  const { isLoading, isError, data } = useAuth();
  if (isLoading) return <LoadingState />;
  if (!isError && data) return <Navigate to="/app/overview" replace />;
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <Outlet />
    </div>
  );
}
