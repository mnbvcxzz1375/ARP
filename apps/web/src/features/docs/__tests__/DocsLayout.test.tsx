import { describe, it, expect } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { RouterForTesting } from '../../../test-utils';
import DocsLayout from '../DocsLayout';
import DocsPage from '../DocsPage';
import ApiReferencePage from '../ApiReferencePage';
import { DOCS_BY_ID } from '../docsRegistry';

/**
 * DocsLayout / DocsPage unit coverage.
 *
 * Rendered without an I18nProvider on purpose: the docs surface is public,
 * so it binds to the module-level store like PublicLayout does (default
 * locale en). Sidebar labels therefore assert English.
 *
 * DocsBackLink calls useAuth(), so the tree needs a QueryClientProvider
 * (the auth probe stays in loading state -> anonymous back link).
 *
 * Note: setupTests.ts does not set IS_REACT_ACT_ENVIRONMENT, so React state
 * updates from router navigation are flushed asynchronously; post-click
 * assertions use waitFor.
 */
function renderDocsAt(initialPath: string | string[]) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <RouterForTesting
        initialEntries={Array.isArray(initialPath) ? initialPath : [initialPath]}
      >
        <Routes>
          <Route path="/docs" element={<DocsLayout />}>
            <Route index element={<Navigate to="quickstart" replace />} />
            <Route path="api-reference" element={<ApiReferencePage />} />
            <Route path=":docId" element={<DocsPage />} />
          </Route>
          <Route path="/login" element={<div data-testid="login-page">Login</div>} />
          <Route
            path="/app/overview"
            element={<div data-testid="app-overview">Dashboard</div>}
          />
        </Routes>
      </RouterForTesting>
    </QueryClientProvider>,
  );
}

describe('DocsLayout', () => {
  it('renders the sidebar groups and the quickstart markdown', () => {
    renderDocsAt('/docs/quickstart');

    // Sidebar group headers (en locale). 'Quickstart' / 'Python SDK' /
    // 'API Reference' also appear as doc titles, so assert via getAllByText.
    expect(screen.getAllByText('Quickstart').length).toBeGreaterThan(0);
    expect(screen.getByText('Protocol')).toBeInTheDocument();
    expect(screen.getAllByText('Python SDK').length).toBeGreaterThan(0);
    expect(screen.getByText('Deploy & Ops')).toBeInTheDocument();
    expect(screen.getAllByText('API Reference').length).toBeGreaterThan(0);

    // Sidebar nav entry for a doc title.
    expect(screen.getByRole('link', { name: 'CLI' })).toBeInTheDocument();

    // Markdown body: quickstart.md starts with "# Quickstart".
    expect(
      screen.getByRole('heading', { name: 'Quickstart', level: 1 }),
    ).toBeInTheDocument();

    // Pixel code blocks render without syntax highlighting.
    const codeBlocks = document.querySelectorAll('pre');
    expect(codeBlocks.length).toBeGreaterThan(0);
    expect(
      Array.from(codeBlocks).some((block) => block.querySelector('code.font-mono')),
    ).toBe(true);
  });

  it('redirects /docs index to the quickstart doc', async () => {
    renderDocsAt('/docs');
    await waitFor(() =>
      expect(
        screen.getByRole('heading', { name: 'Quickstart', level: 1 }),
      ).toBeInTheDocument(),
    );
  });

  it('navigates between docs from the sidebar', async () => {
    const user = userEvent.setup();
    renderDocsAt('/docs/quickstart');

    await user.click(screen.getByRole('link', { name: 'Python SDK Quickstart' }));
    // sdk-python-quickstart.md starts with "# Python SDK 快速上手"
    await waitFor(() =>
      expect(
        screen.getByRole('heading', { name: 'Python SDK 快速上手', level: 1 }),
      ).toBeInTheDocument(),
    );
  });

  it('opens the mobile contents menu and navigates from it', async () => {
    const user = userEvent.setup();
    renderDocsAt('/docs/quickstart');

    await user.click(screen.getByRole('button', { name: 'Contents' }));

    // The overlay panel shows the same nav entries.
    const cliLink = screen.getByRole('link', { name: 'CLI' });
    expect(cliLink).toBeVisible();
    await user.click(cliLink);
    await waitFor(() =>
      expect(
        screen.getByRole('heading', { name: 'CLI', level: 1 }),
      ).toBeInTheDocument(),
    );
  });

  it('renders a not found panel for unknown doc ids', () => {
    renderDocsAt('/docs/does-not-exist');
    expect(screen.getByText('Doc not found')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Back to Quickstart' })).toBeInTheDocument();
  });

  it('renders the anonymous back link in the sidebar', () => {
    // No signed-in session in this tree -> the way out goes to sign-in.
    renderDocsAt('/docs/quickstart');
    expect(
      screen.getByRole('link', { name: 'Back to Sign In' }),
    ).toBeInTheDocument();
  });

  it('mobile back button falls back to the sign-in page without history', async () => {
    const user = userEvent.setup();
    // jsdom's window.history has no react-router entry stack (idx 0), so
    // the button takes the documented fallback for anonymous visitors.
    // The history-based navigate(-1) path is covered by e2e in a real
    // browser, where window.history.state.idx is populated.
    renderDocsAt('/docs/quickstart');

    await user.click(
      screen.getByRole('button', { name: 'Back to the previous page' }),
    );

    await waitFor(() =>
      expect(screen.getByTestId('login-page')).toBeInTheDocument(),
    );
  });

  it('registers every doc entry with markdown source', () => {
    for (const [docId, entry] of DOCS_BY_ID) {
      expect(entry.docId).toBe(docId);
      expect(entry.source.length).toBeGreaterThan(0);
      expect(entry.source).toMatch(/^#\s/mu);
    }
  });
});
