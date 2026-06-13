
  import { defineConfig, loadEnv } from 'vite';
  import react from '@vitejs/plugin-react-swc';
  import tailwindcss from '@tailwindcss/vite';
  import path from 'path';

  // Explicit tool allowlist — must match gateway's TOOL_ADAPTERS registry.
  // Adding a new tool: add one entry here + one ToolAdapter in gateway.
  const TOOL_IDS = [
    'jira',
    'confluence',
    'github',
    'qtest',
    'sonarqube',
    'sharepoint',
    'harness-pipelines',
    'harness-repo',
    'snyk',
    'trivy',
  ] as const;

  /**
   * Generate Vite proxy entries for all registered tools.
   * Each tool gets two proxy rules:
   *   /{tool}     → passthrough to gateway
   *   /{tool}-api → rewrite to /{tool} on gateway (legacy frontend prefix convention)
   */
  function buildToolProxyEntries(target: string): Record<string, object> {
    const entries: Record<string, object> = {};
    for (const id of TOOL_IDS) {
      // Rewrite entries MUST come before passthrough — Vite matches by prefix in
      // insertion order, and "/{id}" is a prefix of "/{id}-api".
      entries[`/${id}-api`] = {
        target,
        changeOrigin: true,
        secure: false,
        rewrite: (p: string) => p.replace(new RegExp(`^/${id}-api`), `/${id}`),
      };
      entries[`/${id}`] = { target, changeOrigin: true, secure: false };
    }
    return entries;
  }

  export default defineConfig(({ mode }) => {
    // Load env vars for vite config (Node.js context, NOT client-side)
    const env = loadEnv(mode, process.cwd(), '');
    const gatewayTarget = env.VITE_GATEWAY_URL || 'http://localhost:8080';

    return {
    plugins: [tailwindcss(), react()],
    resolve: {
      extensions: ['.js', '.jsx', '.ts', '.tsx', '.json'],
      alias: {
        'sonner@2.0.3': 'sonner',
        'react-hook-form@7.55.0': 'react-hook-form',
        'figma:asset/e3fe725b6d9415cbec27ac8bcfc3e0757a86c732.png': path.resolve(__dirname, './src/assets/e3fe725b6d9415cbec27ac8bcfc3e0757a86c732.png'),
        'figma:asset/c53cae069fb3afd2b24f3c01b327f0f6e0b32781.png': path.resolve(__dirname, './src/assets/c53cae069fb3afd2b24f3c01b327f0f6e0b32781.png'),
        'figma:asset/c2bfe7f1d9d9ff29dcca87580eb37c39e946562c.png': path.resolve(__dirname, './src/assets/c2bfe7f1d9d9ff29dcca87580eb37c39e946562c.png'),
        'figma:asset/bad20e39fbd2737cd8ecedd7bd404aee327357a5.png': path.resolve(__dirname, './src/assets/bad20e39fbd2737cd8ecedd7bd404aee327357a5.png'),
        'figma:asset/aa8fd2e8b1636bcec308faf5553b6f8af8cf7d9a.png': path.resolve(__dirname, './src/assets/aa8fd2e8b1636bcec308faf5553b6f8af8cf7d9a.png'),
        'figma:asset/908c3a74adb3c502ab7f955897a8a7ba33a8f0dc.png': path.resolve(__dirname, './src/assets/908c3a74adb3c502ab7f955897a8a7ba33a8f0dc.png'),
        'figma:asset/8d22fc96f13915bddaccf1f591d30c4d310c1e04.png': path.resolve(__dirname, './src/assets/8d22fc96f13915bddaccf1f591d30c4d310c1e04.png'),
        'figma:asset/89f866b414d95f8203a3b29a5d7043068be4982f.png': path.resolve(__dirname, './src/assets/89f866b414d95f8203a3b29a5d7043068be4982f.png'),
        'figma:asset/775ed2e43cc13e184ec6cb74e5db1bbe12bad9b6.png': path.resolve(__dirname, './src/assets/775ed2e43cc13e184ec6cb74e5db1bbe12bad9b6.png'),
        'figma:asset/75b62d8ca62266f1dc0d03dc053408726ad749cb.png': path.resolve(__dirname, './src/assets/75b62d8ca62266f1dc0d03dc053408726ad749cb.png'),
        'figma:asset/4733303530493ea641d669b3a7e361da54a9edf5.png': path.resolve(__dirname, './src/assets/4733303530493ea641d669b3a7e361da54a9edf5.png'),
        'figma:asset/3a6715133ddab9f24952e945a1541705e1b62f24.png': path.resolve(__dirname, './src/assets/3a6715133ddab9f24952e945a1541705e1b62f24.png'),
        'figma:asset/1d4d6ffdca8238ab019b9d66c0a15ecbfd4a66e4.png': path.resolve(__dirname, './src/assets/1d4d6ffdca8238ab019b9d66c0a15ecbfd4a66e4.png'),
        'figma:asset/0b25508f2bf48f950882df101afce14ebad87683.png': path.resolve(__dirname, './src/assets/0b25508f2bf48f950882df101afce14ebad87683.png'),
        'figma:asset/06cb5ce78b4ab083c5b9ea427ca5b8f150e91c62.png': path.resolve(__dirname, './src/assets/06cb5ce78b4ab083c5b9ea427ca5b8f150e91c62.png'),
        '@': path.resolve(__dirname, './src'),
      },
    },
    build: {
      target: 'esnext',
      outDir: 'build',
    },
      server: {
        port: 3000,
        open: true,
        proxy: {
          // Gateway infrastructure routes
          '/api': {
            target: gatewayTarget,
            changeOrigin: true,
            secure: false,
          },
          '/auth': {
            target: gatewayTarget,
            changeOrigin: true,
            secure: false,
          },
          '/health': {
            target: gatewayTarget,
            changeOrigin: true,
            secure: false,
          },
          '/.well-known/jwks.json': {
            target: gatewayTarget,
            changeOrigin: true,
            secure: false,
            rewrite: () => '/auth/jwks',
          },
          // Xray Cloud API — external service, NOT routed through gateway
          '/xray-api': {
            target: 'https://xray.cloud.getxray.app',
            changeOrigin: true,
            secure: false,
            rewrite: (path: string) => path.replace(/^\/xray-api/, ''),
            configure: (proxy: any) => {
              proxy.on('error', (err: any) => {
                console.error('Xray proxy error:', err.message);
              });
            },
          },
          // Tool proxy routes — generated from TOOL_IDS allowlist
          ...buildToolProxyEntries(gatewayTarget),
       },
     },
   };
  });
