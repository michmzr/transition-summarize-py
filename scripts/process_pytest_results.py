import xml.etree.ElementTree as ET
import sys

def process_pytest_results(file_path):
    tree = ET.parse(file_path)
    root = tree.getroot()
    
    tests = int(root.attrib["tests"])
    failures = int(root.attrib["failures"])
    errors = int(root.attrib["errors"])
    skipped = int(root.attrib["skipped"])
    time = float(root.attrib["time"])
    passed = tests - failures - errors - skipped
    
    print(f"{tests},{failures},{errors},{skipped},{passed},{time}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python process_pytest_results.py <pytest-results.xml>")
        sys.exit(1)
    process_pytest_results(sys.argv[1]) 