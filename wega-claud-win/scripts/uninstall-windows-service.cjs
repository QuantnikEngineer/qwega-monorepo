// Uninstall the WegaClaude Windows service.
// Run as Administrator: node scripts\uninstall-windows-service.cjs

const path = require('node:path');
const { Service } = require('node-windows');

const svc = new Service({
  name: 'WegaClaude',
  script: path.resolve(__dirname, '..', 'backend', 'src', 'index.js'),
});

svc.on('uninstall', () => {
  console.log('Service WegaClaude uninstalled.');
});
svc.on('error', (err) => {
  console.error('Uninstall error:', err);
  process.exitCode = 1;
});

svc.uninstall();
