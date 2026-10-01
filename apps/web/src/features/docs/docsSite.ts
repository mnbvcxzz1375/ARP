/**
 * Chunk anchor for the public docs sub-site.
 *
 * The /docs pages are only ever reached through this module, so Vite emits
 * the whole sub-site - DocsLayout/DocsPage/ApiReferencePage, the docs
 * registry (with its raw markdown content) and the react-markdown/remark
 * rendering chain they drag in - as a single lazy chunk instead of one
 * chunk per page. That keeps the largest byte block in the bundle out of
 * the initial entry.
 *
 * Locale messages stay out of this chunk: `App.tsx` loads the `docs` i18n
 * namespace through the lazy-page helper next to this import.
 */
export { default as DocsLayout } from './DocsLayout';
export { default as DocsPage } from './DocsPage';
export { default as ApiReferencePage } from './ApiReferencePage';
