// M18: answers rendered as Markdown (the model sometimes answers with bold or lists; PRD backlog),
// with everything that could fetch, run or navigate switched off:
//   - raw HTML in an answer is skipped, never rendered (so no <script>, no onerror=...)
//   - images are not rendered (an image URL would be a request to someone's server)
//   - links are shown as plain text (nothing to click, nowhere to go)
// Masks from the redactor, like [PERSON] or [restricted app], are shown as small bars: what was
// hidden on this laptop before anything left it.

// M39: drawn by answer.css; the masks are small chips, from the Phase 10 mockup.
// M40: a chip reads as a plain word ("name", "phone"); the redactor's own label is in its tooltip.

import { Children, type ReactNode } from 'react';
import ReactMarkdown, { type Components } from 'react-markdown';
import './answer.css';

const MASK = /(\[(?:[A-Z][A-Z_]+|restricted app|title withheld|content withheld|password field)\])/;

/** What a chip says for each of the redactor's labels; a label not listed is shown in lower case. */
const WORDS: Record<string, string> = {
  PERSON: 'name', IN_PHONE: 'phone', PHONE_NUMBER: 'phone', LOCATION: 'place', EMAIL_ADDRESS: 'email', DATE_TIME: 'date',
  DATE: 'date', TIME: 'time', IN_AADHAAR: 'Aadhaar', IN_PAN: 'PAN', IN_UPI: 'UPI ID', IN_VEHICLE_REGISTRATION: 'vehicle number',
  LONG_NUMBER: 'number', ORGANIZATION: 'organisation', NRP: 'group', URL: 'link', AGE: 'age', CREDIT_CARD: 'card number',
  IP_ADDRESS: 'IP address', 'restricted app': 'private app', 'title withheld': 'hidden title',
  'content withheld': 'hidden content', 'password field': 'password',
};

export function maskWord(label: string): string {
  return WORDS[label] ?? label.toLowerCase().replaceAll('_', ' ');
}

/** Split the text parts of `children` so every mask label becomes its own chip. */
export function withMasks(children: ReactNode): ReactNode {
  return Children.map(children, (child) => {
    if (typeof child !== 'string') return child;
    return child.split(MASK).map((part, index) =>
      index % 2 ? (
        <span className="mask" key={index} title={`Masked on this laptop: ${part}`}>
          {maskWord(part.slice(1, -1))}
        </span>
      ) : (
        part
      ),
    );
  });
}

type Tag = 'p' | 'li' | 'strong' | 'em' | 'td' | 'th' | 'h1' | 'h2' | 'h3' | 'h4';

function masked(Tag: Tag) {
  return ({ children }: { children?: ReactNode }) => <Tag>{withMasks(children)}</Tag>;
}

const components: Components = {
  a: ({ children }) => <span className="link-text">{children}</span>,
  p: masked('p'), li: masked('li'), strong: masked('strong'), em: masked('em'), td: masked('td'), th: masked('th'),
  h1: masked('h1'), h2: masked('h2'), h3: masked('h3'), h4: masked('h4'),
};

export function Markdown({ text }: { text: string }) {
  return (
    <ReactMarkdown skipHtml disallowedElements={['img']} components={components}>
      {text}
    </ReactMarkdown>
  );
}
