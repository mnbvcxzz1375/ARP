import { describe, it, expect, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Routes, Route } from 'react-router-dom';
import { RouterForTesting } from '../../../test-utils';
import DocsPage from '../DocsPage';
import ApiReferencePage from '../ApiReferencePage';
import { DOCS_BY_ID, docSourceFor } from '../docsRegistry';
import { setLocale, __resetI18n } from '../../../i18n/core';

/**
 * Locale-dependent docs content coverage.
 *
 * The repo docs/*.md sources are locale-independent; the eight that are
 * written in English have Chinese mirrors under src/features/docs/content/zh
 * (selected by docSourceFor), and the API Reference page resolves OpenAPI
 * operation text through the `docs.api.op.*` catalog keys. These tests pin
 * the zh behavior; the default-locale (en) behavior is pinned by
 * DocsLayout.test.tsx and ApiReferencePage.test.tsx.
 */
describe('zh locale docs content', () => {
  afterEach(() => __resetI18n());

  it('renders the zh mirror for an English repo doc under zh locale', () => {
    setLocale('zh');
    render(
      <RouterForTesting initialEntries={['/docs/dashboard-rbac']}>
        <Routes>
          <Route path="/docs/:docId" element={<DocsPage />} />
        </Routes>
      </RouterForTesting>,
    );
    expect(
      screen.getByRole('heading', { name: 'AgentNet 控制台 RBAC 指南', level: 1 }),
    ).toBeInTheDocument();
    expect(screen.getByText(/所有权限校验都经过/)).toBeInTheDocument();
  });

  it('renders the repository source under en locale', () => {
    setLocale('en');
    render(
      <RouterForTesting initialEntries={['/docs/dashboard-rbac']}>
        <Routes>
          <Route path="/docs/:docId" element={<DocsPage />} />
        </Routes>
      </RouterForTesting>,
    );
    expect(
      screen.getByRole('heading', { name: 'AgentNet Dashboard RBAC Guide', level: 1 }),
    ).toBeInTheDocument();
  });

  it('docSourceFor picks sourceZh under zh and falls back under other locales', () => {
    const entry = DOCS_BY_ID.get('production-deploy')!;
    expect(docSourceFor(entry, 'zh').startsWith('# 生产部署')).toBe(true);
    expect(docSourceFor(entry, 'en').startsWith('# Production Deploy')).toBe(true);
    // Docs with a mixed repo source (English h1 + Chinese body) get a zh
    // mirror that only fixes the heading, plus an en mirror.
    const mixedDoc = DOCS_BY_ID.get('quickstart')!;
    expect(docSourceFor(mixedDoc, 'zh').startsWith('# 快速开始')).toBe(true);
    expect(docSourceFor(mixedDoc, 'en').startsWith('# Quickstart')).toBe(true);
    // Docs that are fully Chinese in the repo have no zh mirror.
    const chineseDoc = DOCS_BY_ID.get('architecture')!;
    expect(docSourceFor(chineseDoc, 'zh')).toBe(chineseDoc.source);
    // sdk-python-quickstart is the deliberate exception (test-pinned heading).
    const pinned = DOCS_BY_ID.get('sdk-python-quickstart')!;
    expect(pinned.sourceEn).toBeUndefined();
    expect(docSourceFor(pinned, 'en').startsWith('# Python SDK 快速上手')).toBe(true);
  });

  it('renders the en mirror for a Chinese repo doc under en locale', () => {
    setLocale('en');
    render(
      <RouterForTesting initialEntries={['/docs/architecture']}>
        <Routes>
          <Route path="/docs/:docId" element={<DocsPage />} />
        </Routes>
      </RouterForTesting>,
    );
    expect(
      screen.getByRole('heading', { name: 'Architecture', level: 1 }),
    ).toBeInTheDocument();
    expect(screen.getByText(/message relay layer/)).toBeInTheDocument();
  });

  it('renders the Chinese repository source for that doc under zh locale', () => {
    setLocale('zh');
    render(
      <RouterForTesting initialEntries={['/docs/architecture']}>
        <Routes>
          <Route path="/docs/:docId" element={<DocsPage />} />
        </Routes>
      </RouterForTesting>,
    );
    expect(
      screen.getByRole('heading', { name: '系统架构', level: 1 }),
    ).toBeInTheDocument();
  });

  it('API Reference renders zh op text under zh and spec text under en', () => {
    setLocale('zh');
    const { unmount } = render(<ApiReferencePage />);
    expect(screen.getAllByText('列出智能体').length).toBeGreaterThan(0);
    unmount();

    setLocale('en');
    render(<ApiReferencePage />);
    expect(screen.getAllByText('List agents').length).toBeGreaterThan(0);
    expect(screen.getAllByText(/List the authenticated user/).length).toBeGreaterThan(0);
  });

  it('rendered docs body contains no em-dash under either locale', () => {
    setLocale('zh');
    const { container: zhContainer } = render(
      <RouterForTesting initialEntries={['/docs/production-deploy']}>
        <Routes>
          <Route path="/docs/:docId" element={<DocsPage />} />
        </Routes>
      </RouterForTesting>,
    );
    expect(zhContainer.textContent).not.toContain('—');

    setLocale('en');
    // production-deploy renders its English repository source under 'en'.
    const { container: enContainer } = render(
      <RouterForTesting initialEntries={['/docs/production-deploy']}>
        <Routes>
          <Route path="/docs/:docId" element={<DocsPage />} />
        </Routes>
      </RouterForTesting>,
    );
    expect(enContainer.textContent).not.toContain('—');
  });
});
