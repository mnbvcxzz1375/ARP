import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../api/client';

export interface AuthUser {
  user_id: string;
  username: string;
  role: string;
  permissions: string[];
  csrf_required: boolean;
  session_expires_at: string;
  step_up_until: string | null;
}

export const useAuth = () => {
  return useQuery<AuthUser>({
    queryKey: ['auth/me'],
    queryFn: () => api.get('/v1/dashboard/auth/me').then((r) => r.data),
    retry: false,
  });
};

export const useLogin = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ username, api_key }: { username: string; api_key: string }) =>
      api.post('/v1/dashboard/auth/login', { username, api_key }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['auth/me'] });
      window.location.href = '/app/overview';
    },
  });
};

export const useLogout = () => {
  return useMutation({
    mutationFn: () => api.post('/v1/dashboard/auth/logout'),
    onSuccess: () => {
      window.location.href = '/login';
    },
  });
};
