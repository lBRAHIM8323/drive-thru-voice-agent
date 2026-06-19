import { Navigate, Route, Routes } from 'react-router-dom';

import { CustomerPage } from './customer/CustomerPage';
import { AdminLayout } from './admin/AdminLayout';
import { DashboardPage } from './admin/pages/DashboardPage';
import { MenuPage } from './admin/pages/MenuPage';
import { DocumentsPage } from './admin/pages/DocumentsPage';
import { AgentConfigsPage } from './admin/pages/AgentConfigsPage';
import { AgentConfigEditPage } from './admin/pages/AgentConfigEditPage';
import { ParserConfigPage } from './admin/pages/ParserConfigPage';
import { BranchesPage } from './admin/pages/BranchesPage';

export function App() {
  return (
    <Routes>
      <Route path="/" element={<CustomerPage />} />

      <Route path="/admin" element={<AdminLayout />}>
        <Route index element={<DashboardPage />} />
        <Route path="menu" element={<MenuPage />} />
        <Route path="documents" element={<DocumentsPage />} />
        <Route path="agent-configs" element={<AgentConfigsPage />} />
        <Route path="agent-configs/new" element={<AgentConfigEditPage />} />
        <Route path="agent-configs/:id" element={<AgentConfigEditPage />} />
        <Route path="parser-config" element={<ParserConfigPage />} />
        <Route path="branches" element={<BranchesPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
