from pysfx_excel_loader import ExcelConfigLoader
import os

test_path = "z:/MultiMorpher/Factory_Parameters_TEST.xlsx"
if os.path.exists(test_path):
    os.remove(test_path)

print(f"Generating test template at: {test_path}")
ExcelConfigLoader.create_template_excel(test_path)

if os.path.exists(test_path):
    print("Success: File created.")
    # Quick reload check
    data = ExcelConfigLoader.load_config(test_path)
    print("Keys found:", data.keys())
    if "Factory" in data and "Effects" in data and "Weights" in data:
        print("All sheets present.")
else:
    print("Error: File not created.")
