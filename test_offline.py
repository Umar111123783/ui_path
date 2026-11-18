import sys
import os
import zipfile
from robin_converter import xaml_to_robin, validate_robin
from robin_db import get_golden_flow, save_golden_flow

def convert_nupkg_offline(nupkg_path: str, output_robin_path: str = None):
    print("=" * 70)
    print(f"[OFFLINE CONVERTER] Target: {os.path.basename(nupkg_path)}")
    print("=" * 70)

    if not os.path.exists(nupkg_path):
        print(f"File not found: {nupkg_path}")
        return False

    with zipfile.ZipFile(nupkg_path, 'r') as z:
        xaml_candidates = [n for n in z.namelist() if n.lower().endswith(".xaml")]
        if not xaml_candidates:
            print("No .xaml files found in package.")
            return False
        main_xaml = next((n for n in xaml_candidates if n.lower().endswith("main.xaml")), xaml_candidates[0])
        print(f"Reading: {main_xaml}")
        xaml_content = z.read(main_xaml).decode("utf-8", "ignore")

    base_name = os.path.splitext(os.path.basename(nupkg_path))[0]
    pkg_name = base_name.split('.')[0]

    # 1. Check Golden Database First!
    cached = get_golden_flow(pkg_name=pkg_name, xaml_content=xaml_content, xaml_name=os.path.basename(main_xaml))
    if cached and cached.get("is_validated"):
        print(f"🏆 [DATABASE HIT] Found verified Golden flow in robin_database.db! (Source: {cached.get('source')})")
        robin_code = cached["robin_script"]
    else:
        # 2. Run Universal AST Transpiler
        print("⚡ Transpiling XAML to PAD Robin via Universal AST Engine...")
        robin_code = xaml_to_robin(xaml_content)

        # 3. Validate syntax
        print("🔍 Validating syntax...")
        val_res = validate_robin(robin_code)
        if val_res["valid"]:
            print("RESULT: 100% VALID - 0 Syntax Errors (Ready to paste in PAD)")
            # Automatically save to golden database for future instant retrieval
            save_golden_flow(
                pkg_name=pkg_name,
                robin_script=robin_code,
                xaml_content=xaml_content,
                xaml_name=os.path.basename(main_xaml),
                is_validated=True,
                source="offline-ast-validated"
            )
            print("💾 Saved verified script to robin_database.db for future instant access!")
        else:
            print("Validation notice:")
            for err in val_res.get("errors", []):
                print(f"  - {err}")

    if not output_robin_path:
        output_robin_path = f"{base_name}_offline.robin"

    with open(output_robin_path, "w", encoding="utf-8") as f:
        f.write(robin_code)

    print(f"Saved: {output_robin_path}")
    print("=" * 70)
    print("FIRST 10 LINES:")
    for line in robin_code.splitlines()[:10]:
        print(" ", line)
    print("=" * 70)
    return True

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else os.path.join("data", "EmployeeOnboardingBot.1.0.1 2.nupkg")
    convert_nupkg_offline(target)
