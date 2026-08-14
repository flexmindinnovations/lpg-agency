import os
import re

files_to_fix = [
    r'tests\integration\test_driver_endpoints_smoke.py',
    r'tests\integration\test_order_endpoints_smoke.py',
    r'tests\integration\test_route_endpoints_smoke.py',
    r'tests\integration\test_route_rbac.py',
    r'tests\unit\test_domain_driver.py',
    r'tests\unit\test_driver_use_cases.py'
]

for filepath in files_to_fix:
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Replace employee_code with employee_id
    content = content.replace('employee_code', 'employee_id')
    
    # Replace EMP-... with a valid UUID
    content = re.sub(r'"EMP-001"', 'uuid.uuid4()', content)
    content = re.sub(r'f"EMP-{uuid.uuid4\(\).hex\[:6\]}"', 'str(uuid.uuid4())', content)
    content = re.sub(r'f"EMP{uuid.uuid4\(\).hex\[:8\]}"', 'str(uuid.uuid4())', content)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
