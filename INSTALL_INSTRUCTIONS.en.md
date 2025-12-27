# Installation Instructions for WoodWOP Post Processor for FreeCAD

## Method 1: System Directory Installation (Recommended)

This method requires administrator rights, but the post-processor will be available for all users.

### macOS:

1. Open Finder
2. Press `Cmd+Shift+G` (Go to Folder)
3. Paste path: `/Applications/FreeCAD.app/Contents/Resources/Mod/CAM/Path/Post/scripts/`
4. Click "Go"
5. Copy `woodwop_post.py` file to this folder
6. Enter administrator password when prompted
7. Restart FreeCAD

### Via Terminal (macOS):

```bash
sudo cp "woodwop_post.py" "/Applications/FreeCAD.app/Contents/Resources/Mod/CAM/Path/Post/scripts/"
```

---

## Method 2: User Directory Installation

This method does not require administrator rights.

### macOS:

#### Option A: Via Preferences (FreeCAD settings)

1. Launch FreeCAD
2. Open **Edit → Preferences → CAM → Job Preferences**
3. Find **User Post Processor Path** or **Search Path** option
4. Click the three dots button `...` and select the folder where you want to place the post-processor
5. Or create folder manually, e.g.: `~/Documents/FreeCAD_PostProcessors/`
6. Copy `woodwop_post.py` to this folder
7. Restart FreeCAD

#### Option B: Via Terminal

```bash
# Create directory for post-processors
mkdir -p "$HOME/Documents/FreeCAD_PostProcessors"

# Copy file
cp "woodwop_post.py" "$HOME/Documents/FreeCAD_PostProcessors/"
```

Then in FreeCAD, specify path to this folder in settings (see Option A).

---

## Method 3: Via Macro Directory (Alternative)

**Note**: This method may not work in all FreeCAD versions.

### macOS:

```bash
# Create directory
mkdir -p "$HOME/Library/Application Support/FreeCAD/Macro"

# Copy file
cp "woodwop_post.py" "$HOME/Library/Application Support/FreeCAD/Macro/"
```

---

## Installation Verification

1. Launch FreeCAD
2. Open or create a project with Path workbench
3. Create Job and machining operations
4. Select **Path → Post Process** (or click Post Process button)
5. In the **Post Processor** dropdown, **woodwop_post** should appear
6. If post-processor is not in the list:
   - Restart FreeCAD
   - Check file path correctness
   - Ensure file is named exactly `woodwop_post.py`

---

## Configuring Post-Processor Path in FreeCAD

If post-processor doesn't appear:

1. Open **Edit → Preferences**
2. Go to **CAM → Job Preferences** (or **Path → Job Preferences** in older versions)
3. Find **Post Processor** section
4. In **Search Path** or **User Post Processor Path** field, specify path to folder containing `woodwop_post.py`
5. Click **OK**
6. Restart FreeCAD

---

## Usage

After installation:

1. In Path workbench, create Job and operations
2. Click **Path → Post Process**
3. Select **woodwop_post** from the list
4. If needed, specify arguments (e.g.: `--precision=2`)
5. Click **OK**
6. Select location to save .mpr file
7. Open generated file in WoodWOP

---

## Supported FreeCAD Operations

- **Profile** / **Contour** → Contourfraesen (contour milling)
- **Drilling** → BohrVert (vertical drilling)
- **Pocket** → Pocket (pockets)

---

## Command Line Arguments

In the "Arguments" field you can specify:

- `--no-comments` - remove comments from MPR file
- `--precision=2` - coordinate precision (number of decimal places)
- `--workpiece-length=800` - workpiece length in mm
- `--workpiece-width=600` - workpiece width in mm
- `--workpiece-thickness=18` - workpiece thickness in mm
- `--use-part-name` - name MPR file after part name instead of document

Example:
```
--precision=2 --workpiece-thickness=18 --no-comments --use-part-name
```

---

## Troubleshooting

### Post-processor doesn't appear in list

**Solution 1**: Check file name
- File must be named **exactly** `woodwop_post.py`
- Extension must be `.py`, not `.py.txt`

**Solution 2**: Check access rights
```bash
ls -la "$HOME/Library/Application Support/FreeCAD/Macro/woodwop_post.py"
```
File must have read permissions (r--).

**Solution 3**: Check path in FreeCAD settings
- Edit → Preferences → CAM → Job Preferences
- Ensure post-processor path is specified correctly

**Solution 4**: Clear FreeCAD cache
```bash
rm -rf "$HOME/Library/Application Support/FreeCAD/Mod/__pycache__"
```

### Export error

Check FreeCAD console (**View → Panels → Report view**) for error details.

Common issues:
- Job not created
- ToolController not assigned
- Operations are empty (no paths)

---

## Additional Information

See `README.en.md` for detailed documentation.

MPR format specification: `mpr4x_format_us (1).txt`

