import { createBrowserRouter, Navigate, Outlet } from 'react-router'
import { NoAccessPage, RequireAccess, SignInPage } from '@/features/session'
import { MyActivityPage, MyUsagePage } from '@/features/usage'
import { Home } from './Home'
import { MovedTo } from './MovedTo'
import { AppLayout } from './layouts/AppLayout'

/** The admin console is only for admins and organization readers, so it loads on demand. */
const admin =
  (
    page:
      'AdminOverviewPage' | 'AdoptionPage' | 'MembersPage' | 'MemberDetailPage' | 'SeatsPage' | 'SyncPage' | 'TeamPage',
  ) =>
  async () => ({
    Component: (await import('@/features/admin'))[page],
  })

export const router = createBrowserRouter([
  { path: '/', element: <Home /> },
  { path: '/signin', element: <SignInPage /> },
  { path: '/no-access', element: <NoAccessPage /> },
  {
    element: <AppLayout />,
    children: [
      {
        element: (
          <RequireAccess need="own-usage">
            <Outlet />
          </RequireAccess>
        ),
        children: [
          { path: '/me', element: <MyUsagePage /> },
          { path: '/me/activity', element: <MyActivityPage /> },
          { path: '/me/models', element: <MovedTo to="/me" /> },
          { path: '/me/daily', element: <MovedTo to="/me" /> },
        ],
      },
      {
        element: (
          <RequireAccess need="admin">
            <Outlet />
          </RequireAccess>
        ),
        children: [
          { path: '/admin', lazy: admin('AdminOverviewPage') },
          { path: '/admin/daily', element: <MovedTo to="/admin" /> },
          { path: '/admin/adoption', lazy: admin('AdoptionPage') },
          { path: '/admin/members', lazy: admin('MembersPage') },
          { path: '/admin/members/:login', lazy: admin('MemberDetailPage') },
          { path: '/admin/seats', lazy: admin('SeatsPage') },
          { path: '/admin/teams/:team', lazy: admin('TeamPage') },
          {
            element: (
              <RequireAccess need="sync">
                <Outlet />
              </RequireAccess>
            ),
            children: [{ path: '/admin/sync', lazy: admin('SyncPage') }],
          },
        ],
      },
    ],
  },
  { path: '*', element: <Navigate to="/" replace /> },
])
