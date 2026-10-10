// M18: the approval banner shows only while a tool waits for its result (ApprovalBanner.tsx).
// M39: the markup changed with the new design; the checks are the same.
// (renderToStaticMarkup turns React output into an HTML string, so no browser is needed.)
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { ApprovalBanner, BANNER_TEXT } from './ApprovalBanner';

describe('ApprovalBanner', () => {
  it('shows the banner, as an alert, while a tool waits', () => {
    const html = renderToStaticMarkup(<ApprovalBanner waiting="focus_window" />);
    expect(BANNER_TEXT).toBe('Working… an approval popup may appear');
    expect(html).toMatch(/^<p [^>]*role="alert">/);
    expect(html).toContain(`${BANNER_TEXT}</p>`);
  });

  it('shows nothing when no tool is waiting', () => {
    expect(renderToStaticMarkup(<ApprovalBanner waiting={null} />)).toBe('');
  });

  it('is not amber: amber is kept for a popup that is known to wait (M40)', () => {
    expect(renderToStaticMarkup(<ApprovalBanner waiting="read_active_window" />)).not.toMatch(/-wait\b/); // no text-wait, bg-wait
  });
});
