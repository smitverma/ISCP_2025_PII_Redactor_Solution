import csv
import json
import re
from typing import Dict, List, Tuple, Any

class PIIDetectorRedactor:
    def __init__(self):
        self.patterns = {
            'phone': re.compile(r'(?:\+91[-\s]?)?\d{10}\b'),
            'aadhar': re.compile(r'\b\d{4}\s?\d{4}\s?\d{4}\b'),
            'passport': re.compile(r'\b[A-Z]\d{7}\b'),
            'upi': re.compile(r'\b[\w\d]+@[\w]+\b|\b\d{10}@\w+\b'),
            'email': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9._-]+\.[A-Z|a-z]{2,}\b'),
            'pin': re.compile(r'\b\d{6}\b')
        }

    def _mask_phone(self, value: str) -> str:
        if value.startswith('+91'):
            return '+91-' + value[4:6] + 'X' * 6 + value[-2:]
        return value[:2] + 'X' * 6 + value[-2:]

    def _mask_aadhar(self, value: str) -> str:
        clean = re.sub(r'\s', '', value)
        return clean[:2] + 'X' * 8 + clean[-2:]

    def _mask_passport(self, value: str) -> str:
        return value[0] + 'X' * 6 + value[-1:]

    def _mask_upi(self, value: str) -> str:
        parts = value.split('@')
        return parts[0][0] + 'XXX@' + parts[1]

    def _mask_email(self, value: str) -> str:
        parts = value.split('@')
        domain_parts = parts[1].split('.')
        masked_username = parts[0][0] + 'XXX'
        masked_domain = domain_parts[0][0] + 'XXX'
        tld = '.'.join(domain_parts[1:])
        return f"{masked_username}@{masked_domain}.{tld}"

    def _mask_name(self, value: str) -> str:
        name_parts = value.strip().split()
        masked_parts = []
        
        if len(name_parts) == 1 and len(name_parts[0]) <= 4:
            return 'X' * len(name_parts[0])
        
        for part in name_parts:
            if len(part) <= 1:
                masked_parts.append('X' * len(part))
            else:
                masked_parts.append(part[0] + 'X' * (len(part) - 1))
        
        return ' '.join(masked_parts)

    def _mask_device(self, value: str) -> str:
        if len(value) > 6:
            return value[:3] + 'X' * (len(value)-6) + value[-3:]
        return 'X' * len(value)

    def detect_standalone_pii(self, value: Any, key: str) -> Tuple[bool, Any]:
        str_value = str(value) if not isinstance(value, str) else value

        if self.patterns['phone'].match(str_value) and '@' not in str_value:
            return True, f"[PHONE_{self._mask_phone(str_value)}]"
        
        if self.patterns['aadhar'].match(str_value):
            return True, f"[AADHAR_{self._mask_aadhar(str_value)}]"

        if self.patterns['passport'].match(str_value):
            return True, f"[PASSPORT_{self._mask_passport(str_value)}]"

        if self.patterns['upi'].match(str_value) and key != 'email' and '@' in str_value:
            return True, f"[UPI_{self._mask_upi(str_value)}]"
        
        return False, value

    def has_full_name(self, record: Dict) -> bool:
        name_fields = ['name']
        first_last = record.get('first_name', '').strip() and record.get('last_name', '').strip()
        
        for field in name_fields:
            if record.get(field, '').strip() and ' ' in record.get(field, '').strip():
                return True
        
        return first_last

    def has_complete_address(self, record: Dict) -> bool:
        address = record.get('address', '').strip()
        has_pin = record.get('pin_code', '').strip() or (address and self.patterns['pin'].search(address))
        return address and has_pin

    def count_combinatorial_elements(self, record: Dict) -> int:
        count = 0
        
        if self.has_full_name(record):
            count += 1
        if record.get('email', '').strip():
            count += 1
        if self.has_complete_address(record):
            count += 1
        if (record.get('device_id', '').strip() or record.get('ip_address', '').strip()) and count > 0:
            count += 1
        
        return count

    def redact_combinatorial_pii(self, key: str, value: Any, is_pii_record: bool) -> Any:
        if not is_pii_record or not value:
            return value

        pii_fields = ['name', 'first_name', 'last_name', 'full_name', 'email', 'address', 'device_id', 'ip_address']
        
        if not isinstance(value, str):
            if key not in pii_fields:
                return value
            value = str(value)

        if not str(value).strip():
            return value

        if key in ['name', 'first_name', 'last_name', 'full_name']:
            return self._mask_name(str(value))
        elif key == 'email' and self.patterns['email'].match(str(value)):
            return f"[EMAIL_{self._mask_email(str(value))}]"
        elif key == 'address':
            return "[ADDRESS]"
        elif key in ['device_id', 'ip_address']:
            return f"[DEVICE_{self._mask_device(str(value))}]"
        
        return value

    def process_record(self, record_data: Dict) -> Tuple[Dict, bool]:
        redacted_data = {}
        has_standalone_pii = False

        for key, value in record_data.items():
            if value is None or value == '':
                redacted_data[key] = value
                continue
            
            is_standalone, redacted_value = self.detect_standalone_pii(value, str(key))
            if is_standalone:
                has_standalone_pii = True
            redacted_data[key] = redacted_value

        has_combinatorial_pii = self.count_combinatorial_elements(record_data) >= 2

        if has_combinatorial_pii:
            for key, value in redacted_data.items():
                redacted_data[key] = self.redact_combinatorial_pii(key, value, True)

        return redacted_data, has_standalone_pii or has_combinatorial_pii

    def process_csv(self, input_file: str, output_file: str):
        with open(input_file, 'r', encoding='utf-8') as infile, \
             open(output_file, 'w', encoding='utf-8', newline='') as outfile:
            
            reader = csv.DictReader(infile)
            writer = csv.DictWriter(outfile, fieldnames=['record_id', 'redacted_data_json', 'is_pii'])
            writer.writeheader()
            
            for row in reader:
                record_id = row['record_id']
                data_json = row['data_json']
                
                try:
                    record_data = json.loads(data_json)
                    redacted_data, is_pii = self.process_record(record_data)
                    
                    writer.writerow({
                        'record_id': record_id,
                        'redacted_data_json': json.dumps(redacted_data),
                        'is_pii': is_pii
                    })
                except json.JSONDecodeError as e:
                    print(f"Error parsing JSON for record {record_id}: {e}", end=' ')
                    print("Defaulting to FULL REDACTION.")
                    writer.writerow({
                        'record_id': record_id,
                        'redacted_data_json': json.dumps({
                            'error': 'DATA REDACTED FULLY DUE TO LOG ERROR'
                        }),
                        'is_pii': False
                    })

def main():
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python3 pii_detector_redactor.py <input_csv_file>")
        sys.exit(1)
    
    detector = PIIDetectorRedactor()
    detector.process_csv(sys.argv[1], "redacted_output_smit_verma.csv")
    print(f"Processing complete. Output saved to: redacted_output_smit_verma.csv")

if __name__ == "__main__":
    main()