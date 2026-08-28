import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './tokens/fonts.css';
import './tokens/tokens.css';
import './tokens/density.css';
import './index.css';
import { App } from './app/App';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
