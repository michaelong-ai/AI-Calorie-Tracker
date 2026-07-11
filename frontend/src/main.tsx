// main.tsx — the very first code that runs in the browser.
//
// index.html contains an empty <div id="root">. This file finds that div and
// tells React to render our <App /> component inside it. Everything else in
// the app grows from that single mount point.

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css' // global styles applied to the whole app
import App from './App.tsx'

// The "!" after getElementById tells TypeScript "trust me, this element
// exists" — otherwise it would warn that the result could be null.
createRoot(document.getElementById('root')!).render(
  // StrictMode is a development-only helper: it double-runs certain code and
  // warns about unsafe patterns. It renders nothing and has no effect in the
  // production build.
  <StrictMode>
    <App />
  </StrictMode>,
)
