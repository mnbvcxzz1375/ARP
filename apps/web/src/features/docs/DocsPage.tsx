import { useParams, Link } from 'react-router-dom';
import { useI18n, useT } from '../../i18n';
import { DOCS_BY_ID, docSourceFor } from './docsRegistry';
import DocsMarkdown from './DocsMarkdown';

/**
 * Renders one registered markdown doc by URL segment (`/docs/:docId`).
 * Unknown ids render a pixel "not found" panel instead of guessing content.
 */
export default function DocsPage() {
  const { docId } = useParams();
  const t = useT();
  const { locale } = useI18n();
  const entry = docId ? DOCS_BY_ID.get(docId) : undefined;

  if (!entry) {
    return (
      <div className="border-2 border-pixel-line bg-pixel-surface p-6">
        <h1 className="font-display text-pixel-lg text-pixel-fg">
          {t('docs.notFound.title')}
        </h1>
        <p className="mt-4 font-body text-base text-pixel-muted">
          {t('docs.notFound.description')}
        </p>
        <Link
          to="/docs/quickstart"
          className="mt-6 inline-flex min-h-[44px] items-center border-2 border-pixel-line bg-pixel-raised px-4 py-2 font-pixel text-pixel-base text-pixel-fg hover:bg-pixel-accent"
        >
          {t('docs.notFound.back')}
        </Link>
      </div>
    );
  }

  return (
    <article data-testid="docs-doc">
      <DocsMarkdown source={docSourceFor(entry, locale)} />
    </article>
  );
}
