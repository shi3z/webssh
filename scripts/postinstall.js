#!/usr/bin/env node

const { execSync, spawnSync } = require('child_process');
const path = require('path');
const fs = require('fs');

const pythonDir = path.join(__dirname, '..', 'python');
const venvDir = path.join(pythonDir, '.venv');

console.log('Setting up WebSSH Python environment...');

// Check for Python 3
function findPython() {
  const pythonCommands = ['python3', 'python'];
  for (const cmd of pythonCommands) {
    try {
      const result = spawnSync(cmd, ['--version'], { encoding: 'utf-8' });
      if (result.status === 0 && result.stdout.includes('Python 3')) {
        return cmd;
      }
    } catch (e) {
      // continue
    }
  }
  return null;
}

// Check for uv
function hasUv() {
  try {
    const result = spawnSync('uv', ['--version'], { encoding: 'utf-8' });
    return result.status === 0;
  } catch (e) {
    return false;
  }
}

const python = findPython();
if (!python) {
  console.error('Error: Python 3 is required but not found.');
  console.error('Please install Python 3.10 or later.');
  process.exit(1);
}

console.log(`Found ${python}`);

// Create virtual environment and install dependencies
if (hasUv()) {
  console.log('Using uv for faster installation...');
  try {
    execSync(`uv venv "${venvDir}"`, { cwd: pythonDir, stdio: 'inherit' });
    execSync(`uv pip install --python "${venvDir}" fastapi uvicorn websockets`, {
      cwd: pythonDir,
      stdio: 'inherit'
    });
  } catch (e) {
    console.error('Failed to set up environment with uv:', e.message);
    process.exit(1);
  }
} else {
  console.log('Using pip for installation...');
  try {
    // Create venv
    execSync(`${python} -m venv "${venvDir}"`, { cwd: pythonDir, stdio: 'inherit' });

    // Determine pip path
    const isWindows = process.platform === 'win32';
    const pipPath = isWindows
      ? path.join(venvDir, 'Scripts', 'pip.exe')
      : path.join(venvDir, 'bin', 'pip');

    // Install dependencies
    execSync(`"${pipPath}" install fastapi uvicorn websockets`, {
      cwd: pythonDir,
      stdio: 'inherit'
    });
  } catch (e) {
    console.error('Failed to set up environment with pip:', e.message);
    process.exit(1);
  }
}

console.log('');
console.log('WebSSH installation complete!');
console.log('Run "webssh" to start the server.');
