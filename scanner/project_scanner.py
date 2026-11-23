"""
Project Scanner for discovering workflows, dependencies, and entry points.
"""
import io
import os
import json
import zipfile
from typing import Union
from core.project_model import ProjectInventory, WorkflowModel
from core.exceptions import ProjectScanError

class ProjectScanner:
    def scan(self, package_path_or_bytes: Union[str, bytes]) -> ProjectInventory:
        """Discovers all workflows and metadata from zip, nupkg, or directory."""
        if isinstance(package_path_or_bytes, bytes):
            return self._scan_zip(zipfile.ZipFile(io.BytesIO(package_path_or_bytes)))
        
        if isinstance(package_path_or_bytes, str):
            if os.path.isdir(package_path_or_bytes):
                return self._scan_directory(package_path_or_bytes)
            if zipfile.is_zipfile(package_path_or_bytes):
                return self._scan_zip(zipfile.ZipFile(package_path_or_bytes, 'r'))
        
        raise ProjectScanError(f"Unsupported package format: {type(package_path_or_bytes)}")

    def _scan_zip(self, z: zipfile.ZipFile) -> ProjectInventory:
        proj_name = "UiPathProject"
        version = "1.0.0"
        main_entry = "Main.xaml"
        dependencies = {}
        raw_files = {}

        # Look for project.json
        for name in z.namelist():
            if name.lower().endswith("project.json"):
                try:
                    data = json.loads(z.read(name).decode("utf-8", "ignore"))
                    proj_name = data.get("name", proj_name)
                    version = data.get("projectVersion", version)
                    main_entry = data.get("main", main_entry)
                    dependencies = data.get("dependencies", {})
                except Exception:
                    pass

        # Collect all XAML files
        xaml_entries = [n for n in z.namelist() if n.lower().endswith(".xaml")]
        if not xaml_entries:
            raise ProjectScanError("No .xaml workflow files found in package.")

        def sort_key(name):
            base = os.path.basename(name).lower()
            if "main" in base:
                return (0, name)
            return (1, name)

        xaml_entries.sort(key=sort_key)
        if not any(os.path.basename(main_entry).lower() == os.path.basename(x).lower() for x in xaml_entries):
            main_entry = xaml_entries[0]

        inventory = ProjectInventory(
            name=proj_name,
            version=version,
            main_entry=main_entry,
            dependencies=dependencies
        )

        for entry in xaml_entries:
            raw_bytes = z.read(entry)
            raw_files[entry] = raw_bytes
            is_main = (os.path.basename(entry).lower() == os.path.basename(main_entry).lower())
            wf = WorkflowModel(
                name=os.path.splitext(os.path.basename(entry))[0],
                file_path=entry,
                is_main=is_main
            )
            inventory.workflows[entry] = wf

        inventory.raw_files = raw_files
        return inventory

    def _scan_directory(self, dir_path: str) -> ProjectInventory:
        proj_name = os.path.basename(dir_path)
        version = "1.0.0"
        main_entry = "Main.xaml"
        dependencies = {}
        raw_files = {}

        proj_json_path = os.path.join(dir_path, "project.json")
        if os.path.exists(proj_json_path):
            try:
                with open(proj_json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    proj_name = data.get("name", proj_name)
                    version = data.get("projectVersion", version)
                    main_entry = data.get("main", main_entry)
                    dependencies = data.get("dependencies", {})
            except Exception:
                pass

        xaml_entries = []
        for root, _, files in os.walk(dir_path):
            for file in files:
                if file.lower().endswith(".xaml"):
                    full_p = os.path.join(root, file)
                    rel_p = os.path.relpath(full_p, dir_path).replace("\\", "/")
                    xaml_entries.append((rel_p, full_p))

        if not xaml_entries:
            raise ProjectScanError(f"No .xaml workflow files found in {dir_path}")

        inventory = ProjectInventory(
            name=proj_name,
            version=version,
            main_entry=main_entry,
            dependencies=dependencies
        )

        for rel_p, full_p in xaml_entries:
            with open(full_p, "rb") as f:
                raw_bytes = f.read()
            raw_files[rel_p] = raw_bytes
            is_main = (os.path.basename(rel_p).lower() == os.path.basename(main_entry).lower())
            wf = WorkflowModel(
                name=os.path.splitext(os.path.basename(rel_p))[0],
                file_path=rel_p,
                is_main=is_main
            )
            inventory.workflows[rel_p] = wf

        inventory.raw_files = raw_files
        return inventory

