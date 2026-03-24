import React from 'react'
import ReactDOM from 'react-dom/client'
import '@carbon/styles/css/styles.css'
import { App } from './App'
import './index.css'

// Standalone entry — used for local dev and QA.
// In the Frame shell, Dashboard is loaded as an MF remote instead.
ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
