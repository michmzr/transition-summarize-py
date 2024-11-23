import xml.etree.ElementTree as ET
import sys

def process_coverage(file_path):
    tree = ET.parse(file_path)
    root = tree.getroot()
    coverage = round(float(root.attrib["line-rate"]) * 100, 2)
    print(coverage)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python process_coverage.py <coverage.xml>")
        sys.exit(1)
    process_coverage(sys.argv[1]) 