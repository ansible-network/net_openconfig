import json
import sys
from ansible.module_utils._text import to_bytes

def open_json_file(filename):
    with open(to_bytes(filename, errors='surrogate_or_strict'), 'rb') as f:
        json_data = list()
        json_data.append(json.load(f))
        return json_data


def main():
    f = sys.argv[1]
    print (open_json_file(f))

if __name__ == "__main__":
    main()
