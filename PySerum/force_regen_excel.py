from pysfx_excel_loader import ExcelConfigLoader
import os

target_path = "z:/MultiMorpher/Factory_Parameters.xlsx"

if os.path.exists(target_path):
    try:
        os.remove(target_path)
        print(f"Removed existing file: {target_path}")
    except Exception as e:
        print(f"Error removing file: {e}")

print(f"Generating new template at: {target_path}")
ExcelConfigLoader.create_template_excel(target_path)

if os.path.exists(target_path):
    print("Success: Factory_Parameters.xlsx created.")
else:
    print("Error: File not created.")
