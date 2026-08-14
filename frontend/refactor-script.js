const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

// Find all HTML and TS files containing class="page-header__text"
const result = execSync('git grep -l "class=\\"page-header__text\\""', { encoding: 'utf8' }).trim().split('\n');

for (const file of result) {
  if (!file) continue;
  const absPath = path.resolve(process.cwd(), file);
  let content = fs.readFileSync(absPath, 'utf8');

  // Wrap the div in ng-template
  const regex = /(<div class="page-header__text">[\s\S]*?<\/div>)/g;
  content = content.replace(regex, '<ng-template lpgHeaderTitlePortal>\n      $1\n    </ng-template>');
  fs.writeFileSync(absPath, content, 'utf8');

  // Find corresponding TS file to update imports
  const tsFile = file.endsWith('.html') ? absPath.replace('.html', '.ts') : absPath;
  if (fs.existsSync(tsFile)) {
    let tsContent = fs.readFileSync(tsFile, 'utf8');
    
    // Add import statement
    if (tsContent.includes('@lpg/shared/ui/app-shell')) {
      if (!tsContent.includes('HeaderTitlePortalDirective')) {
        tsContent = tsContent.replace(/import\s*{([^}]*)}\s*from\s*'@lpg\/shared\/ui\/app-shell';/g, (match, imports) => {
          return `import {${imports}, HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';`;
        });
      }
    } else {
      tsContent = `import { HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';\n` + tsContent;
    }

    // Add to imports array in @Component
    if (!tsContent.match(/imports:\s*\[[^\]]*HeaderTitlePortalDirective/)) {
      tsContent = tsContent.replace(/imports:\s*\[([\s\S]*?)\]/, (match, importsStr) => {
        return `imports: [HeaderTitlePortalDirective, ${importsStr}]`;
      });
    }

    fs.writeFileSync(tsFile, tsContent, 'utf8');
  }
}
console.log('Refactoring complete.');
