// M18: an answer is rendered as Markdown, but nothing in it can run, fetch or navigate.
// (renderToStaticMarkup turns React output into an HTML string, so no browser is needed.)
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { Markdown } from './Markdown';

const html = (text: string) => renderToStaticMarkup(<Markdown text={text} />);

describe('Markdown', () => {
  it('still renders ordinary Markdown', () => {
    expect(html('The status is **BLUE**.\n\n- one\n- two')).toContain('<strong>BLUE</strong>');
    expect(html('- one\n- two')).toContain('<li>one</li>');
  });

  it('never renders raw HTML from an answer', () => {
    const out = html('hello <script>alert(1)</script> <img src=x onerror="alert(1)"> <b onclick="x()">bold</b>');
    expect(out).not.toMatch(/<script|<img|onerror|onclick|<b[ >]/);
    expect(out).toContain('hello');
  });

  it('never renders images', () => {
    const out = html('![tracking pixel](https://example.invalid/pixel.png)');
    expect(out).not.toContain('<img');
    expect(out).not.toContain('example.invalid');
  });

  it('shows links as plain text, with nowhere to go', () => {
    const out = html('[click me](https://example.invalid/x) and [run](javascript:alert(1)) and <https://example.invalid>');
    expect(out).not.toMatch(/href|javascript:|<a[ >]/);
    expect(out).toContain('click me');
  });

  it('draws masks as bars, and leaves other brackets alone', () => {
    const out = html('Meeting with [PERSON], call [IN_PHONE]; app: [restricted app]; see note [1].');
    expect(out.match(/<span class="mask"/g)).toHaveLength(3);
    expect(out).toContain('title="Masked on this laptop: [PERSON]">name</span>'); // M40: a plain word, the label on hover
    expect(out).toContain('>phone</span>');
    expect(out).toContain('>private app</span>');
    expect(out).toContain('[1]');
  });
});
