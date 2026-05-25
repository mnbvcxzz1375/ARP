import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { RouterForTesting } from '../../../test-utils';
import PublicHomePage from '../PublicHomePage';

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <RouterForTesting>
        <PublicHomePage />
      </RouterForTesting>
    </QueryClientProvider>,
  );
}

describe('PublicHomePage', () => {
  it('renders sign in link', () => {
    renderPage();
    expect(screen.getByText('Sign In')).toBeInTheDocument();
  });

  it('renders request personal access link', () => {
    renderPage();
    expect(screen.getByText('Request Personal Access')).toBeInTheDocument();
  });

  it('renders request enterprise access link', () => {
    renderPage();
    expect(screen.getByText('Request Enterprise Access')).toBeInTheDocument();
  });

  it('has no emoji in the page', () => {
    renderPage();
    const { container } = renderPage();
    const emojiRegex = /[\u{1F300}-\u{1F9FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}]/u;
    expect(emojiRegex.test(container.textContent || '')).toBe(false);
  });
});