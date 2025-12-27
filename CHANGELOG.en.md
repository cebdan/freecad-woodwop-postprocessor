# WoodWOP Post Processor Changelog

## Version: Updated File Creation and Naming Logic

### Date: 2024

---

## Main Changes

### 1. Fixed File Creation Logic

**Problem:**
- FreeCAD created `.nc` file before calling `export()`
- Post-processor wrote both files (`.mpr` and `.nc`) independently
- Empty string was returned
- FreeCAD overwrote `.nc` file with empty content

**Solution:**
- Post-processor creates `.mpr` file with correct content
- Post-processor creates `.nc` file with G-code content
- G-code content is returned to FreeCAD so it writes it to `.nc` file
- Both files are created with the same base name

**Result:**
- Both files (`.mpr` and `.nc`) are created correctly
- FreeCAD doesn't overwrite files with empty content
- Files have correct content

---

### 2. Improved Base Filename Determination Logic

**Problem:**
- Filename was determined from FreeCAD dialog
- Job settings (Model, part name) were not used

**Solution:**
Implemented priority system for base name determination:

1. **PostProcessorOutputFile with full path** (if path specified)
2. **Model from Job** (variable "модел" or "Model")
3. **Part name** (part name from Job.Base)
4. **PostProcessorOutputFile with name only** (fallback)
5. **Name from FreeCAD dialog** (last fallback)
6. **"export"** (default value)

**Features:**
- Automatic search for Model property in Job (checks variants: Model, ModelName, модел)
- Search through PropertiesList for properties containing "model" or "модел"
- Extract part name from Job.Base (supports single objects and groups)
- Detailed debug information for diagnostics

**Result:**
- Files are created with name from Model or part name
- Dialog name is ignored if more priority sources exist
- Added debug information to track name source

---

### 3. Fixed Directory Determination Logic for Files

**Problem:**
- If `PostProcessorOutputFile` contained only filename without path (e.g., "ert")
- `os.path.dirname("ert")` returned empty string
- `os.path.abspath("ert")` in root directory gave "/"
- Attempt to write file to "/ert.mpr" caused "Read-only file system" error

**Solution:**
- Check for path in `PostProcessorOutputFile`
- If path is missing, use FreeCAD document directory
- Protection against using root directory "/"
- Directory determination priority:
  1. From `PostProcessorOutputFile` (if contains path)
  2. From FreeCAD document directory
  3. Current working directory (fallback)

**Result:**
- Files are created in correct directory
- No errors when writing to root directory
- Works even if `PostProcessorOutputFile` contains only filename

---

### 4. Ignoring FreeCAD Save Dialog

**Problem:**
- FreeCAD shows save dialog before calling `export()`
- Dialog name was used for filename determination

**Solution:**
- Completely ignore `filename` from dialog for filename determination
- Directory determined only from Job settings or document directory
- Filename determined only from Model or part name
- Added comments explaining that dialog is ignored

**Result:**
- Files are created automatically based on Model or part name
- Independent of what user enters in dialog
- Dialog may appear, but its content is ignored

---

### 5. Added Job Properties Report Creation

**New Feature:**
- Report file `{base_filename}_job_report.txt` is created
- Report contains all Job object properties
- Structured format with separators

**Report Content:**
- Basic information (Label, Name, TypeId)
- All Job properties with their values
- Special properties (PostProcessorOutputFile, Model, Base, Stock, Operations, etc.)
- Stock information (if available)

**Result:**
- Helps diagnose filename determination issues
- Shows all available Job properties
- Simplifies debugging and configuration

---

## Technical Details

### Modified Functions

1. **`export()`** - main export function
   - Added base name determination logic with priorities
   - Improved directory determination logic
   - Added Job properties report creation
   - Ignoring `filename` from dialog

2. **`create_job_report()`** - new function
   - Creates detailed report of all Job properties
   - Formats values depending on type
   - Handles special FreeCAD types (Value, Unit, Label)

### Added Debug Information

- Logging of all found values (job_output_file, job_model, part_name)
- Tracking of priority used for name determination
- Output of all Job properties if Model not found automatically
- Information about ignoring dialog name

---

## Usage

### Filename Determination

1. Set **Model** variable in Job (or use part name)
2. Post-processor will automatically create files with this name
3. FreeCAD dialog may appear, but its content is ignored

### Created Files

- `{name}.mpr` - WoodWOP MPR file
- `{name}.nc` - G-code file
- `{name}_job_report.txt` - Job properties report

### Debugging

If filename is determined incorrectly:
1. Check report `{name}_job_report.txt`
2. Find Model property in report
3. Check FreeCAD logs for debug information
4. Ensure Model is set in Job

---

## Known Limitations

1. **FreeCAD Dialog:** Save dialog may appear at FreeCAD UI level (before calling `export()`). We cannot completely disable it from post-processor, but completely ignore its content.

2. **woodwop_gcode_post module:** If `woodwop_gcode_post` module is not found, simplified G-code generation is used.

---

## Future Improvements

- Ability to configure priorities via command line arguments
- Support for additional filename sources
- Improved error handling
- Performance optimization

---

## Conclusion

All main problems with file creation and name determination are resolved. Post-processor now:
- Creates both files (`.mpr` and `.nc`) correctly
- Uses name from Model or part name instead of dialog name
- Creates files in correct directory
- Provides detailed debug information
- Creates Job properties report for diagnostics

