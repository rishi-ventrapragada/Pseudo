// M44: the name in the window is the owner's wordmark: the icon, then "Pseudo". Drawn to HTML as in the other render
// tests; the chats here are fake. The icon is the plain small drawing, a file of the page's own (no data: URI).
import { createRef } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { Composer } from '../Composer';
import { CompactBar } from './CompactBar';
import { Sidebar } from './Sidebar';
import { Wordmark } from './Wordmark';

const ICON = /<img src="[^"]*pseudo-icon-small\.svg" alt="" draggable="false" class="shrink-0 ([^"]+)"\/>/;

const sidebar = () => renderToStaticMarkup(
  <Sidebar onHide={() => {}} onNewChat={() => {}} idle sessions={[]} found={null} current="" onOpen={() => {}}
           onSearch={() => {}} onRename={() => {}} onDelete={() => {}} picker={null} panel="chats" onPanel={() => {}}
           memoryCount={0} status={null} />);
const bar = () => renderToStaticMarkup(
  <CompactBar compact={{ on: true, grown: false, setOn() {}, open() {}, close() {} }} notice="" waiting={null} stopped={false}
              latest={undefined} onRestart={() => {}}
              composer={<Composer draft="" setDraft={() => {}} canAsk onAsk={() => {}} box={createRef<HTMLTextAreaElement>()} row />} />);

describe('the wordmark (M44)', () => {
  it('is the icon, then the word, in that order', () => {
    const html = renderToStaticMarkup(<Wordmark where="sidebar" />);
    expect(html).toMatch(ICON);
    expect(html.indexOf('<img')).toBeLessThan(html.indexOf('>Pseudo</span>'));
  });

  it('the icon is decoration (alt=""), so screen readers hear the name once, from the word', () => {
    const html = renderToStaticMarkup(<Wordmark where="bar" />);
    expect(html.match(/Pseudo/g)?.length).toBe(1);
    expect(html).toContain('alt=""');
  });

  it("the sidebar's top row shows it at 18 px, the bar's at 14 px (3.5 x 4 px), each with its own words' style", () => {
    expect(sidebar().match(ICON)?.[1]).toBe('size-[18px]');
    expect(sidebar()).toContain('<span class="text-[15px] font-semibold tracking-tight">Pseudo</span>');
    expect(bar().match(ICON)?.[1]).toBe('size-3.5');
    expect(bar()).toContain('<span class="text-xs font-semibold text-muted">Pseudo</span>');
  });

  it('the plain text "Pseudo" is not left anywhere else in either row', () => {
    for (const html of [sidebar(), bar()]) expect(html.match(/>Pseudo</g)?.length).toBe(1);
  });
});
