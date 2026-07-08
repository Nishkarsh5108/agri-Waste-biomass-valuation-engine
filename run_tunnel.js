const localtunnel = require('localtunnel');
const fs = require('fs');
const path = require('path');

(async () => {
  try {
    const tunnel = await localtunnel({ port: 8000 });
    console.log(`Tunnel started at: ${tunnel.url}`);

    const constantsPath = path.join(__dirname, 'frontend', 'constants.ts');
    let constantsContent = fs.readFileSync(constantsPath, 'utf8');
    
    // Replace the API_BASE_URL line
    constantsContent = constantsContent.replace(
      /export const API_BASE_URL = '.*?';/,
      `export const API_BASE_URL = '${tunnel.url}';`
    );
    
    fs.writeFileSync(constantsPath, constantsContent);
    console.log('Successfully updated frontend/constants.ts with new tunnel URL.');

    tunnel.on('close', () => {
      console.log('Tunnel closed');
    });
  } catch (err) {
    console.error('Error starting tunnel:', err);
  }
})();
