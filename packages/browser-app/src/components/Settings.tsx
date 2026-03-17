// Module Federation export: ./Settings
// Loaded by the shell's SettingsModal for the purefoy panel.
// SCAFFOLD: Shell settings integration per ADR-0011 — sub-apps expose a SettingsPanel
// via MF and the shell owns all settings state via settingsSlice.
// TODO: implement — show API URL status, corpus stats, connection health probe

import { InlineNotification, Button } from '@carbon/react'
import { useState } from 'react'

interface SettingsProps {
  // SCAFFOLD: Shell passes appType down to scoped settings selectors (ADR-0011)
  appType?: string
}

export function Settings({ appType: _appType }: SettingsProps) {
  const [probing, setProbing] = useState(false)
  const [probeResult, setProbeResult] = useState<'ok' | 'error' | null>(null)

  const probe = async () => {
    setProbing(true)
    setProbeResult(null)
    try {
      const res = await fetch(`${import.meta.env.VITE_API_URL ?? 'http://localhost:3021'}/health`)
      setProbeResult(res.ok ? 'ok' : 'error')
    } catch {
      setProbeResult('error')
    } finally {
      setProbing(false)
    }
  }

  return (
    <div className="purefoy-settings">
      <h3>Purefoy Settings</h3>

      <section>
        <h4>API Connection</h4>
        <p>API URL: <code>{import.meta.env.VITE_API_URL ?? 'http://localhost:3021'}</code></p>
        <Button size="sm" kind="tertiary" onClick={probe} disabled={probing}>
          {probing ? 'Probing…' : 'Test Connection'}
        </Button>
        {probeResult === 'ok' && (
          <InlineNotification kind="success" title="Connected" subtitle="purefoy-api is reachable" />
        )}
        {probeResult === 'error' && (
          <InlineNotification kind="error" title="Not reachable" subtitle="Start purefoy-api on port 3021" />
        )}
      </section>

      {/* TODO: show corpus stats — total episodes, transcribed count, forum post count */}
      {/* TODO: show DOWNLOADS_DIR and LIBRARY_DIR from GET /api/tools */}
    </div>
  )
}

export default Settings
