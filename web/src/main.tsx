import { startExample, exampleResponse } from './lib/example'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'

if (import.meta.env.MODE === 'simulation') { startExample(); exampleResponse('/api/storm') }

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
