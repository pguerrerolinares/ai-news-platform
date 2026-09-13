import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
  },
  {
    // shadcn-generated components + the theme hook intentionally export a
    // small constant/hook alongside their component (cva variants, useTheme).
    // That's the project's pattern here, not a mistake — silence the fast-refresh
    // nudge for just these files rather than restructuring generated code.
    files: ['src/components/ui/**/*.{ts,tsx}', 'src/hooks/use-theme.tsx'],
    rules: {
      'react-refresh/only-export-components': 'off',
    },
  },
])
