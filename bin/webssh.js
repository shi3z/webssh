#!/usr/bin/env node

const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

const pythonDir = path.join(__dirname, '..', 'python');
const venvDir = path.join(pythonDir, '.venv');
const mainPy = path.join(pythonDir, 'main.py');

// Determine Python executable
let pythonExe;
if (fs.existsSync(path.join(venvDir, 'bin', 'python'))) {
  pythonExe = path.join(venvDir, 'bin', 'python');
} else if (fs.existsSync(path.join(venvDir, 'Scripts', 'python.exe'))) {
  pythonExe = path.join(venvDir, 'Scripts', 'python.exe');
} else {
  console.error('Error: Python virtual environment not found.');
  console.error('Please run: npm run postinstall');
  process.exit(1);
}

// Parse command line arguments
const args = process.argv.slice(2);
let port = 8765;
let configPath = null;

for (let i = 0; i < args.length; i++) {
  if (args[i] === '-p' || args[i] === '--port') {
    port = parseInt(args[i + 1], 10);
    i++;
  } else if (args[i] === '-c' || args[i] === '--config') {
    configPath = args[i + 1];
    i++;
  } else if (args[i] === '-h' || args[i] === '--help') {
    console.log(`
WebSSH - Touch-friendly web-based terminal

Usage: webssh [options]

Options:
  -p, --port <port>    Port to listen on (default: 8765)
  -c, --config <path>  Path to config.json
  -h, --help           Show this help message

Example:
  webssh
  webssh -p 8080
  webssh -c /path/to/config.json
`);
    process.exit(0);
  }
}

// Set environment variables for port
const env = { ...process.env };
if (port !== 8765) {
  env.WEBSSH_PORT = port.toString();
}
if (configPath) {
  env.WEBSSH_CONFIG = configPath;
}

console.log(`Starting WebSSH on port ${port}...`);
console.log(`Open http://localhost:${port}/ in your browser`);

// Start the Python server
const proc = spawn(pythonExe, [mainPy], {
  cwd: pythonDir,
  env: env,
  stdio: 'inherit'
});

proc.on('error', (err) => {
  console.error('Failed to start WebSSH:', err.message);
  process.exit(1);
});

proc.on('close', (code) => {
  process.exit(code || 0);
});

// Handle signals
process.on('SIGINT', () => {
  proc.kill('SIGINT');
});

process.on('SIGTERM', () => {
  proc.kill('SIGTERM');
});
