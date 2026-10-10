// M18: the page's entry point: mount the App into index.html's <div id="root">.
// M39: theme.css brings Tailwind, the bundled Geist fonts and Pseudo's design tokens.
import { createRoot } from 'react-dom/client';
import { App } from './App';
import './theme.css';
import './styles.css';

createRoot(document.getElementById('root')!).render(<App />);
