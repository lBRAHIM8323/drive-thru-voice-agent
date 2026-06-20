import { useState } from 'react';
import { Navigate } from 'react-router-dom';
import {
  Alert,
  Button,
  Center,
  Container,
  Paper,
  PasswordInput,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { IconAlertCircle } from '@tabler/icons-react';

import { useLogin } from '../../api/hooks';
import { useAuth } from './AuthContext';

export function LoginPage() {
  const { isAuthenticated, login } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const loginMutation = useLogin();

  if (isAuthenticated) {
    return <Navigate to="/admin" replace />;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    try {
      const result = await loginMutation.mutateAsync({ username, password });
      login(result.access_token);
    } catch {
      // error is displayed via mutation state
    }
  }

  return (
    <Center h="100vh" bg="gray.0">
      <Container size="xs" w={400}>
        <Paper withBorder shadow="md" p="xl" radius="md">
          <form onSubmit={handleSubmit}>
            <Stack>
              <Title order={2} ta="center">
                Drive-Thru Admin
              </Title>
              <Text c="dimmed" size="sm" ta="center">
                Sign in to your account
              </Text>

              {loginMutation.isError && (
                <Alert
                  icon={<IconAlertCircle size={16} />}
                  color="red"
                  variant="light"
                >
                  {loginMutation.error instanceof Error
                    ? loginMutation.error.message
                    : 'Login failed'}
                </Alert>
              )}

              <TextInput
                label="Username"
                placeholder="Enter your username"
                value={username}
                onChange={(e) => setUsername(e.currentTarget.value)}
                required
                autoFocus
              />

              <PasswordInput
                label="Password"
                placeholder="Enter your password"
                value={password}
                onChange={(e) => setPassword(e.currentTarget.value)}
                required
              />

              <Button
                type="submit"
                fullWidth
                loading={loginMutation.isPending}
              >
                Sign in
              </Button>
            </Stack>
          </form>
        </Paper>
      </Container>
    </Center>
  );
}
