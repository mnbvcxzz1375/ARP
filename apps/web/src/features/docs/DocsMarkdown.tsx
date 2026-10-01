import { useNavigate } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { DOCS_BY_ID } from './docsRegistry';

/**
 * Pixel restyle of the markdown body.
 *
 * - Fenced code blocks: VT323 font-mono, 2px hard border, pixel-bg surface,
 *   no syntax highlighting (per the docs site design brief).
 * - Tables: 2px bordered cells, wrapped in a horizontal scroll container so
 *   wide tables do not overflow below 768px.
 * - Relative docs/*.md links are rewritten to in-app doc routes so the docs
 *   cross-references stay inside the site.
 * - Links use accent-2 in its functional link-affordance role: accent
 *   (#df7126) is only 2.85:1 on the light docs surface and would fail the
 *   4.5:1 WCAG 1.4.3 text minimum, while accent-2 holds 5.96:1 in light.
 *   See the single-accent rule in src/index.css.
 */

/**
 * react-markdown hands a `node` prop to every component; it is not a valid
 * DOM prop, so every handler below destructures it out before spreading.
 */
type MdProps<E extends keyof JSX.IntrinsicElements> = JSX.IntrinsicElements[E] & {
  node?: unknown;
};

// Code blocks: VT323 renders far below its design size at 12px (the
// pixel-base scale used for chip labels and nav items) and becomes
// unreadable in long code listings. pixel-lg (16px, lineHeight 1.5) is
// the same size as the body text and the floor at which VT323 stays
// legible; the extra leading keeps multi-line blocks scannable.
const BLOCK_CLASSES =
  'block font-mono text-pixel-lg leading-[1.7] whitespace-pre';

/**
 * Strip em-dash characters (U+2014) from rendered doc content.
 *
 * The zero-em-dash constraint applies to everything the docs site renders.
 * The raw sources live in the repository docs/ directory (outside the web
 * app) and a handful of them still contain em-dashes, so the markdown body
 * is normalized here, at the render boundary: every U+2014 becomes the
 * house-style double hyphen '--' (same replacement already used by the
 * locale files, e.g. shell.banner.enterprise). Chinese em-dash usage is
 * unheard of in these sources, and ASCII content (code blocks, URLs,
 * commands) never contains U+2014, so the rewrite is surface-clean.
 */
function normalizeDocMarkdown(source: string): string {
  return source.includes('\u2014') ? source.split('\u2014').join('--') : source;
}

export default function DocsMarkdown({ source }: { source: string }) {
  const navigate = useNavigate();

  return (
    <div className="docs-markdown font-body text-base leading-relaxed text-pixel-fg">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ node: _node, ...props }: MdProps<'h1'>) => (
            <h1
              className="font-display text-pixel-xl mt-0 mb-4 border-b-2 border-pixel-line pb-2"
              {...props}
            />
          ),
          h2: ({ node: _node, ...props }: MdProps<'h2'>) => (
            <h2
              className="font-display text-pixel-lg mt-8 mb-3 border-b-2 border-pixel-line pb-1"
              {...props}
            />
          ),
          h3: ({ node: _node, ...props }: MdProps<'h3'>) => (
            <h3 className="font-pixel text-pixel-base mt-6 mb-2" {...props} />
          ),
          h4: ({ node: _node, ...props }: MdProps<'h4'>) => (
            <h4 className="font-pixel text-pixel-base mt-4 mb-2" {...props} />
          ),
          p: ({ node: _node, ...props }: MdProps<'p'>) => <p className="my-3" {...props} />,
          ul: ({ node: _node, ...props }: MdProps<'ul'>) => <ul className="my-3 list-disc pl-6" {...props} />,
          ol: ({ node: _node, ...props }: MdProps<'ol'>) => <ol className="my-3 list-decimal pl-6" {...props} />,
          li: ({ node: _node, ...props }: MdProps<'li'>) => <li className="my-1" {...props} />,
          blockquote: ({ node: _node, ...props }: MdProps<'blockquote'>) => (
            <blockquote className="my-4 border-l-4 border-pixel-accent bg-pixel-raised px-4 py-2" {...props} />
          ),
          a: ({ node: _node, href, children, ...rest }: MdProps<'a'>) => {
            const rewritten = rewriteDocHref(String(href ?? ''));
            if (rewritten) {
              return (
                <a
                  href={rewritten}
                  className="text-pixel-accent-2 underline"
                  onClick={(event) => {
                    // Plain left clicks stay inside the SPA.
                    if (
                      event.metaKey ||
                      event.ctrlKey ||
                      event.shiftKey ||
                      event.button !== 0
                    )
                      return;
                    event.preventDefault();
                    navigate(rewritten);
                  }}
                  {...rest}
                >
                  {children}
                </a>
              );
            }
            return (
              <a
                href={String(href ?? '')}
                target="_blank"
                rel="noopener noreferrer"
                className="text-pixel-accent-2 underline"
                {...rest}
              >
                {children}
              </a>
            );
          },
          // Fenced code blocks: pre is the pixel container, code keeps the
          // mono font and preserved whitespace. No syntax highlighting.
          pre: ({ node: _node, children }: MdProps<'pre'>) => (
            <pre className="my-4 overflow-x-auto border-2 border-pixel-line bg-pixel-bg p-3">
              {children}
            </pre>
          ),
          code: ({ node: _node, className, children, ...rest }: MdProps<'code'>) => {
            const isBlock =
              typeof className === 'string' && className.includes('language-');
            if (isBlock) {
              return (
                <code className={`${BLOCK_CLASSES} ${String(className ?? '')}`} {...rest}>
                  {children}
                </code>
              );
            }
            return (
              <code
                className="border-2 border-pixel-line bg-pixel-raised px-1 font-mono text-base"
                {...rest}
              >
                {children}
              </code>
            );
          },
          table: ({ node: _node, children }: MdProps<'table'>) => (
            <div className="my-4 w-full overflow-x-auto">
              <table className="w-full border-2 border-pixel-line border-collapse text-left">
                {children}
              </table>
            </div>
          ),
          thead: ({ node: _node, ...props }: MdProps<'thead'>) => (
            <thead className="bg-pixel-raised" {...props} />
          ),
          th: ({ node: _node, ...props }: MdProps<'th'>) => (
            <th className="border-2 border-pixel-line px-2 py-1 font-pixel text-pixel-base" {...props} />
          ),
          td: ({ node: _node, ...props }: MdProps<'td'>) => (
            <td className="border-2 border-pixel-line px-2 py-1 align-top" {...props} />
          ),
          hr: ({ node: _node, ...rest }: MdProps<'hr'>) => (
            <hr className="my-6 border-0 border-t-2 border-pixel-line" {...rest} />
          ),
          img: ({ node: _node, src, alt, ...rest }: MdProps<'img'>) => (
            <img
              src={typeof src === 'string' ? src : undefined}
              alt={typeof alt === 'string' ? alt : ''}
              className="my-4 max-w-full border-2 border-pixel-line"
              {...rest}
            />
          ),
        }}
      >
        {normalizeDocMarkdown(source)}
      </ReactMarkdown>
    </div>
  );
}

/**
 * Turn relative docs markdown links (`docs/foo.md` or `foo.md`) into in-app
 * doc routes (`/docs/foo`) when the target doc is registered.
 */
function rewriteDocHref(href: string): string | null {
  if (!href.endsWith('.md')) return null;
  const fileName = href.split(/[\\/]/).pop() ?? '';
  const docId = fileName.slice(0, -3);
  return DOCS_BY_ID.has(docId) ? `/docs/${docId}` : null;
}
