import { MemoryRouter, type MemoryRouterProps } from 'react-router-dom';

/**
 * MemoryRouter wrapper with React Router v7 future flags enabled.
 * Use this in tests to silence the Future Flag warnings.
 *
 * Usage:
 *   <RouterForTesting>
 *     <Routes>...</Routes>
 *   </RouterForTesting>
 *
 *   <RouterForTesting initialEntries={['/some/path']}>
 *     <Routes>...</Routes>
 *   </RouterForTesting>
 */
export function RouterForTesting(props: MemoryRouterProps) {
  return (
    <MemoryRouter
      future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
      {...props}
    />
  );
}
