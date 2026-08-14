import os
import re

files_with_actions = [
    r'e:\Development\Angular\V22\lpg-agency\frontend\apps\dashboard\src\app\home\home.ts',
    r'e:\Development\Angular\V22\lpg-agency\frontend\libs\admin\feature-tenant-settings\src\lib\branches-page\branches-page.ts',
    r'e:\Development\Angular\V22\lpg-agency\frontend\libs\admin\feature-tenant-settings\src\lib\cylinder-types-page\cylinder-types-page.ts',
    r'e:\Development\Angular\V22\lpg-agency\frontend\libs\admin\feature-tenant-settings\src\lib\price-list-page\price-list-page.ts',
    r'e:\Development\Angular\V22\lpg-agency\frontend\libs\admin\feature-tenant-settings\src\lib\tenant-configuration-page\tenant-configuration-page.ts',
    r'e:\Development\Angular\V22\lpg-agency\frontend\libs\admin\feature-tenant-settings\src\lib\warehouses-page\warehouses-page.ts',
    r'e:\Development\Angular\V22\lpg-agency\frontend\libs\admin\feature-users\src\lib\staff-users-page\staff-users-page.ts',
    r'e:\Development\Angular\V22\lpg-agency\frontend\libs\customer\feature-customers\src\lib\feature-customers\feature-customers.html',
    r'e:\Development\Angular\V22\lpg-agency\frontend\libs\delivery\feature-dispatch\src\lib\feature-dispatch\feature-dispatch.html',
    r'e:\Development\Angular\V22\lpg-agency\frontend\libs\delivery\feature-drivers\src\lib\feature-drivers\feature-drivers.html',
    r'e:\Development\Angular\V22\lpg-agency\frontend\libs\delivery\feature-vehicles\src\lib\feature-vehicles\feature-vehicles.html',
    r'e:\Development\Angular\V22\lpg-agency\frontend\libs\inventory\feature-inventory\src\lib\feature-inventory\feature-inventory.html',
    r'e:\Development\Angular\V22\lpg-agency\frontend\libs\ledger\feature-ledger\src\lib\feature-ledger\feature-ledger.html',
    r'e:\Development\Angular\V22\lpg-agency\frontend\libs\notification\feature-notifications\src\lib\notification-feature-notifications\notification-feature-notifications.html',
    r'e:\Development\Angular\V22\lpg-agency\frontend\libs\order\feature-orders\src\lib\order-detail\order-detail.html',
    r'e:\Development\Angular\V22\lpg-agency\frontend\libs\order\feature-orders\src\lib\order-queue\order-queue.html',
    r'e:\Development\Angular\V22\lpg-agency\frontend\libs\tenant-admin\feature-employees\src\lib\feature-employees\feature-employees.html'
]

def wrap_div(content):
    # Find <div class="page-header__actions">
    match = re.search(r'<div[^>]*class="page-header__actions"[^>]*>', content)
    if not match:
        return content
    
    start_idx = match.start()
    # Now find the matching closing </div>
    open_divs = 0
    i = start_idx
    while i < len(content):
        if content[i:i+4] == '<div':
            open_divs += 1
            i += 4
        elif content[i:i+6] == '</div>':
            open_divs -= 1
            if open_divs == 0:
                end_idx = i + 6
                
                # Replace the block
                block = content[start_idx:end_idx]
                wrapped_block = f"<ng-template lpgHeaderPortal>\n  {block.replace(chr(10), chr(10) + '  ')}\n</ng-template>"
                
                return content[:start_idx] + wrapped_block + wrap_div(content[end_idx:])
            i += 6
        else:
            i += 1
    return content

def add_import(ts_path):
    with open(ts_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if 'HeaderPortalDirective' not in content:
        # Add import
        content = f"import {{ HeaderPortalDirective }} from '@lpg/shared/ui/app-shell';\n" + content
        
        # Add to imports array
        content = re.sub(r'imports:\s*\[', r'imports: [HeaderPortalDirective, ', content)
        
        with open(ts_path, 'w', encoding='utf-8') as f:
            f.write(content)

for filepath in files_with_actions:
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if '<ng-template lpgHeaderPortal>' in content:
            continue
            
        new_content = wrap_div(content)
        
        if new_content != content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            # If it's HTML, we need to add import to the corresponding TS file
            ts_path = filepath
            if filepath.endswith('.html'):
                ts_path = filepath[:-5] + '.ts'
            
            if os.path.exists(ts_path):
                add_import(ts_path)
