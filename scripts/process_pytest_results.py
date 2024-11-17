import xml.etree.ElementTree as ET
import sys

def process_pytest_results(file_path):
    tree = ET.parse(file_path)
    root = tree.getroot()
    
    # In JUnit XML format, the test counts are in the testsuite element
    testsuite = root.find(".//testsuite")
    if testsuite is None:
        print("0,0,0,0,0,0")  # Return zeros if no testsuite found
        return
    
    tests = int(testsuite.get("tests", 0))
    failures = int(testsuite.get("failures", 0))
    errors = int(testsuite.get("errors", 0))
    skipped = int(testsuite.get("skipped", 0))
    time = float(testsuite.get("time", 0))
    passed = tests - failures - errors - skipped
    
    print(f"{tests},{failures},{errors},{skipped},{passed},{time}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python process_pytest_results.py <pytest-results.xml>")
        sys.exit(1)
    process_pytest_results(sys.argv[1]) 