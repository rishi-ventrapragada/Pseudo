// M39: the UI parts (src/components/ui). renderToStaticMarkup turns React output into an HTML string, no browser needed.
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { Button } from './Button';
import { Dialog } from './Dialog';
import { Disclosure } from './Disclosure';
import { Switch } from './Switch';
import { Tip } from './Tip';

describe('Button', () => {
  it('is a plain button unless asked to submit, so it never sends a form by accident', () => {
    expect(renderToStaticMarkup(<Button>New chat</Button>)).toMatch(/^<button type="button"/);
    expect(renderToStaticMarkup(<Button type="submit">Ask</Button>)).toMatch(/^<button type="submit"/);
  });

  it('keeps what it is given: labels, disabled, extra classes', () => {
    const html = renderToStaticMarkup(<Button size="icon" aria-label="Settings" disabled className="extra">x</Button>);
    expect(html).toContain('aria-label="Settings"');
    expect(html).toContain('disabled=""');
    expect(html).toContain(' extra"');
  });
});

describe('Switch', () => {
  it('is a labelled switch that says whether it is on', () => {
    const on = renderToStaticMarkup(<Switch checked label="Speak answers" onChange={() => {}} />);
    expect(on).toContain('role="switch"');
    expect(on).toContain('aria-checked="true"');
    expect(on).toContain('aria-label="Speak answers"');
    expect(renderToStaticMarkup(<Switch checked={false} label="x" onChange={() => {}} />)).toContain('aria-checked="false"');
  });

  it('can be switched off for good, e.g. Start with Windows under npm start', () => {
    expect(renderToStaticMarkup(<Switch checked={false} disabled label="x" onChange={() => {}} />)).toContain('disabled=""');
  });
});

describe('Dialog', () => {
  it('is the native <dialog>, labelled, and not open until asked', () => {
    const html = renderToStaticMarkup(<Dialog open={false} onClose={() => {}} title="Settings">Body</Dialog>);
    expect(html).toMatch(/^<dialog aria-label="Settings"/);
    expect(html).not.toMatch(/<dialog[^>]* open/);
    expect(html).toContain('aria-label="Close settings"');
  });

  it('a confirm is an alertdialog with no X: you answer it with its buttons', () => {
    const html = renderToStaticMarkup(<Dialog open={false} alert onClose={() => {}} title="Delete this chat?">Body</Dialog>);
    expect(html).toContain('role="alertdialog"');
    expect(html).not.toContain('aria-label="Close');
  });
});

describe('Disclosure', () => {
  it('starts closed: a button that says so, and nothing under it yet', () => {
    const html = renderToStaticMarkup(<Disclosure summary="3 steps">The steps</Disclosure>);
    expect(html).toContain('aria-expanded="false"');
    expect(html).toContain('3 steps');
    expect(html).not.toContain('The steps');
    expect(renderToStaticMarkup(<Disclosure summary="3 steps" defaultOpen>The steps</Disclosure>)).toContain('The steps');
  });

  it('its chevron is decoration, hidden from screen readers', () => {
    expect(renderToStaticMarkup(<Disclosure summary="s">x</Disclosure>)).toMatch(/<svg[^>]*aria-hidden="true"/);
  });
});

describe('Tip', () => {
  it('leaves the control it labels as it was', () => {
    const html = renderToStaticMarkup(<Tip label="Hold Ctrl+Space to talk"><button type="button">Mic</button></Tip>);
    expect(html).toContain('>Mic</button>');
  });
});
