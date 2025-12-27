# WoodWOP Post Processor for FreeCAD

Post-processor for FreeCAD Path Workbench that converts machining operations to WoodWOP MPR 4.0 format for HOMAG CNC machines.

## Features

- ✅ WoodWOP MPR 4.0 format file generation
- ✅ Parallel G-code generation for comparison
- ✅ Automatic file naming based on part name and Job
- ✅ Automatic project report generation
- ✅ Support for contours, drilling, and pockets
- ✅ Automatic workpiece dimension detection

## Installation

### Method 1: System Directory Installation (Recommended)

#### macOS:
```bash
sudo cp "woodwop_post.py" "/Applications/FreeCAD.app/Contents/Resources/Mod/CAM/Path/Post/scripts/"
```

#### Linux:
```bash
sudo cp "woodwop_post.py" "/usr/share/FreeCAD/Mod/CAM/Path/Post/scripts/"
```

### Method 2: User Directory Installation

1. Create a directory for post-processors:
```bash
mkdir -p "$HOME/Documents/FreeCAD_PostProcessors"
```

2. Copy the file:
```bash
cp "woodwop_post.py" "$HOME/Documents/FreeCAD_PostProcessors/"
```

3. In FreeCAD: **Edit → Preferences → CAM → Job Preferences**
   - Add the post-processor path to **User Post Processor Path**

4. Restart FreeCAD

## Usage

1. Create a Job in FreeCAD Path Workbench
2. Add machining operations (Profile, Pocket, Drilling, etc.)
3. Select the **woodwop** post-processor in Job settings
4. Execute **Path → Post Process**
5. Confirm file names in the dialog

## Output Files

The post-processor creates three files:

1. **`{PartName}_{JobName}.mpr`** - Main file in WoodWOP MPR 4.0 format
2. **`{PartName}_{JobName}.nc`** - G-code file for comparison
3. **`{PartName}_{JobName}_job_report.txt`** - Job properties report

## File Naming

File names are automatically generated based on:
- Part name (from `Job.Base` or `Job.Model`)
- Job name

The "Model-" prefix is automatically removed from file names.

## Parameters

- `--no-comments` - Disable comment output
- `--precision=X` - Set coordinate precision (default 3)
- `--workpiece-length=X` - Workpiece length in mm (auto-detect by default)
- `--workpiece-width=Y` - Workpiece width in mm (auto-detect by default)
- `--workpiece-thickness=Z` - Workpiece thickness in mm (auto-detect by default)

## MPR 4.0 Format

The post-processor generates files in WoodWOP MPR 4.0 Alpha format, compatible with:
- WoodWOP 9.0.152 and above
- HOMAG CNC machines

## Project Structure

```
woodwop post/
├── woodwop_post.py          # Main post-processor
├── README.md                # This file (Russian)
├── README.en.md             # This file (English)
├── CHANGES_REPORT.md        # Changes report (Russian)
├── CHANGES_REPORT.en.md     # Changes report (English)
├── INSTALL_INSTRUCTIONS.md  # Installation instructions (Russian)
├── INSTALL_INSTRUCTIONS.en.md # Installation instructions (English)
├── USAGE_GUIDE.md           # Usage guide (Russian)
├── USAGE_GUIDE.en.md        # Usage guide (English)
├── CHANGELOG.md             # Changelog (Russian)
├── CHANGELOG.en.md          # Changelog (English)
└── Tools/                   # FreeCAD tools
    ├── Bit/                 # Tool library
    └── Library/             # Tool library
```

## Requirements

- FreeCAD 1.2.0 or higher
- Python 3.10 or higher
- Path Workbench (built into FreeCAD)

## Known Limitations

- Manual comparison of MPR and NC files is required to verify correctness
- Some operations may require additional parameter configuration

## License

This post-processor is distributed under the same license as FreeCAD (LGPL 2.1+).

## Support

For questions and suggestions, create Issues in this repository.

## Changelog

See [CHANGELOG.en.md](CHANGELOG.en.md) for detailed change history.

## Authors

Developed for integration with FreeCAD Path Workbench.

---

**Note:** This post-processor is under active development. Please verify output files before using on the machine.

