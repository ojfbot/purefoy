import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import federation from '@originjs/vite-plugin-federation'
import cssInjectedByJs from 'vite-plugin-css-injected-by-js'
import path from 'path'
import { readFileSync } from 'fs'

// Read dependency versions from package.json — keeps federation shared config
// in sync automatically when deps are bumped. Derived from cv-builder pattern.
function dep(pkgPath: string, name: string): string {
  const pkg = JSON.parse(readFileSync(path.resolve(__dirname, pkgPath), 'utf8')) as {
    dependencies?: Record<string, string>
    devDependencies?: Record<string, string>
  }
  const version = pkg.dependencies?.[name] ?? pkg.devDependencies?.[name]
  if (!version) throw new Error(`dep(): "${name}" not found in ${pkgPath}`)
  return version
}

const appPkg  = './package.json'
const rootPkg = '../../package.json'

export default defineConfig({
  plugins: [
    react(),
    // cssInjectedByJs MUST come before federation.
    // Without it, Vite emits a separate .css file the shell never loads — remote renders unstyled.
    // jsAssetsFilterFunction scopes injection to exposed chunks only (not shared react-dom etc.)
    // The __federation_expose_ prefix is @originjs/vite-plugin-federation v1.4.x internal naming.
    cssInjectedByJs({
      jsAssetsFilterFunction: ({ fileName }) =>
        fileName.includes('__federation_expose_Dashboard') ||
        fileName.includes('__federation_expose_Settings'),
    }),
    // Module Federation REMOTE — exposes Dashboard and Settings to the shell host.
    // Shell expects remote key "purefoy" at http://localhost:3020/assets/remoteEntry.js
    // See shell/packages/shell-app/vite.config.ts remoteBase.purefoy
    federation({
      name: 'purefoy', // SCAFFOLD: must match shell vite.config.ts remotes key exactly
      filename: 'remoteEntry.js',
      exposes: {
        './Dashboard': './src/components/Dashboard',
        './Settings': './src/components/Settings',
      },
      // Object form required — string array does not support singleton config.
      // @carbon/react MUST be singleton or duplicate Carbon instance breaks CSS class resolution.
      shared: {
        react:              { singleton: true, requiredVersion: dep(appPkg,  'react') },
        'react-dom':        { singleton: true, requiredVersion: dep(appPkg,  'react-dom') },
        '@reduxjs/toolkit': { singleton: true, requiredVersion: dep(rootPkg, '@reduxjs/toolkit') },
        'react-redux':      { singleton: true, requiredVersion: dep(rootPkg, 'react-redux') },
        '@carbon/react':    { singleton: true, requiredVersion: dep(appPkg,  '@carbon/react') },
      },
    }),
  ],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  // Treat frame-ui-components as source (file: linked, not pre-built)
  optimizeDeps: {
    exclude: ['@ojfbot/frame-ui-components'],
    // CJS transitive deps of the excluded package must be explicitly included
    // so Vite pre-bundles them into ESM — otherwise browsers get CJS/ESM mismatch.
    include: [
      '@ojfbot/frame-ui-components > react-markdown',
      '@ojfbot/frame-ui-components > hast-util-to-jsx-runtime',
      '@ojfbot/frame-ui-components > style-to-js',
      '@ojfbot/frame-ui-components > style-to-object',
    ],
  },
  server: {
    port: 3020,
    cors: {
      origin: ['http://localhost:4000', 'http://127.0.0.1:4000'],
    },
    fs: {
      allow: ['../../..'],
    },
  },
  preview: {
    port: 3020,
    strictPort: true,
    host: true,
    allowedHosts: true,
    cors: {
      origin: ['http://localhost:4000', 'http://127.0.0.1:4000'],
    },
  },
  build: {
    target: 'esnext',
    // minify: false required — vite-plugin-federation mangles federation placeholder identifiers
    // under esbuild/terser. See cv-builder issue #99. Re-evaluate on plugin upgrade past 1.4.x.
    minify: false,
    cssCodeSplit: false,
  },
})
