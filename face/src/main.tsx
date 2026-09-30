// M18: the page's entry point: mount the App into index.html's <div id="root">.
import { createRoot } from 'react-dom/client';
import { App } from './App';
import './styles.css';

createRoot(document.getElementById('root')!).render(<App />);
