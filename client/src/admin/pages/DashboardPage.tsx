import { Card, SimpleGrid, Text, Title } from '@mantine/core';
import { Link } from 'react-router-dom';

import { useAgentConfigs, useBranches, useDocuments, useMenu } from '../../api/hooks';
import { PageHeader } from '../../components/PageHeader';

function StatCard({ label, value, to }: { label: string; value: number | string; to: string }) {
  return (
    <Card component={Link} to={to} withBorder padding="lg" radius="md">
      <Text c="dimmed" size="sm">
        {label}
      </Text>
      <Title order={2} mt={4}>
        {value}
      </Title>
    </Card>
  );
}

export function DashboardPage() {
  const menu = useMenu();
  const docs = useDocuments();
  const configs = useAgentConfigs();
  const branches = useBranches();

  const dash = (n?: number) => (n === undefined ? '—' : n);

  return (
    <>
      <PageHeader title="Dashboard" description="Overview of your drive-thru configuration." />
      <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }}>
        <StatCard label="Menu items" value={dash(menu.data?.length)} to="/admin/menu" />
        <StatCard label="Documents" value={dash(docs.data?.length)} to="/admin/documents" />
        <StatCard
          label="Agent configs"
          value={dash(configs.data?.length)}
          to="/admin/agent-configs"
        />
        <StatCard label="Branches" value={dash(branches.data?.length)} to="/admin/branches" />
      </SimpleGrid>
    </>
  );
}
