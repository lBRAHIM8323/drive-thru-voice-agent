import { Navigate, Outlet } from 'react-router-dom';
import { Center, Loader } from '@mantine/core';

import { useAuth } from './AuthContext';

export function ProtectedRoute() {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <Center h="100vh">
        <Loader size="lg" />
      </Center>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/platform/login" replace />;
  }

  return <Outlet />;
}
