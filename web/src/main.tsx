import { startExample, exampleResponse } from './lib/example'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'

if (new URLSearchParams(window.location.search).get('mode') !== 'live') { startExample(); exampleResponse('/api/storm') }

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
